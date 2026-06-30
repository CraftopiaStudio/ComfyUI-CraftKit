import os
from pathlib import Path
from PIL import Image as PILImage
import numpy as np
import torch


INTERP_MAP = {
    "lanczos":  PILImage.LANCZOS,
    "bicubic":  PILImage.BICUBIC,
    "bilinear": PILImage.BILINEAR,
    "nearest":  PILImage.NEAREST,
}

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _calc_new_size(w, h, longest_side, multiple_of):
    longest = max(w, h)
    if longest <= longest_side:
        new_w, new_h = w, h
    else:
        scale = longest_side / longest
        new_w = int(w * scale)
        new_h = int(h * scale)
    if multiple_of > 1:
        new_w = max(multiple_of, round(new_w / multiple_of) * multiple_of)
        new_h = max(multiple_of, round(new_h / multiple_of) * multiple_of)
    return new_w, new_h


class SmartBatchResize:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # INPUT
                "input_folder": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Folder containing images to resize."
                }),

                # RESIZE SETTINGS
                "longest_side": ("INT", {
                    "default": 1024, "min": 64, "max": 8192, "step": 64,
                    "tooltip": "Longest side target in pixels. Aspect ratio is always preserved."
                }),
                "multiple_of": ("INT", {
                    "default": 8, "min": 1, "max": 128, "step": 1,
                    "tooltip": "Snap both dimensions to a multiple of this value. Use 8 for SD/Flux."
                }),
                "interpolation": (["lanczos", "bicubic", "bilinear", "nearest"], {
                    "default": "lanczos",
                    "tooltip": "Resampling method. Lanczos is sharpest for downscaling."
                }),

                # OUTPUT NAMING
                "suffix_resolution": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Append resolution to filename. E.g. image_1024.png"
                }),
                "suffix_custom": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Text added after the filename. E.g. photo → photo_headshot."
                }),

                # OUTPUT LOCATION
                "folder_resolution": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Append resolution to subfolder name. E.g. resized_1024"
                }),
                "folder_custom": ("STRING", {
                    "default": "resized",
                    "multiline": False,
                    "tooltip": "Subfolder name. Resolution is appended if 'Create resolution subfolder' is on."
                }),

                # OPTIONS
                "skip_if_exists": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Skip files that already exist in the output folder."
                }),
                "delimiter": ("STRING", {
                    "default": "_",
                    "multiline": False,
                    "tooltip": "Separator between filename and folder parts. E.g. _ or -"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "run"
    CATEGORY = "CraftKit"
    OUTPUT_NODE = True

    def run(self, input_folder, longest_side, multiple_of, interpolation,
            suffix_resolution, suffix_custom,
            folder_resolution, folder_custom,
            skip_if_exists, delimiter):

        # Resolve filename suffix
        suffix_raw = suffix_custom.strip()
        if suffix_resolution:
            if suffix_raw == "":
                suffix_raw = f"{delimiter}{longest_side}"
            else:
                suffix_raw = f"{suffix_raw}{delimiter}{longest_side}"

        # Ensure delimiter is prepended if there's a suffix
        if suffix_raw != "" and not suffix_raw.startswith(delimiter):
            filename_suffix = f"{delimiter}{suffix_raw}"
        else:
            filename_suffix = suffix_raw

        # Resolve output subfolder
        subfolder = folder_custom.strip()
        
        if subfolder == "":
            if folder_resolution:
                subfolder = str(longest_side)  # Only resolution
            else:
                subfolder = "resized"  # Fallback
        else:
            if folder_resolution:
                subfolder = f"{subfolder}{delimiter}{longest_side}"

        input_folder = input_folder.strip()
        if not input_folder:
            raise ValueError("[SmartBatchResize] No folder selected. Enter a path or use the Browse button.")
        if not os.path.isdir(input_folder):
            raise ValueError(f"[SmartBatchResize] Folder not found: {input_folder}")

        files = sorted([
            f for f in Path(input_folder).iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
        ])

        if not files:
            raise ValueError(f"[SmartBatchResize] No images found in: {input_folder}")

        out_dir = Path(input_folder) / subfolder
        out_dir.mkdir(parents=True, exist_ok=True)

        interp = INTERP_MAP[interpolation]
        images_out = []

        for f in files:
            out_name = f"{f.stem}{filename_suffix}{f.suffix.lower()}"
            out_path = out_dir / out_name

            if skip_if_exists and out_path.exists():
                print(f"[SmartBatchResize] Skipped (exists): {out_name}")
                continue

            img = PILImage.open(f).convert("RGB")
            w, h = img.size
            new_w, new_h = _calc_new_size(w, h, longest_side, multiple_of)

            img_resized = img.resize((new_w, new_h), interp)

            save_kwargs = {"quality": 95} if f.suffix.lower() in (".jpg", ".jpeg") else {}
            img_resized.save(out_path, **save_kwargs)

            print(f"[SmartBatchResize] {f.name} → {out_name} ({w}x{h} → {new_w}x{new_h})")

            arr = np.array(img_resized).astype("float32") / 255.0
            images_out.append(torch.from_numpy(arr).unsqueeze(0))

        if not images_out:
            raise ValueError("[SmartBatchResize] No images processed.")

        return (images_out, len(images_out))


NODE_CLASS_MAPPINGS        = {"SmartBatchResize": SmartBatchResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartBatchResize": "Smart Batch Resize 📁"}
