# ComfyUI-SmartResize

Smart image resize nodes for ComfyUI — batch processing, LoRA prep & SeedVR support.

All nodes appear under the **Craftopia** category in the node menu.

---

## Nodes

### 📐 Smart Resize
Resize any image (or batch) so the **longest side** equals `max_pixels`, with aspect ratio preserved.

Use this as a **pipeline node** — IMAGE in, IMAGE out. No files are saved to disk.

**Typical usecases:**
- Downscale a SeedVR (or other upscaler) result back to your target training size — the upscaler adds fine detail, Smart Resize brings it to the right dimensions for LoRA training
- Any workflow step that needs a clean resize before the next node
- Normalize mixed-resolution batches to a consistent size

| Input | Type | Default | Description |
|---|---|---|---|
| image | IMAGE | — | Single image or batch |
| max_pixels | INT | 1536 | Target size for longest side |
| multiple_of | INT | 8 | Snap dimensions to this multiple (8 = SD/Flux compatible) |
| interpolation | ENUM | lanczos | lanczos / bicubic / bilinear / nearest |
| upscale_if_smaller | BOOLEAN | false | Also upscale images already smaller than max_pixels |

**Outputs:** `image`, `width`, `height`

---

### 📁 Smart Batch Resize
Load **all images from a folder**, resize each one by longest side, and save with the original filename + a suffix into a subfolder. Original filenames are always preserved.

Use this for **bulk preprocessing** — e.g. preparing a LoRA dataset from a folder of high-res images.

| Input | Type | Default | Description |
|---|---|---|---|
| input_folder | STRING | D:/images/input | Source folder path |
| max_pixels | INT | 1536 | Target size for longest side |
| filename_suffix | STRING | _Small | Appended to each output filename before the extension |
| output_subfolder | STRING | resized | Subfolder created inside input_folder |
| multiple_of | INT | 8 | Snap dimensions to this multiple |
| interpolation | ENUM | lanczos | lanczos / bicubic / bilinear / nearest |
| skip_if_exists | BOOLEAN | false | Skip files that already exist in output |

**Outputs:** `images` (list), `filenames` (list), `output_paths` (list), `count`

---

### 📏 Smart Size Multiplier
Multiply image dimensions by a factor and output the results as integers.

SeedVR takes a single `resolution` INT (the longest side) — not a width and height separately. Standard math nodes give you a FLOAT or require multiple steps to get there. This node does it cleanly in one step: give it your image and a multiplier, and it outputs `width`, `height`, and `resolution` (longest side) ready to connect directly to SeedVR's `max_resolution` input.

Also useful for LoRA dataset prep — using mixed resolutions in your training set generally produces better results than training on a single fixed size. Smart Size Multiplier makes it easy to dynamically calculate the right target size per image rather than hardcoding a value.

| Input | Type | Default | Description |
|---|---|---|---|
| image | IMAGE | — | Source image |
| multiplier | FLOAT | 2.0 | Multiply width and height by this factor |
| multiple_of | INT | 8 | Snap dimensions to this multiple |

**Outputs:** `width`, `height`, `resolution` (longest side as INT → directly into SeedVR)

---

## Why these nodes?

- ComfyUI's built-in `Resize Images by Longer Edge` [BETA] has no Lanczos and no `multiple_of` snapping
- `JWImageResizeByLongerSide` (comfyui-various) has no Lanczos in the official release
- No existing node combines batch folder loading + longest-side resize + original filename preservation
- No existing node outputs a ready-to-use `resolution` INT for SeedVR

---

## Installation

**ComfyUI Manager:** search for `ComfyUI-SmartResize` and install.

**Manual:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/CraftopiaStudio/ComfyUI-SmartResize
```
Restart ComfyUI. All nodes appear under **Craftopia** in the node menu:

- `Craftopia` → **Smart Resize 📐**
- `Craftopia` → **Smart Batch Resize 📁**
- `Craftopia` → **Smart Size Multiplier 📏**

---

## Requirements
Pillow, NumPy, PyTorch — all included with ComfyUI. No extra dependencies.
