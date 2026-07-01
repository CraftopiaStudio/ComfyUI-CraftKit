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


def _build_stem(original_stem, prefix, use_original_name, use_counter, counter_index, counter_start, suffix_resolution, longest_side, delimiter):
    parts = []

    if prefix:
        parts.append(prefix)

    if use_original_name:
        parts.append(original_stem)

    if use_counter:
        number = counter_start + counter_index
        parts.append(f"{number:03d}")

    if suffix_resolution:
        parts.append(str(longest_side))

    if not parts:
        parts.append(original_stem)

    return delimiter.join(parts)


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
                "prefix": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Label prepended to filename. E.g. 'headshot' → headshot_photo_001_1024.jpg"
                }),
                "use_original_name": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Include the original filename in the output name."
                }),
                "use_counter": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Add a sequential 3-digit counter to each filename (001, 002, ...)."
                }),
                "counter_start": ("INT", {
                    "default": 1, "min": 0, "max": 99999, "step": 1,
                    "tooltip": "Starting number for the counter. Useful when processing multiple batches."
                }),
                "suffix_resolution": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Append resolution to filename. E.g. photo_1024.png"
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
                    "tooltip": "Separator between filename parts. E.g. _ or -"
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
            prefix, use_original_name, use_counter, counter_start, suffix_resolution,
            folder_resolution, folder_custom,
            skip_if_exists, delimiter):

        # Resolve output subfolder
        subfolder = folder_custom.strip()
        if subfolder == "":
            subfolder = str(longest_side) if folder_resolution else "resized"
        elif folder_resolution:
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
        counter_index = 0

        for f in files:
            stem = _build_stem(
                original_stem=f.stem,
                prefix=prefix.strip(),
                use_original_name=use_original_name,
                use_counter=use_counter,
                counter_index=counter_index,
                counter_start=counter_start,
                suffix_resolution=suffix_resolution,
                longest_side=longest_side,
                delimiter=delimiter,
            )
            out_name = f"{stem}{f.suffix.lower()}"
            out_path = out_dir / out_name

            if skip_if_exists and out_path.exists():
                print(f"[SmartBatchResize] Skipped (exists): {out_name}")
                counter_index += 1
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
            counter_index += 1

        if not images_out:
            raise ValueError("[SmartBatchResize] No images processed.")

        summary = f"✓ {len(images_out)} images saved → {subfolder}/"
        return {"ui": {"text": [summary]}, "result": (images_out, len(images_out))}


NODE_CLASS_MAPPINGS        = {"SmartBatchResize": SmartBatchResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartBatchResize": "Smart Batch Resize 📁"}
