WEB_DIRECTORY = "./js"

from .smart_prompt_controller import NODE_CLASS_MAPPINGS as A, NODE_DISPLAY_NAME_MAPPINGS as A_NAMES
from .smart_profile_switch import NODE_CLASS_MAPPINGS as B, NODE_DISPLAY_NAME_MAPPINGS as B_NAMES
from .smart_resize import NODE_CLASS_MAPPINGS as C, NODE_DISPLAY_NAME_MAPPINGS as C_NAMES
from .smart_batch_resize import NODE_CLASS_MAPPINGS as D, NODE_DISPLAY_NAME_MAPPINGS as D_NAMES
from .smart_resolution_multiplier import NODE_CLASS_MAPPINGS as E, NODE_DISPLAY_NAME_MAPPINGS as E_NAMES

NODE_CLASS_MAPPINGS = {**A, **B, **C, **D, **E}
NODE_DISPLAY_NAME_MAPPINGS = {**A_NAMES, **B_NAMES, **C_NAMES, **D_NAMES, **E_NAMES}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

# This package deliberately registers no HTTP routes and launches no external
# processes.
#
# Up to 1.1.4 there was a "Browse folder" button here, backed by a POST
# /craftkit/browse_folder route that opened the native OS folder dialog by
# launching a helper process: PowerShell's FolderBrowserDialog on Windows,
# osascript on macOS, zenity/kdialog on Linux. The commands were fixed
# constants with nothing interpolated into them, and the route was
# loopback-only with an Origin/Host check.
#
# The Comfy Registry's yara scanner matches every process launch under rule
# `python_command_injection_risk` regardless of whether attacker input can
# reach it. On 1.1.2/1.1.3/1.1.4 that produced three severity-"info" hits, all
# of them these dialog calls and nothing else, after which a registry admin
# escalated each version from Flagged to Banned. Removing the calls removes the
# only finding the scanner has against this package.
#
# The scanner reads source text, so this note deliberately avoids naming the
# module involved: even a mention inside a comment can re-trigger the rule.
#
# Do not reintroduce a process launch or a PromptServer route here without
# checking the registry's current policy first. Folder approval moved to
# ComfyUI's own settings store instead — see craftkit_folder_guard.py.
