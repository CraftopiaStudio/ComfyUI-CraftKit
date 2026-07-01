class SmartProfileSwitch:
    """
    CraftKit — Smart Profile Switch 🧩
    Maps an active index (1–4) to a label, width, and height.
    Designed to pair with Smart Prompt Controller's active_list output.
    """

    _DEFAULTS = [
        ("Headshots",  1024, 1024),
        ("Halfbody",    832, 1216),
        ("Fullbody",    768, 1344),
        ("Tall",        640, 1536),
    ]

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "index": ("INT", {
                "default": 1,
                "min": 1,
                "max": 4,
                "step": 1,
                "display": "number",
                "tooltip": "Active profile (1–4). Connect to active_list from Smart Prompt Controller.",
            }),
        }
        for i, (label, w, h) in enumerate(cls._DEFAULTS, 1):
            required[f"label_{i}"] = ("STRING", {
                "default": label,
                "tooltip": f"Label for profile {i}, used as filename suffix.",
            })
            required[f"width_{i}"]  = ("INT", {"default": w, "min": 64, "max": 8192, "step": 8})
            required[f"height_{i}"] = ("INT", {"default": h, "min": 64, "max": 8192, "step": 8})
        return {"required": required}

    RETURN_TYPES  = ("STRING", "INT", "INT")
    RETURN_NAMES  = ("label", "width", "height")
    FUNCTION      = "route"
    CATEGORY      = "CraftKit"
    OUTPUT_NODE   = True

    def route(self, index,
              label_1, width_1, height_1,
              label_2, width_2, height_2,
              label_3, width_3, height_3,
              label_4, width_4, height_4):
        slots = [
            (label_1, width_1, height_1),
            (label_2, width_2, height_2),
            (label_3, width_3, height_3),
            (label_4, width_4, height_4),
        ]
        idx = max(1, min(4, index)) - 1
        label, width, height = slots[idx]
        status = f"Slot {idx + 1}: {label}  |  {width} × {height}"
        return {"ui": {"text": [status]}, "result": (label, width, height)}


NODE_CLASS_MAPPINGS = {
    "SmartProfileSwitch": SmartProfileSwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartProfileSwitch": "Smart Profile Switch \U0001f9e9",
}
