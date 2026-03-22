class SmartBatchController:
    """
    Craftopia — Smart Batch Controller 🎛️
    Drives batch switching and prompt index from a single incrementing counter.
    Accepts up to 4 prompt lists as STRING inputs and counts lines automatically.
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
            },
            "optional": {
                "batch_1": ("STRING", {"forceInput": True}),
                "batch_2": ("STRING", {"forceInput": True}),
                "batch_3": ("STRING", {"forceInput": True}),
                "batch_4": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = ("select", "prompt_index", "total_all")
    FUNCTION = "control"
    CATEGORY = "Craftopia"
    OUTPUT_NODE = True

    def _count_lines(self, text):
        """Count non-empty lines in a prompt list string."""
        if not text:
            return 0
        return len([l for l in text.splitlines() if l.strip()])

    def control(self, counter, batch_1=None, batch_2=None, batch_3=None, batch_4=None):
        raw = [batch_1, batch_2, batch_3, batch_4]

        # Build active batch list: (original_index, line_count)
        active = []
        for i, text in enumerate(raw):
            count = self._count_lines(text)
            if count > 0:
                active.append((i, count))

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
                batch_index = i
                prompt_index = position - cumulative  # 0-based within batch
                break
            cumulative += t

        # UI label on node: "B2 — 3 / 7"
        batch_number = batch_index + 1
        batch_total = self._count_lines(raw[batch_index])
        prompt_display = prompt_index + 1  # 1-based for display
        label = f"B{batch_number}  —  {prompt_display} / {batch_total}  |  total: {total_all}"

        return {"ui": {"text": [label]}, "result": (batch_index, prompt_index, total_all)}


NODE_CLASS_MAPPINGS = {
    "SmartBatchController": SmartBatchController,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartBatchController": "Smart Batch Controller 🎛️",
}
