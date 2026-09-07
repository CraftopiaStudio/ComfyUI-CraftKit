"""Containment guard for nodes that take a free-text folder path (SmartBatchResize's
`input_folder`).

WHY THIS EXISTS
----------------
ComfyUI's /prompt endpoint is unauthenticated, so any STRING widget value is
effectively attacker-controlled: a malicious webpage open in the same browser
can POST a crafted prompt to http://127.0.0.1:8188/prompt via CSRF. A node
that reads/writes an arbitrary user-supplied folder is therefore an
unconfined filesystem read/write reachable without any real authorization —
exactly what got CraftKit 1.0.1-1.1.1 banned from the registry (HIGH severity,
see smart_batch_resize.py:246-263 in the pre-fix version).

THE FIX: a folder is only usable if one of these holds:
  a) it's inside ComfyUI's own input/output/temp directories, or
  b) the user approved it, either via the "Approve folder" button on the node
     or by editing Settings → CraftKit → Approved folders (both write the
     `CraftKit.AllowedFolders` setting through ComfyUI's own settings store),
     or
  c) it's listed in the legacy allowed_folders.json.

There is deliberately no "allow everything" escape hatch. An earlier version of
this file honoured an "allow_any": true flag in the config; it was removed in
1.1.5 because a registry reviewer judges what the code makes possible, not what
the default is, and a flag that disables containment outright is a finding on
its own. Anyone who needs a wide scope approves a wide folder instead.

Up to 1.1.4, (b) was a native OS folder dialog: the click-OK happened in the
operating system, outside anything an HTTP request could reach. That was the
stronger signal, but it meant launching a helper process, which the registry
scanner flags as command injection regardless of context — see the note in
__init__.py. Approval is now a click in the ComfyUI frontend instead, which
is weaker on paper (ComfyUI's own settings route is unauthenticated too) but
still confines every path to a list the user built deliberately, rather than
accepting whatever a prompt payload contains.

Legacy config lives at <ComfyUI user dir>/craftkit/allowed_folders.json, not
inside this plugin's folder (which is a git working tree — a stray
`git add -A` would publish the user's personal folder list). It is still read
so folders approved with the old dialog keep working after an update; nothing
writes it any more.

Pattern adapted from Pixaroma's ComfyUI-Pixaroma/nodes/_path_guard.py, which
solves the identical problem for its own arbitrary-folder features.
"""
from __future__ import annotations

import json
import os

_CONFIG_NAME = "allowed_folders.json"

# Setting id under which approved folders are stored in ComfyUI's own settings.
# Must stay identical to the id registered in js/smart_batch_resize.js.
SETTING_KEY = "CraftKit.AllowedFolders"


def is_path_under(child: str, *parents: str) -> bool:
    """True iff `child` resolves inside ANY of `parents`.

    Strict realpath-on-both-sides is the primary (and usually only) test. A
    lexical (abspath) fallback runs only when the strict comparison can't even
    be made because the two sides land on different drives (e.g. a models
    folder junctioned onto another disk) — os.path.commonpath raises
    ValueError in that case rather than just returning False.
    """
    if not child or not isinstance(child, str):
        return False
    try:
        child_real = os.path.realpath(child)
        child_abs = os.path.abspath(child)
    except (OSError, ValueError, TypeError):
        return False
    for p in parents:
        if not p or not isinstance(p, str):
            continue
        cross_drive = False
        try:
            parent_real = os.path.realpath(p)
            if os.path.commonpath([child_real, parent_real]) == parent_real:
                return True
        except ValueError:
            cross_drive = True
        except (OSError, TypeError):
            continue
        if not cross_drive:
            continue
        try:
            parent_abs = os.path.abspath(p)
            if os.path.commonpath([os.path.normcase(child_abs), os.path.normcase(parent_abs)]) == os.path.normcase(parent_abs):
                return True
        except (OSError, ValueError, TypeError):
            continue
    return False


def _norm_raw(p) -> str:
    if not p or not isinstance(p, str):
        return ""
    return p.strip().strip('"').strip("'").strip()


def unc_like(p) -> bool:
    r"""True for a Windows UNC path (\\server\share, //server/share).

    Purely lexical — must not touch the filesystem. Merely calling
    os.path.realpath/isdir on a UNC path makes Windows open an SMB connection
    and hand over an NTLM hash before any containment check gets to run, so a
    UNC value has to be judged before it's resolved, not after.
    """
    return _norm_raw(p).replace("/", "\\").startswith("\\\\")


def is_unc_root(p) -> bool:
    r"""True when `p` is exactly a UNC share root (\\server\share, no subpath).

    os.path.commonpath can't compare such a root against a path inside it
    (splitdrive gives an empty, "relative"-looking remainder), so it has to be
    matched by prefix instead — see _lexically_under_any.
    """
    try:
        drive, rest = os.path.splitdrive(os.path.abspath(p))
    except (OSError, ValueError, TypeError):
        return False
    return drive.replace("/", "\\").startswith("\\\\") and rest.strip("\\/") == ""


def _lexically_under_any(child: str, parents) -> bool:
    """Prefix test on abspath only — no realpath, so no filesystem access.
    Weaker than is_path_under (a symlink could fool it); used only to accept a
    UNC path under a share root the user already approved via the picker."""
    child = _norm_raw(child)
    if not child:
        return False
    try:
        c = os.path.normcase(os.path.abspath(child))
    except (OSError, ValueError, TypeError):
        return False
    for p in parents or ():
        p = _norm_raw(p)
        if not p:
            continue
        try:
            pa = os.path.normcase(os.path.abspath(p)).rstrip("\\/")
        except (OSError, ValueError, TypeError):
            continue
        if pa and (c == pa or c.startswith(pa + os.sep) or c.startswith(pa + "/")):
            return True
    return False


def comfy_roots() -> list:
    """ComfyUI's own input/output/temp directories, whichever resolve.

    folder_paths is imported lazily so this module stays importable outside a
    live ComfyUI process (e.g. under pytest).
    """
    roots = []
    try:
        import folder_paths
    except Exception:
        return roots
    for getter in ("get_input_directory", "get_output_directory", "get_temp_directory"):
        try:
            fn = getattr(folder_paths, getter, None)
            v = fn() if callable(fn) else None
            if v:
                roots.append(v)
        except Exception:
            continue
    return roots


def _config_path() -> str:
    base = None
    try:
        import folder_paths
        base = folder_paths.get_user_directory()
    except Exception:
        base = None
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".craftkit")
    return os.path.join(base, "craftkit", _CONFIG_NAME)


def _read_config() -> dict:
    """Never raises — a missing or damaged file means 'nothing extra is
    allowed', never an exception mid-run. `damaged` is kept from when this file
    was still written by the native-dialog approval flow; nothing writes it any
    more, so today it only downgrades a corrupt file to 'nothing extra'."""
    out = {"folders": [], "damaged": False}
    path = _config_path()
    if not os.path.exists(path):
        return out
    try:
        # utf-8-sig transparently strips a BOM if present (e.g. a file written
        # by PowerShell's `Set-Content -Encoding utf8`, or hand-edited in an
        # older Notepad) — plain utf-8 would otherwise fail to parse it and
        # this file would wrongly read as "damaged".
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
    except Exception:
        out["damaged"] = True
        return out
    if not isinstance(obj, dict):
        out["damaged"] = True
        return out
    folders = obj.get("folders")
    if isinstance(folders, list):
        out["folders"] = [x for x in folders if isinstance(x, str) and x.strip()]
    elif folders is not None:
        out["damaged"] = True
    return out


def _settings_file() -> str:
    """ComfyUI's own settings JSON, where the Approve button stores folders.

    Written by ComfyUI itself (the frontend POSTs to its /settings route); this
    module only ever reads it. Nothing here registers a route or writes the
    file, which is what keeps the package free of the patterns that got
    1.1.2-1.1.4 banned — see __init__.py.
    """
    base = None
    try:
        import folder_paths
        base = folder_paths.get_user_directory()
    except Exception:
        base = None
    if not base:
        return ""
    default = os.path.join(base, "default", "comfy.settings.json")
    if os.path.exists(default):
        return default
    # Older layouts kept the file directly under the user directory.
    flat = os.path.join(base, "comfy.settings.json")
    return flat if os.path.exists(flat) else ""


def _split_folders(value) -> list:
    """Accept either a list or a ';'/newline-separated string.

    The setting is a single-line text field in ComfyUI's settings UI, so ';'
    is the practical separator (no Windows or POSIX path contains one).
    Newlines are accepted too for anyone who pastes a list by hand.
    """
    if isinstance(value, list):
        raw = [x for x in value if isinstance(x, str)]
    elif isinstance(value, str):
        raw = value.replace("\r", "\n").replace(";", "\n").split("\n")
    else:
        return []
    return [p for p in (_norm_raw(x) for x in raw) if p]


def settings_folders() -> list:
    """Folders the user approved via the node button or the settings UI.

    Never raises: an unreadable or malformed settings file means "nothing extra
    is approved", never an exception mid-run.
    """
    path = _settings_file()
    if not path:
        return []
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    return _split_folders(obj.get(SETTING_KEY))


def approved_folders() -> list:
    """Every folder the user approved, from both stores.

    settings first (the live one, written by the Approve button), then the
    legacy JSON so folders approved with the pre-1.1.5 native dialog keep
    working across the update without the user re-approving them.
    """
    return settings_folders() + _read_config()["folders"]


def prescreen(raw) -> bool:
    """Cheap no-filesystem screen to run BEFORE anything calls realpath/isdir
    on an untrusted folder string. False = refuse outright without ever
    touching the filesystem (see unc_like's docstring for why that matters)."""
    if unc_like(raw):
        return _lexically_under_any(raw, approved_folders())
    return True


def folder_allowed(path: str) -> bool:
    """True when `path` is somewhere SmartBatchResize may read/write."""
    if not path or not isinstance(path, str):
        return False
    if not prescreen(path):
        return False
    roots = comfy_roots()
    if roots and is_path_under(path, *roots):
        return True
    folders = approved_folders()
    if not folders:
        return False
    if is_path_under(path, *folders):
        return True
    unc_roots = [f for f in folders if is_unc_root(f)]
    return bool(unc_roots) and _lexically_under_any(path, unc_roots)


def denied_message(path: str) -> str:
    return (
        f"[SmartBatchResize] Folder not approved: {path}\n"
        "To approve it: put this path in the node's input_folder field and click "
        "'Approve folder'. That approves it, and everything under it, permanently.\n"
        "The full list is editable under Settings > CraftKit > Approved folders.\n"
        "ComfyUI's own input/output/temp folders always work without approval."
    )
