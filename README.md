# ComfyUI-SmartResize

Two focused resize nodes for ComfyUI — both with **Lanczos** interpolation and **multiple_of** snapping.

---

## Nodes

### 📐 Smart Resize
Resize any image (or batch) so the **longest side** equals `max_pixels`, with aspect ratio preserved.

Use this as a **pipeline node** — IMAGE in, IMAGE out. Perfect for downscaling SeedVR upscales before LoRA training, or any workflow step where you need a clean downscale without saving to disk.

**Inputs:**
| Input | Type | Default | Description |
|---|---|---|---|
| image | IMAGE | — | Single image or batch |
| max_pixels | INT | 1536 | Target size for longest side |
| multiple_of | INT | 8 | Snap dimensions to this multiple (8 = SD/Flux compatible) |
| interpolation | ENUM | lanczos | lanczos / bicubic / bilinear / nearest |
| upscale_if_smaller | BOOLEAN | false | Also upscale images already smaller than max_pixels |

**Outputs:** `IMAGE`, `width`, `height`

---

### 📁 Batch Resize & Save
Load **all images from a folder**, resize each one (longest side), and save them with the original filename + a suffix into a subfolder.

Use this for **bulk preprocessing** — e.g. preparing a LoRA dataset from a folder of high-res images.

**Inputs:**
| Input | Type | Default | Description |
|---|---|---|---|
| input_folder | STRING | D:/images/mijnmap | Source folder path |
| max_pixels | INT | 1536 | Target size for longest side |
| filename_suffix | STRING | _Small | Appended to each output filename |
| output_subfolder | STRING | resized | Subfolder created inside input_folder |
| multiple_of | INT | 8 | Snap dimensions to this multiple |
| interpolation | ENUM | lanczos | lanczos / nearest / bilinear / bicubic |
| skip_if_exists | BOOLEAN | false | Skip files that already exist in output |

**Outputs:** `images` (list), `filenames` (list), `output_paths` (list), `count`

---

## Why these nodes?

Existing nodes like `JWImageResizeByLongerSide` lack **Lanczos** interpolation (the best choice for downscaling). Other batch nodes don't preserve original filenames or offer `multiple_of` snapping.

These nodes fill that gap with a minimal, focused feature set.

---

## Installation

**Option A — ComfyUI Manager:**
Search for `ComfyUI-SmartResize` and install.

**Option B — Manual:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/YOUR_USERNAME/ComfyUI-SmartResize
```
Restart ComfyUI. Nodes appear under:
- `image/transform` → **Smart Resize 📐**
- `image/batch` → **Batch Resize & Save 📁**

---

## Requirements
- ComfyUI
- Pillow (included with ComfyUI)
- PyTorch (included with ComfyUI)
