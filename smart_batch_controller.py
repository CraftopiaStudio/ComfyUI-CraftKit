class SmartBatchController:
    """
    Craftopia — Smart Batch Controller 🎛️
    Drives batch switching and prompt index from a single incrementing counter.
    Replaces SELECT BATCH + WELKE REGEL + Math Expression + Math Int.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "counter": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 99999,
                    "step": 1,
                    "display": "number",
                    "control_after_generate": "increment",
                }),
                "batch_1_total": ("INT", {"default": 5,  "min": 0, "max": 999, "step": 1, "display": "number"}),
                "batch_2_total": ("INT", {"default": 8,  "min": 0, "max": 999, "step": 1, "display": "number"}),
                "batch_3_total": ("INT", {"default": 0,  "min": 0, "max": 999, "step": 1, "display": "number"}),
                "batch_4_total": ("INT", {"default": 0,  "min": 0, "max": 999, "step": 1, "display": "number"}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = ("select", "prompt_index", "total_all")
    FUNCTION = "control"
    CATEGORY = "Craftopia"
    OUTPUT_NODE = True

    def control(self, counter, batch_1_total, batch_2_total, batch_3_total, batch_4_total):
        totals = [batch_1_total, batch_2_total, batch_3_total, batch_4_total]

        # Filter out empty batches
        active = [(i, t) for i, t in enumerate(totals) if t > 0]
        total_all = sum(t for _, t in active)

        if total_all == 0:
            return {"ui": {"text": ["no prompts"]}, "result": (0, 0, 0)}

        # Wrap counter within total_all (1-based counter → 0-based position)
        position = (counter - 1) % total_all

        # Find which batch and which prompt within that batch
        cumulative = 0
        batch_index = 0
        prompt_index = 0

        for i, t in active:
            if position < cumulative + t:
                batch_index = i          # 0-based → Switch select
                prompt_index = position - cumulative  # 0-based within batch
                break
            cumulative += t

        # UI label: "B2 — 3 / 8"
        batch_number = batch_index + 1
        batch_total = totals[batch_index]
        prompt_display = prompt_index + 1  # 1-based for display
        label = f"B{batch_number}  —  {prompt_display} / {batch_total}"

        # prompt_index +1 because Pose node select is 0-based but we subtract 1 via Math Int
        # Actually return 0-based so user can connect directly to Pose select
        return {"ui": {"text": [label]}, "result": (batch_index, prompt_index, total_all)}


NODE_CLASS_MAPPINGS = {
    "SmartBatchController": SmartBatchController,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartBatchController": "Smart Batch Controller 🎛️",
}
