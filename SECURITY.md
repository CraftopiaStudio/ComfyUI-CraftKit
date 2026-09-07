# Security

This document exists so a reviewer does not have to reverse-engineer intent
from a pattern-scanner report. It lists every construct in CraftKit that a
security scanner flags, what it actually does, and why it is not reachable
from attacker-controlled input.

Please open an issue at
<https://github.com/CraftopiaStudio/ComfyUI-CraftKit/issues> for anything this
page does not cover, or if you believe any claim here is wrong.

## Summary

- **No third-party dependencies.** `pyproject.toml` declares
  `dependencies = []`. Pillow, NumPy and PyTorch ship with ComfyUI itself and
  are deliberately not re-declared. Nothing is installed or downloaded at
  runtime.
- **No outbound network traffic.** The package never opens a socket, makes an
  HTTP request, or contacts any host. No telemetry, no update check, no
  analytics. There is no `requests`, `urllib`, `socket`, or `http.client`
  import anywhere in it.
- **No `eval`, `exec`, `compile`, `pickle`, `marshal`, or `__import__()`.**
- **No HTTP routes.** As of 1.1.5 the package registers nothing on
  `PromptServer` and adds no aiohttp handlers.
- **No process execution.** As of 1.1.5 there is not a single `subprocess`,
  `os.system`, or `os.popen` call site in the package.
- **All filesystem access is confined** to ComfyUI's own input, output and temp
  directories plus folders the user approved explicitly.

## The one node that touches the filesystem

Four of the five nodes (`SmartResize`, `SmartResolutionMultiplier`,
`SmartPromptController`, `SmartProfileSwitch`) are pure computation on tensors,
numbers and strings. They open no files and take no paths.

`SmartBatchResize` in `smart_batch_resize.py` is the only node that reads and
writes files. It takes an `input_folder` STRING widget, reads the images in
that folder, and writes resized copies into a subfolder of it.

### Why a free STRING path is treated as hostile

ComfyUI's `/prompt` endpoint is unauthenticated, so any widget value is
effectively attacker-controlled: a malicious page open in the same browser can
POST a crafted prompt to `http://127.0.0.1:8188/prompt` by CSRF. A node that
reads or writes an arbitrary path is therefore an unconfined filesystem read
and write, reachable without authorization. That is exactly what got versions
1.0.1 through 1.1.1 banned from the registry, and the finding was correct.

### The containment, and where it runs

`craftkit_folder_guard.folder_allowed()` decides whether a path may be used at
all. A path is accepted only if:

1. it resolves inside one of ComfyUI's own directories
   (`folder_paths.get_input_directory()`, `get_output_directory()`,
   `get_temp_directory()`), or
2. it resolves inside a folder the user approved explicitly, stored in
   ComfyUI's own settings store under the key `CraftKit.AllowedFolders`, or
3. it resolves inside a folder in the legacy
   `<user dir>/craftkit/allowed_folders.json`, kept readable so approvals made
   before 1.1.5 survive the update. Nothing in the package writes that file any
   more.

Containment is `os.path.realpath` on both sides plus `os.path.commonpath`
against each allowed root, in `is_path_under()`. Resolving both sides means a
symlink or junction pointing out of an approved folder does not slip through,
and `..` cannot walk upward, because the comparison happens after resolution.

The guard is called before any filesystem access, on both paths:

| Call site | Guards |
| --- | --- |
| `smart_batch_resize.py:251` | `run()`, before `iterdir()`, before `PILImage.open()`, and before the output directory is created |
| `smart_batch_resize.py:213` | `IS_CHANGED()`, before the folder is listed for cache hashing |

So reads are gated, not only writes. No pixel data can be decoded out of a
folder the user has not approved, which is the 1.0.1 `ARBITRARY_FILE_READ`
finding.

### The write target

The output subfolder name is validated separately, in `run()`: it is rejected
if it is absolute, carries a drive letter, contains `..`, or contains any path
separator. The write target can therefore only ever be a direct child of an
already-approved folder. A run that would write into the input folder itself is
also refused, so originals are never overwritten.

### No escape hatch

Before 1.1.5 the config honoured an `"allow_any": true` flag that disabled
containment. It is removed. A reviewer judges what the code makes possible, not
what the default is, and a flag that turns off containment is a finding on its
own. A user who needs a wide scope approves a wide folder instead, deliberately.

### Two smaller precautions

- **UNC paths are screened before resolution.** On Windows, merely calling
  `os.path.realpath()` or `os.path.isdir()` on a `\\server\share` path opens an
  SMB connection and hands over an NTLM hash before any containment check gets
  to run. `prescreen()` in the guard therefore judges UNC values lexically and
  refuses them outright unless they sit under a share root the user already
  approved. No filesystem call happens first.
- **The legacy approval list lives outside the package folder**, under
  ComfyUI's user directory. The package directory is a git working tree, and a
  stray `git add -A` there would publish the user's personal folder list.

## Removed in 1.1.5

Up to 1.1.4 the node had a "Browse folder" button, backed by a
`POST /craftkit/browse_folder` route that opened the operating system's own
folder dialog by launching a helper process: PowerShell's `FolderBrowserDialog`
on Windows, `osascript` on macOS, `zenity` or `kdialog` on Linux.

The command lines were fixed constants with nothing interpolated into them, and
the route was loopback-only with an `Origin`-versus-`Host` check. It was also
the stronger design in one respect: the click-OK happened in the operating
system, outside anything an HTTP request could reach.

It is gone regardless. Versions 1.1.2, 1.1.3 and 1.1.4 were banned for command
injection, and 1.1.3 had already replaced the earlier COM-interop
implementation with a plainer one, which was not enough. The feature is removed
rather than reworked a third time. Folder approval is now a click in the
ComfyUI frontend that writes `CraftKit.AllowedFolders` through ComfyUI's own
settings route. The package only ever reads that setting.

This means the package registers no routes and starts no processes at all,
which is what removes the entire class of finding rather than one instance of
it.

## Known scanner findings and why they are false positives

| Pattern | Where | What it is |
| --- | --- | --- |
| `PILImage.open(f)` | `smart_batch_resize.py` | Decoding an image file the user approved the folder for. Gated by `folder_allowed()` above it. |
| `Path(input_folder).iterdir()` | `smart_batch_resize.py` | Listing that same approved folder. Same gate. |
| `open(path, "r")` | `craftkit_folder_guard.py` | Reading two JSON files, both under ComfyUI's user directory, both read-only, both with fixed names. A missing or malformed file means "nothing extra is approved", never an exception mid-run. |
| `json.load()` | `craftkit_folder_guard.py` | The same two files. No `pickle`, no `yaml.load`, no deserialization of user-supplied objects. |

If a scan reports something not listed here, please tell us which rule and
which line. We would rather remove a construct than have a version banned for
it.
