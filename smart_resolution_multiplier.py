class SmartResolutionMultiplier:
    """
    Multiplies image dimensions by a factor.
    Outputs width, height, and resolution (longest side) as INT.
    Use resolution output directly with SeedVR max_resolution.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Source image. Its current width/height are read directly — no separate Get Image Size node needed."
                }),
                "multiplier": ("FLOAT", {
                    "default": 2.0,
                    "min": 0.1,
                    "max": 16.0,
                    "step": 0.1,
                    "round": 0.01,
                    "tooltip": "Multiply width and height by this factor. E.g. 2.0 = double resolution."
                }),
                "multiple_of": ("INT", {
                    "default": 8,
                    "min": 1,
                    "max": 64,
                    "step": 1,
                    "tooltip": "Snap output dimensions to a multiple of this value."
                }),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = ("width", "height", "resolution")
    FUNCTION = "run"
    CATEGORY = "CraftKit"

    def run(self, image, multiplier, multiple_of):
        h, w = image.shape[1], image.shape[2]

        new_w = int(round(w * multiplier))
        new_h = int(round(h * multiplier))

        if multiple_of > 1:
            new_w = max(multiple_of, round(new_w / multiple_of) * multiple_of)
            new_h = max(multiple_of, round(new_h / multiple_of) * multiple_of)

        resolution = max(new_w, new_h)
        print(f"[SmartResolutionMultiplier] {w}x{h} x {multiplier} -> {new_w}x{new_h} (resolution: {resolution})")
        return (new_w, new_h, resolution)


NODE_CLASS_MAPPINGS        = {"SmartResolutionMultiplier": SmartResolutionMultiplier}
NODE_DISPLAY_NAME_MAPPINGS = {"SmartResolutionMultiplier": "Smart Resolution Multiplier 📏"}
