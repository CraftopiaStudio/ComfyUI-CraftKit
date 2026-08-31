WEB_DIRECTORY = "./js"

from .smart_prompt_controller import NODE_CLASS_MAPPINGS as A, NODE_DISPLAY_NAME_MAPPINGS as A_NAMES
from .smart_profile_switch import NODE_CLASS_MAPPINGS as B, NODE_DISPLAY_NAME_MAPPINGS as B_NAMES
from .smart_resize import NODE_CLASS_MAPPINGS as C, NODE_DISPLAY_NAME_MAPPINGS as C_NAMES
from .smart_batch_resize import NODE_CLASS_MAPPINGS as D, NODE_DISPLAY_NAME_MAPPINGS as D_NAMES
from .smart_resolution_multiplier import NODE_CLASS_MAPPINGS as E, NODE_DISPLAY_NAME_MAPPINGS as E_NAMES

NODE_CLASS_MAPPINGS = {**A, **B, **C, **D, **E}
NODE_DISPLAY_NAME_MAPPINGS = {**A_NAMES, **B_NAMES, **C_NAMES, **D_NAMES, **E_NAMES}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

try:
    import asyncio
    import concurrent.futures
    import os
    import threading
    from aiohttp import web
    from server import PromptServer

    _dialog_lock = threading.Lock()
    # Must match the literal 'CRAFTKIT_DIALOG_ERROR:' prefix written by the
    # PowerShell catch block below (kept literal there to avoid brace-escaping
    # a dense here-string).
    _DIALOG_ERROR_PREFIX = "CRAFTKIT_DIALOG_ERROR:"

    def _open_dialog_macos():
        import subprocess
        script = 'POSIX path of (choose folder with prompt "Select input folder")'
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=300
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        if result.returncode != 0:
            return ""  # cancelled, or osascript unavailable
        return result.stdout.strip()

    _LINUX_PICKER_COMMANDS = [
        ["zenity", "--file-selection", "--directory", "--title=Select input folder"],
        ["kdialog", "--getexistingdirectory", os.path.expanduser("~"), "--title", "Select input folder"],
    ]

    def _open_dialog_linux():
        import subprocess
        for cmd in _LINUX_PICKER_COMMANDS:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                return ""
            if result.returncode != 0:
                return ""  # cancelled
            return result.stdout.strip()
        print("[CraftKit] No folder picker found (tried zenity, kdialog); paste input folder paths manually.")
        return ""

    def _open_dialog_windows():
        # Deliberately uses the plain .NET FolderBrowserDialog instead of the
        # earlier IFileDialog/COM-interop approach (which used Add-Type to
        # compile inline C#, ComImport, and raw Marshal/IntPtr calls). That
        # pattern reads as COM-hijack-style shellcode to automated registry
        # scanners even though it was benign; this trades the modern Explorer
        # look for a plain tree-view dialog, in exchange for a much smaller,
        # ordinary-looking script with no dynamic code compilation.
        #
        # Reverting to the modern look: the full IFileDialog/COM version
        # (modern Explorer-style picker, works on Windows PowerShell 5.1 too)
        # lived here before commit that introduced this comment — `git log -p
        # -- __init__.py` to dig it out — and can be restored if the registry
        # confirms that code pattern wasn't actually the scan trigger, or once
        # pwsh is common enough that this fallback rarely matters. See
        # [[comfyui-browse-folder-dialog]] memory for the full history/tradeoffs.
        import subprocess
        ps = r"""
Add-Type -AssemblyName System.Windows.Forms
$r = ''
$o = New-Object System.Windows.Forms.Form
$o.TopMost = $true
$o.ShowInTaskbar = $false
$o.FormBorderStyle = 'None'
$o.Width = 1; $o.Height = 1; $o.Opacity = 0
$o.StartPosition = 'CenterScreen'
$o.Add_Shown({
    $o.Activate()
    try {
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = 'Select input folder'
        $dlg.ShowNewFolderButton = $true
        if ($dlg.ShowDialog($o) -eq [System.Windows.Forms.DialogResult]::OK) {
            $script:r = $dlg.SelectedPath
        }
    } catch {
        # Must match _DIALOG_ERROR_PREFIX in __init__.py.
        $script:r = 'CRAFTKIT_DIALOG_ERROR:' + $_.Exception.Message
    }
    $o.Close()
})
$o.ShowDialog() | Out-Null
$r
"""
        # PowerShell 7+ (pwsh, .NET 5+) renders FolderBrowserDialog with the
        # modern Explorer-style picker automatically; Windows PowerShell 5.1
        # (.NET Framework) only has the classic tree-view. Prefer pwsh when
        # present and fall back to the always-available powershell.exe.
        for exe in ("pwsh", "powershell"):
            try:
                result = subprocess.run(
                    [exe, "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=300,
                    # Without this, launching powershell.exe pops up its own
                    # visible console window behind the folder dialog (ComfyUI
                    # itself doesn't reuse it) — the dialog is the only UI this
                    # is meant to show.
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                return ""
            return result.stdout.strip()
        return ""

    def _open_dialog():
        import sys
        if sys.platform == "win32":
            return _open_dialog_windows()
        elif sys.platform == "darwin":
            return _open_dialog_macos()
        else:
            return _open_dialog_linux()

    async def browse_folder(request):
        if request.remote not in ("127.0.0.1", "::1"):
            return web.json_response({"ok": False, "error": "forbidden"}, status=403)

        origin = request.headers.get("Origin")
        if origin is not None:
            host = request.headers.get("Host", "")
            origin_host = origin.split("://", 1)[-1]
            if origin_host != host:
                return web.json_response({"ok": False, "error": "forbidden"}, status=403)

        if not _dialog_lock.acquire(blocking=False):
            return web.json_response({"ok": False, "error": "A folder dialog is already open."}, status=409)
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                folder = await loop.run_in_executor(pool, _open_dialog)
        finally:
            _dialog_lock.release()

        if folder.startswith(_DIALOG_ERROR_PREFIX):
            return web.json_response({"ok": False, "error": folder.removeprefix(_DIALOG_ERROR_PREFIX)}, status=500)

        if folder and os.path.isdir(folder):
            # The dialog's click-OK just happened in the operating system, not
            # in this request, so this is the one place a folder can be
            # authorized for SmartBatchResize's input_folder — see
            # craftkit_folder_guard.py.
            try:
                from .craftkit_folder_guard import remember_folder
                remember_folder(folder)
            except Exception as e:
                print(f"[CraftKit] Could not remember approved folder ({e}); it will need re-approving.")
            return web.json_response({"ok": True, "path": folder})
        return web.json_response({"ok": False, "cancelled": True})

    PromptServer.instance.routes.post("/craftkit/browse_folder")(browse_folder)
except Exception as e:
    print(f"[CraftKit] Browse folder endpoint unavailable ({e}); paste input folder paths manually.")
