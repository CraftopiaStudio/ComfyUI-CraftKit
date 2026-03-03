import math
from PIL import Image as PILImage
import numpy as np
import torch


class SmartResize:
    """
    Resize images so the longest side equals max_pixels.
    Supports lanczos interpolation and multiple_of snapping.
    Works with single images and batches.
    """

    INTERP_MAP = {
        "lanczos":  PILImage.LANCZOS,
        "bicubic":  PILImage.BICUBIC,
        "bilinear": PILImage.BILINEAR,
        "nearest":  PILImage.NEAREST,
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_pixels": ("INT", {
                    "default": 1536,
                    "min": 64,
                    "max": 8192,
                    "step": 8,
                    "tooltip": "Longest side will be resized to this value (aspect ratio preserved)"
                }),
                "multiple_of": ("INT", {
                    "default": 8,
                    "min": 1,
                    "max": 64,
                    "step": 1,
                    "tooltip": "Round dimensions to a multiple of this value (8 = SD compatible)"
                }),
                "interpolation": (["lanczos", "bicubic", "bilinear", "nearest"], {
                    "default": "lanczos"
                }),
                "upscale_if_smaller": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Also upscale images that are already smaller than max_pixels"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "run"
    CATEGORY = "image/transform"

    def _resize_one(self, img_tensor, max_pixels, multiple_of, interp, upscale_if_smaller):
        """Resize a single [H, W, C] tensor."""
        h, w = img_tensor.shape[0], img_tensor.shape[1]
        longest = max(w, h)

        # Skip if already small enough and upscale disabled
        if longest <= max_pixels and not upscale_if_smaller:
            # Still snap to multiple_of
            new_w = max(multiple_of, round(w / multiple_of) * multiple_of) if multiple_of > 1 else w
            new_h = max(multiple_of, round(h / multiple_of) * multiple_of) if multiple_of > 1 else h
            if new_w == w and new_h == h:
                return img_tensor, w, h
        else:
            scale = max_pixels / longest
            new_w = int(w * scale)
            new_h = int(h * scale)

        # Snap to multiple_of
        if multiple_of > 1:
            new_w = max(multiple_of, round(new_w / multiple_of) * multiple_of)
            new_h = max(multiple_of, round(new_h / multiple_of) * multiple_of)

        # Convert tensor [H, W, C] float32 → PIL → resize → tensor
        arr = (img_tensor.numpy() * 255).astype(np.uint8)
        pil = PILImage.fromarray(arr, mode="RGB")
        pil_resized = pil.resize((new_w, new_h), interp)
        arr_resized = np.array(pil_resized).astype(np.float32) / 255.0
        return torch.from_numpy(arr_resized), new_w, new_h

    def run(self, image, max_pixels, multiple_of, interpolation, upscale_if_smaller):
        # image shape: [B, H, W, C]
        interp = self.INTERP_MAP[interpolation]
        results = []
        last_w, last_h = 0, 0

        for i in range(image.shape[0]):
            resized, w, h = self._resize_one(
                image[i], max_pixels, multiple_of, interp, upscale_if_smaller
            )
            results.append(resized)
            last_w, last_h = w, h

        # Stack back to [B, H, W, C] — all frames must be same size
        # (they will be if all input frames are same size, which is the ComfyUI norm)
        output = torch.stack(results, dim=0)
        return (output, last_w, last_h)


NODE_CLASS_MAPPINGS = {
    "SmartResize": SmartResize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartResize": "Smart Resize 📐",
}
