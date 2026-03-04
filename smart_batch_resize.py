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


def _calc_new_size(w, h, max_pixels, multiple_of):
    longest = max(w, h)
    if longest <= max_pixels:
        new_w, new_h = w, h
    else:
        scale = max_pixels / longest
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
                "input_folder": ("STRING", {
                    "default": "D:/images/input",
                    "multiline": False,
                    "tooltip": "Folder containing images to resize."
                }),
                "max_pixels": ("INT", {
                    "default": 1536, "min": 64, "max": 8192, "step": 8,
                    "tooltip": "Longest side target in pixels. Aspect ratio is always preserved."
                }),
                "delimiter": ("STRING", {
                    "default": "_",
                    "multiline": False,
                    "tooltip": "Separator used when auto-naming. E.g. _ or -"
                }),
                "filename_suffix": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Appended to filename. When auto_suffix_from_pixels is on, pixel value is added after this."
                }),
                "auto_suffix_from_pixels": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Appends {delimiter}{max_pixels} to filename_suffix. E.g. dog_512 or _512 if suffix is empty."
                }),
                "output_subfolder": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Subfolder for output. Leave empty for 'resized'. When auto_folder_from_pixels is on, pixel value is added after this."
                }),
                "auto_folder_from_pixels": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Appends {delimiter}{max_pixels} to subfolder name. E.g. cat_512 or just 512 if subfolder is empty."
                }),
                "multiple_of": ("INT", {
                    "default": 8, "min": 1, "max": 64, "step": 1,
                    "tooltip": "Snap both dimensions to a multiple of this value. Use 8 for SD/Flux."
                }),
                "interpolation": (["lanczos", "bicubic", "bilinear", "nearest"],),
                "skip_if_exists": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Skip files that already exist in the output folder."
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "INT")
    RETURN_NAMES = ("images", "filenames", "output_paths", "count")
    OUTPUT_IS_LIST = (True, True, True, False)
    FUNCTION = "run"
    CATEGORY = "Craftopia"
    OUTPUT_NODE = True

    def run(self, input_folder, max_pixels, delimiter, filename_suffix,
            auto_suffix_from_pixels, output_subfolder, auto_folder_from_pixels,
            multiple_of, interpolation, skip_if_exists):

        # Resolve filename suffix
        if auto_suffix_from_pixels:
            filename_suffix = f"{filename_suffix}{delimiter}{max_pixels}"

        # Resolve output subfolder
        if output_subfolder.strip() == "":
            if auto_folder_from_pixels:
                output_subfolder = str(max_pixels)
            else:
                output_subfolder = "resized"
        else:
            if auto_folder_from_pixels:
                output_subfolder = f"{output_subfolder}{delimiter}{max_pixels}"

        input_folder = input_folder.strip()
        if not os.path.isdir(input_folder):
            raise ValueError(f"[SmartBatchResize] Folder not found: {input_folder}")

        files = sorted([
            f for f in Path(input_folder).iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
        ])

        if not files:
            raise ValueError(f"[SmartBatchResize] No images found in: {input_folder}")

        out_dir = Path(input_folder) / output_subfolder
        out_dir.mkdir(parents=True, exist_ok=True)

        interp = INTERP_MAP[interpolation]
        images_out, filenames_out, paths_out = [], [], []

        for f in files:
            out_name = f"{f.stem}{filename_suffix}{f.suffix.lower()}"
            out_path = out_dir / out_name

            if skip_if_exists and out_path.exists():
                print(f"[SmartBatchResize] Skipped (exists): {out_name}")
                continue

            img = PILImage.open(f).convert("RGB")
            w, h = img.size
            new_w, new_h = _calc_new_size(w, h, max_pixels, multiple_of)

            img_resized = img.resize((new_w, new_h), interp)

            save_kwargs = {"quality": 95} if f.suffix.lower() in (".jpg", ".jpeg") else {}
            img_resized.save(out_path, **save_kwargs)

            print(f"[SmartBatchResize] {f.name} → {out_name} ({w}x{h} → {new_w}x{new_h})")

            arr = np.array(img_resized).astype("float32") / 255.0
            images_out.append(torch.from_numpy(arr).unsqueeze(0))
            filenames_out.append(out_name)
            paths_out.append(str(out_path))

        if not images_out:
            raise ValueError("[SmartBatchResize] No images processed.")

        return (images_out, filenames_out, paths_out, len(images_out))


NODE_CLASS_MAPPINGS        = {"SmartBatchResize": SmartBatchResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartBatchResize": "Smart Batch Resize 📁"}
