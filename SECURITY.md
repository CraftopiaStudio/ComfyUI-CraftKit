# Security

This document exists so a reviewer does not have to reverse-engineer intent
from a pattern-scanner report. It lists every construct in CraftKit that a
security scanner flags, what it actually does, and why it is not reachable
from attacker-controlled input.

> **A note on how this file is written.** The registry scanner reads Markdown
> as if it were source, so a security document that quotes the very call syntax
> it is explaining adds findings to its own package. Function names below are
> therefore written without their call parentheses and arguments. Nothing is
> being hidden: every construct is named, and the line numbers point at the
> real code.

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
- **No dynamic execution**: no eval, no exec, no compile, no pickle, no
  marshal, and no dunder-import builtin anywhere in the package.
- **No HTTP routes.** As of 1.1.5 the package registers nothing on
  `PromptServer` and adds no aiohttp handlers.
- **No process execution.** As of 1.1.5 the package contains no process
  spawning call of any kind: no subprocess module use, no os-level system or
  popen call.
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

The guard function `folder_allowed` in `craftkit_folder_guard.py` decides
whether a path may be used at all. A path is accepted only if:

1. it resolves inside one of ComfyUI's own directories
   (the input, output and temp directory getters on ComfyUI's own
   `folder_paths` module), or
2. it resolves inside a folder the user approved explicitly, stored in
   ComfyUI's own settings store under the key `CraftKit.AllowedFolders`, or
3. it resolves inside a folder in the legacy
   `<user dir>/craftkit/allowed_folders.json`, kept readable so approvals made
   before 1.1.5 survive the update. Nothing in the package writes that file any
   more.

Containment is `os.path.realpath` on both sides plus `os.path.commonpath`
against each allowed root, in the `is_path_under` helper. Resolving both sides
means a symlink or junction pointing out of an approved folder does not slip
through,
and `..` cannot walk upward, because the comparison happens after resolution.

The guard is called before any filesystem access, on both paths:

| Call site | Guards |
| --- | --- |
| `smart_batch_resize.py:251` | the node's run method, ahead of the directory listing, ahead of any image decode, and ahead of creating the output directory |
| `smart_batch_resize.py:213` | the IS_CHANGED classmethod, ahead of the listing used for cache hashing |

So reads are gated, not only writes. No pixel data can be decoded out of a
folder the user has not approved, which is the 1.0.1 `ARBITRARY_FILE_READ`
finding.

### The write target

The output subfolder name is validated separately, in the run method: it is
rejected if it is absolute, carries a drive letter, contains `..`, or contains
any path separator. The write target can therefore only ever be a direct child of an
already-approved folder. A run that would write into the input folder itself is
also refused, so originals are never overwritten.

### No escape hatch

Before 1.1.5 the config honoured an `"allow_any": true` flag that disabled
containment. It is removed. A reviewer judges what the code makes possible, not
what the default is, and a flag that turns off containment is a finding on its
own. A user who needs a wide scope approves a wide folder instead, deliberately.

### Two smaller precautions

- **UNC paths are screened before resolution.** On Windows, merely resolving or
  stat-ing a `\\server\share` path opens an SMB connection and hands over an
  NTLM hash before any containment check gets to run. The `prescreen` helper
  therefore judges UNC values lexically and refuses them outright unless they
  sit under a share root the user already approved. No filesystem call happens
  first.
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
| Pillow image decode | `smart_batch_resize.py` | Decoding an image file in a folder the user approved. The guard runs above it. |
| pathlib directory listing | `smart_batch_resize.py` | Listing that same approved folder. Same guard. |
| two read-only file opens | `craftkit_folder_guard.py` | Reading two JSON files, both under ComfyUI's user directory, both with fixed names, never written. A missing or malformed file means "nothing extra is approved", never an exception mid-run. |
| JSON parsing | `craftkit_folder_guard.py` | The same two files. No pickle, no YAML loader, no deserialization of user-supplied objects. |

If a scan reports something not listed here, please tell us which rule and
which line. We would rather remove a construct than have a version banned for
it.
