from PIL import Image as PILImage
import numpy as np
import torch


INTERP_MAP = {
    "lanczos":  PILImage.LANCZOS,
    "bicubic":  PILImage.BICUBIC,
    "bilinear": PILImage.BILINEAR,
    "nearest":  PILImage.NEAREST,
}


def _calc_new_size(w, h, longest_side, multiple_of, upscale_if_smaller):
    longest = max(w, h)
    if longest <= longest_side and not upscale_if_smaller:
        new_w, new_h = w, h
    else:
        scale = longest_side / longest
        new_w = int(w * scale)
        new_h = int(h * scale)
    if multiple_of > 1:
        new_w = max(multiple_of, round(new_w / multiple_of) * multiple_of)
        new_h = max(multiple_of, round(new_h / multiple_of) * multiple_of)
    return new_w, new_h


class SmartResize:
    """
    Resize IMAGE by longest side. Lanczos included. Multiple_of snapping.
    Works with single images and batches. IMAGE in → IMAGE out.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "longest_side": ("INT", {
                    "default": 1536, "min": 64, "max": 8192, "step": 8,
                    "tooltip": "Longest side target in pixels. Aspect ratio is always preserved."
                }),
                "multiple_of": ("INT", {
                    "default": 8, "min": 1, "max": 64, "step": 1,
                    "tooltip": "Snap both dimensions to a multiple of this value. Use 8 for SD/Flux."
                }),
                "interpolation": (["lanczos", "bicubic", "bilinear", "nearest"], {
                    "tooltip": "Resampling method. Lanczos is sharpest for downscaling."
                }),
                "upscale_if_smaller": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Upscale images that are smaller than the target longest side. Turn off to only ever downscale, never upscale."
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "run"
    CATEGORY = "CraftKit"

    def run(self, image, longest_side, multiple_of, interpolation, upscale_if_smaller):
        interp = INTERP_MAP[interpolation]
        results = []
        last_w, last_h = 0, 0

        for i in range(image.shape[0]):
            frame = image[i]  # [H, W, C]
            h, w = frame.shape[0], frame.shape[1]
            new_w, new_h = _calc_new_size(w, h, longest_side, multiple_of, upscale_if_smaller)

            if new_w == w and new_h == h:
                results.append(frame)
            else:
                arr = (frame.numpy() * 255).astype("uint8")
                pil = PILImage.fromarray(arr, mode="RGB")
                pil = pil.resize((new_w, new_h), interp)
                arr = np.array(pil).astype("float32") / 255.0
                results.append(torch.from_numpy(arr))

            last_w, last_h = new_w, new_h

        return (torch.stack(results, dim=0), last_w, last_h)


NODE_CLASS_MAPPINGS      = {"SmartResize": SmartResize}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartResize": "Smart Resize 📐"}
