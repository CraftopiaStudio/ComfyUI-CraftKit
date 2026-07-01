WEB_DIRECTORY = "./js"

from .smart_prompt_controller import NODE_CLASS_MAPPINGS as A, NODE_DISPLAY_NAME_MAPPINGS as A_NAMES
from .smart_profile_switch import NODE_CLASS_MAPPINGS as B, NODE_DISPLAY_NAME_MAPPINGS as B_NAMES
from .smart_resize import NODE_CLASS_MAPPINGS as C, NODE_DISPLAY_NAME_MAPPINGS as C_NAMES
from .smart_batch_resize import NODE_CLASS_MAPPINGS as D, NODE_DISPLAY_NAME_MAPPINGS as D_NAMES
from .smart_resolution_multiplier import NODE_CLASS_MAPPINGS as E, NODE_DISPLAY_NAME_MAPPINGS as E_NAMES

NODE_CLASS_MAPPINGS = {**A, **B, **C, **D, **E}
NODE_DISPLAY_NAME_MAPPINGS = {**A_NAMES, **B_NAMES, **C_NAMES, **D_NAMES, **E_NAMES}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

import asyncio
import concurrent.futures
from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.get("/craftkit/browse_folder")
async def browse_folder(request):
    import subprocess, sys

    def _open_dialog():
        if sys.platform != "win32":
            return ""
        ps = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class CraftKitFolderPicker
{
    [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")]
    private class FileOpenDialogRCW { }

    [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IFileDialog
    {
        [PreserveSig] int Show(IntPtr parent);
        void SetFileTypes(uint cFileTypes, IntPtr rgFilterSpec);
        void SetFileTypeIndex(uint iFileType);
        void GetFileTypeIndex(out uint piFileType);
        void Advise(IntPtr pfde, out uint pdwCookie);
        void Unadvise(uint dwCookie);
        void SetOptions(uint fos);
        void GetOptions(out uint fos);
        void SetDefaultFolder(IntPtr psi);
        void SetFolder(IntPtr psi);
        void GetFolder(out IntPtr ppsi);
        void GetCurrentSelection(out IntPtr ppsi);
        void SetFileName(string pszName);
        void GetFileName(out IntPtr pszName);
        void SetTitle(string pszTitle);
        void SetOkButtonLabel(string pszText);
        void SetFileNameLabel(string pszLabel);
        void GetResult(out IShellItemLocal ppsi);
        void AddPlace(IntPtr psi, uint fdap);
        void SetDefaultExtension(string pszDefaultExtension);
        void Close(int hr);
        void SetClientGuid(ref Guid guid);
        void ClearClientData();
        void SetFilter(IntPtr pFilter);
    }

    [ComImport, Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellItemLocal
    {
        void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
        void GetParent(out IShellItemLocal ppsi);
        void GetDisplayName(uint sigdnName, out IntPtr ppszName);
        void GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
        void Compare(IShellItemLocal psi, uint hint, out int piOrder);
    }

    public static string ShowDialog(IntPtr owner, string title)
    {
        var dialog = (IFileDialog)new FileOpenDialogRCW();
        dialog.SetOptions(0x20u | 0x40u); // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
        if (!string.IsNullOrEmpty(title)) dialog.SetTitle(title);
        int hr = dialog.Show(owner);
        if (hr != 0) return null;
        IShellItemLocal item;
        dialog.GetResult(out item);
        IntPtr pszPath;
        item.GetDisplayName(0x80058000u, out pszPath); // SIGDN_FILESYSPATH
        string path = Marshal.PtrToStringAuto(pszPath);
        Marshal.FreeCoTaskMem(pszPath);
        return path;
    }
}
"@

$r = ''
$o = New-Object System.Windows.Forms.Form
$o.TopMost = $true
$o.ShowInTaskbar = $false
$o.FormBorderStyle = 'None'
$o.Width = 1; $o.Height = 1; $o.Opacity = 0
$o.StartPosition = 'CenterScreen'
$o.Add_Shown({
    $o.Activate()
    $path = [CraftKitFolderPicker]::ShowDialog($o.Handle, 'Select input folder')
    if ($path) { $script:r = $path }
    $o.Close()
})
$o.ShowDialog() | Out-Null
$r
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True
        )
        return result.stdout.strip()

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        folder = await loop.run_in_executor(pool, _open_dialog)

    if folder and __import__("os").path.isdir(folder):
        return web.json_response({"ok": True, "path": folder})
    return web.json_response({"ok": False, "cancelled": True})
