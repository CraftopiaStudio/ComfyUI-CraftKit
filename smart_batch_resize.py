import hashlib
import os
from pathlib import Path
from PIL import Image as PILImage, ImageOps
import numpy as np
import torch

try:
    # Only unavailable when this module is imported standalone outside a live
    # ComfyUI process (e.g. the test suite); ImportError is the only expected
    # failure here, so anything else is left to surface normally.
    from comfy.utils import ProgressBar
except ImportError:
    ProgressBar = None


INTERP_MAP = {
    "lanczos":  PILImage.LANCZOS,
    "bicubic":  PILImage.BICUBIC,
    "bilinear": PILImage.BILINEAR,
    "nearest":  PILImage.NEAREST,
}

# .avif/.heic decoding (and, with output_format=keep_source, re-encoding) depends on
# optional Pillow plugins that may not be installed; if unsupported, the per-file
# try/except below skips that file with a clear warning instead of crashing the batch.
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".tiff", ".tif", ".avif", ".heic"}


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


ALPHA_INCOMPATIBLE_EXT = {".jpg", ".jpeg", ".bmp"}


def _flatten_to_white(img):
    img = img.convert("RGBA")
    bg = PILImage.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    return bg


def _apply_alpha_mode(img, alpha_mode):
    has_alpha = img.mode in ("RGBA", "LA", "PA") or ("transparency" in img.info)
    if alpha_mode == "flatten":
        return _flatten_to_white(img) if has_alpha else img.convert("RGB")
    if alpha_mode == "keep":
        return img.convert("RGBA")
    # auto
    return img.convert("RGBA") if has_alpha else img.convert("RGB")


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
                    "tooltip": "Folder containing images to resize. Only files directly in this folder are scanned — subfolders are not included."
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
                    "tooltip": "Skip files that already exist in the output folder AND still match the current size settings. If longest_side/multiple_of/upscale_if_smaller changed since the file was made, it's reprocessed instead of skipped."
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

                # OUTPUT FORMAT
                "output_format": (["keep_source", "png", "webp", "jpg"], {
                    "default": "keep_source",
                    "tooltip": "File format for saved images. 'keep_source' preserves each file's original extension. jpg cannot store transparency."
                }),
                "alpha_mode": (["auto", "flatten", "keep"], {
                    "default": "auto",
                    "tooltip": "auto: preserve transparency only if the source has it. flatten: always composite onto white and output opaque RGB. keep: always output RGBA. jpg/bmp output always flattens regardless (those formats can't store alpha)."
                }),
                "quality": ("INT", {
                    "default": 95, "min": 1, "max": 100, "step": 1,
                    "tooltip": "Compression quality for jpg/webp output. Ignored for png (always lossless)."
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
            skip_if_exists, delimiter, preview_limit, output_format, alpha_mode, quality):

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
        pbar = ProgressBar(len(files)) if ProgressBar else None

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
            out_ext = f.suffix.lower() if output_format == "keep_source" else f".{output_format}"
            out_name = f"{stem}{out_ext}"
            out_path = out_dir / out_name
            keep_preview = keep_all or total_count < preview_limit

            try:
                can_skip = False
                if skip_if_exists and out_path.exists():
                    # Only honor the skip if the existing file's actual dimensions
                    # still match what the current settings would produce — otherwise
                    # a lowered longest_side/multiple_of would silently keep serving
                    # a stale size from a previous run.
                    try:
                        src_w, src_h = PILImage.open(f).size
                        expected_w, expected_h = _calc_new_size(src_w, src_h, longest_side, multiple_of, upscale_if_smaller)
                        can_skip = PILImage.open(out_path).size == (expected_w, expected_h)
                    except Exception:
                        can_skip = False

                if can_skip:
                    print(f"[SmartBatchResize] Skipped (exists, matches current settings): {out_name}")
                    skipped_count += 1
                    total_count += 1
                    counter_index += 1
                    if keep_preview:
                        existing = PILImage.open(out_path)
                        existing = _apply_alpha_mode(existing, alpha_mode)
                        arr = np.array(existing).astype("float32") / 255.0
                        images_out.append(torch.from_numpy(arr).unsqueeze(0))
                    continue
                elif skip_if_exists and out_path.exists():
                    print(f"[SmartBatchResize] Reprocessing (existing file doesn't match current settings): {out_name}")

                img = PILImage.open(f)
                img = ImageOps.exif_transpose(img)
                img = _apply_alpha_mode(img, alpha_mode)
                w, h = img.size
                new_w, new_h = _calc_new_size(w, h, longest_side, multiple_of, upscale_if_smaller)

                img_resized = img.resize((new_w, new_h), interp)

                if img_resized.mode == "RGBA" and out_ext in ALPHA_INCOMPATIBLE_EXT:
                    img_resized = _flatten_to_white(img_resized)
                    print(f"[SmartBatchResize] {f.name}: flattened transparency for {out_ext} (format doesn't support alpha)")

                save_kwargs = {"quality": quality} if out_ext in (".jpg", ".jpeg", ".webp") else {}
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
            finally:
                if pbar:
                    pbar.update(1)

        if skipped_count:
            summary = f"✓ {processed_count} new, {skipped_count} already existed → {subfolder}/"
        else:
            summary = f"✓ {processed_count} images saved → {subfolder}/"
        if failed_count:
            summary += f" ({failed_count} failed)"
        return {"ui": {"text": [summary]}, "result": (images_out, total_count)}


NODE_CLASS_MAPPINGS        = {"SmartBatchResize": SmartBatchResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartBatchResize": "Smart Batch Resize 📁"}
