class SmartPromptController:
    """
    Craftopia — Smart Prompt Controller 🎛️
    Cycles through up to 4 prompt lists using a single incrementing counter.
    Counts lines automatically and outputs the selected prompt + list number.
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
                "prompt_list_1": ("STRING", {"forceInput": True}),
                "prompt_list_2": ("STRING", {"forceInput": True}),
                "prompt_list_3": ("STRING", {"forceInput": True}),
                "prompt_list_4": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("prompt", "list_index")
    FUNCTION = "control"
    CATEGORY = "CraftKit"
    OUTPUT_NODE = True

    def _get_lines(self, text):
        """Return list of non-empty lines from a text block."""
        if not text:
            return []
        if isinstance(text, list):
            text = text[0] if text else ""
        return [l for l in str(text).splitlines() if l.strip()]

    def control(self, counter, prompt_list_1="", prompt_list_2="",
                prompt_list_3="", prompt_list_4=""):
        raw = [prompt_list_1, prompt_list_2, prompt_list_3, prompt_list_4]

        # Collect active lists: (list_index, [lines])
        active = []
        for i, text in enumerate(raw):
            lines = self._get_lines(text)
            if lines:
                active.append((i, lines))

        total_all = sum(len(lines) for _, lines in active)

        if total_all == 0:
            return {"ui": {"text": ["no prompts connected"]},
                    "result": ("", 0)}

        # Map counter position to list + line
        position = (counter - 1) % total_all

        cumulative = 0
        selected_list_index = 0
        selected_line_index = 0
        selected_prompt = ""

        for list_idx, lines in active:
            if position < cumulative + len(lines):
                selected_list_index = list_idx
                selected_line_index = position - cumulative
                selected_prompt = lines[selected_line_index]
                break
            cumulative += len(lines)

        # Label: "List 1 — 4/5 | total: 8"
        list_number = selected_list_index + 1
        list_total = len(self._get_lines(raw[selected_list_index]))
        prompt_display = selected_line_index + 1
        label = f"List {list_number} \u2014 {prompt_display}/{list_total} | total: {total_all}"

        return {
            "ui": {"text": [label]},
            "result": (
                selected_prompt,
                list_number,
            )
        }


NODE_CLASS_MAPPINGS = {
    "SmartPromptController": SmartPromptController,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SmartPromptController": "Smart Prompt Controller \ud83c\udf9b\ufe0f",
}
