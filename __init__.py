WEB_DIRECTORY = "./js"

from .smart_resize import NODE_CLASS_MAPPINGS as A, NODE_DISPLAY_NAME_MAPPINGS as A_NAMES
from .smart_batch_resize import NODE_CLASS_MAPPINGS as B, NODE_DISPLAY_NAME_MAPPINGS as B_NAMES
from .smart_resolution_multiplier import NODE_CLASS_MAPPINGS as C, NODE_DISPLAY_NAME_MAPPINGS as C_NAMES
from .smart_prompt_controller import NODE_CLASS_MAPPINGS as D, NODE_DISPLAY_NAME_MAPPINGS as D_NAMES

NODE_CLASS_MAPPINGS = {**A, **B, **C, **D}
NODE_DISPLAY_NAME_MAPPINGS = {**A_NAMES, **B_NAMES, **C_NAMES, **D_NAMES}

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
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$r='';"
            "$o=New-Object System.Windows.Forms.Form;"
            "$o.TopMost=$true;$o.ShowInTaskbar=$false;$o.FormBorderStyle='None';"
            "$o.Width=1;$o.Height=1;$o.Opacity=0;$o.StartPosition='CenterScreen';"
            "$o.Add_Shown({"
            "$o.Activate();"
            "$d=New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title='Select input folder';"
            "$d.ValidateNames=$false;$d.CheckFileExists=$false;$d.CheckPathExists=$true;"
            "$d.FileName='Folder Selection.';"
            "$d.Filter='Folders|*.none';"
            "if($d.ShowDialog($o) -eq 'OK'){$r=[System.IO.Path]::GetDirectoryName($d.FileName)};"
            "$o.Close()});"
            "$o.ShowDialog()|Out-Null;"
            "$r"
        )
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
