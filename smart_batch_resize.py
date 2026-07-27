import hashlib
import os
from pathlib import Path
from PIL import Image as PILImage, ImageOps
import numpy as np
import torch


INTERP_MAP = {
    "lanczos":  PILImage.LANCZOS,
    "bicubic":  PILImage.BICUBIC,
    "bilinear": PILImage.BILINEAR,
    "nearest":  PILImage.NEAREST,
}

SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def _calc_new_size(w, h, longest_side, multiple_of, upscale_if_smaller):
    longest = max(w, h)
    scaled = longest > longest_side or upscale_if_smaller
    if not scaled:
        new_w, new_h = w, h
    else:
        scale = longest_side / longest
        new_w = round(w * scale)
        new_h = round(h * scale)
    if multiple_of > 1:
        raw_w, raw_h = new_w, new_h
        new_w = max(multiple_of, round(raw_w / multiple_of) * multiple_of)
        new_h = max(multiple_of, round(raw_h / multiple_of) * multiple_of)
        if scaled and max(new_w, new_h) > longest_side:
            # Rounding to the nearest multiple pushed the longest side past the
            # target — floor that side to the multiple instead and rescale the
            # other side to match, so the requested cap is always honored.
            if raw_w >= raw_h:
                floored = max(multiple_of, (raw_w // multiple_of) * multiple_of)
                other_scale = floored / raw_w
                new_w = floored
                new_h = max(multiple_of, round((raw_h * other_scale) / multiple_of) * multiple_of)
            else:
                floored = max(multiple_of, (raw_h // multiple_of) * multiple_of)
                other_scale = floored / raw_h
                new_h = floored
                new_w = max(multiple_of, round((raw_w * other_scale) / multiple_of) * multiple_of)
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
                "upscale_if_smaller": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Upscale images that are smaller than the target longest side. Turn off to only ever downscale, never upscale."
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
                "preview_limit": ("INT", {
                    "default": 32, "min": 0, "max": 10000, "step": 1,
                    "tooltip": "Max images to keep in memory for the preview output. All files are still processed and saved to disk; this only limits what's returned/previewed. 0 = no limit."
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT")
    RETURN_NAMES = ("images", "count")
    OUTPUT_IS_LIST = (True, False)
    FUNCTION = "run"
    CATEGORY = "CraftKit"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, input_folder, **kwargs):
        # Folder contents aren't a widget input, so ComfyUI can't see when files
        # are added/removed on its own. Hash the listing so unrelated graph runs
        # can still hit the cache, while an actual folder change invalidates it.
        folder = input_folder.strip()
        if not folder or not os.path.isdir(folder):
            return ""
        try:
            files = sorted(
                (f.name, f.stat().st_size, f.stat().st_mtime)
                for f in Path(folder).iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
            )
        except OSError:
            return float("nan")
        return hashlib.sha256(repr(files).encode()).hexdigest()

    def run(self, input_folder, longest_side, multiple_of, interpolation, upscale_if_smaller,
            prefix, use_original_name, use_counter, counter_start, suffix_resolution,
            folder_resolution, folder_custom,
            skip_if_exists, delimiter, preview_limit):

        # Resolve output subfolder
        subfolder = folder_custom.strip()
        if subfolder != "" and (
            os.path.isabs(subfolder)
            or Path(subfolder).drive
            or ".." in Path(subfolder).parts
            or os.sep in subfolder
            or (os.altsep and os.altsep in subfolder)
        ):
            raise ValueError(f"[SmartBatchResize] Invalid subfolder name: {folder_custom!r}. Use a plain folder name, not a path.")
        if subfolder == "":
            subfolder = str(longest_side) if folder_resolution else "resized"
        elif folder_resolution:
            subfolder = f"{subfolder}{delimiter}{longest_side}"

        if not use_original_name and not use_counter:
            raise ValueError("[SmartBatchResize] Enable 'use_original_name' or 'use_counter' — otherwise all files would collapse to the same output name.")

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
        if out_dir.resolve() == Path(input_folder).resolve():
            raise ValueError("[SmartBatchResize] Output folder resolves to the input folder — refusing to overwrite originals.")
        out_dir.mkdir(parents=True, exist_ok=True)

        interp = INTERP_MAP[interpolation]
        images_out = []
        counter_index = 0
        skipped_count = 0
        processed_count = 0
        failed_count = 0
        total_count = 0
        keep_all = preview_limit == 0

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
            keep_preview = keep_all or total_count < preview_limit

            try:
                if skip_if_exists and out_path.exists():
                    print(f"[SmartBatchResize] Skipped (exists): {out_name}")
                    skipped_count += 1
                    total_count += 1
                    counter_index += 1
                    if keep_preview:
                        existing = PILImage.open(out_path).convert("RGB")
                        arr = np.array(existing).astype("float32") / 255.0
                        images_out.append(torch.from_numpy(arr).unsqueeze(0))
                    continue

                img = PILImage.open(f)
                img = ImageOps.exif_transpose(img)
                img = img.convert("RGB")
                w, h = img.size
                new_w, new_h = _calc_new_size(w, h, longest_side, multiple_of, upscale_if_smaller)

                img_resized = img.resize((new_w, new_h), interp)

                save_kwargs = {"quality": 95} if f.suffix.lower() in (".jpg", ".jpeg") else {}
                img_resized.save(out_path, **save_kwargs)

                print(f"[SmartBatchResize] {f.name} → {out_name} ({w}x{h} → {new_w}x{new_h})")

                processed_count += 1
                total_count += 1
                counter_index += 1
                if keep_preview:
                    arr = np.array(img_resized).astype("float32") / 255.0
                    images_out.append(torch.from_numpy(arr).unsqueeze(0))
            except Exception as e:
                print(f"[SmartBatchResize] Failed: {f.name}: {e}")
                failed_count += 1

        if skipped_count:
            summary = f"✓ {processed_count} new, {skipped_count} already existed → {subfolder}/"
        else:
            summary = f"✓ {processed_count} images saved → {subfolder}/"
        if failed_count:
            summary += f" ({failed_count} failed)"
        return {"ui": {"text": [summary]}, "result": (images_out, total_count)}


NODE_CLASS_MAPPINGS        = {"SmartBatchResize": SmartBatchResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartBatchResize": "Smart Batch Resize 📁"}
