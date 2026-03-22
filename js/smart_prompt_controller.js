import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartPromptController",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartPromptController") return;

        // Status widget — no visible label name
        const widget = node.addWidget("text", "", "", () => {});
        widget.serializeValue = () => undefined;

        const onExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            const w = node.size[0];
            const h = node.size[1];

            onExecuted?.apply(this, arguments);

            if (output?.text?.[0]) {
                widget.value = output.text[0];
            }

            // Preserve node size
            node.size[0] = Math.max(w, node.size[0]);
            node.size[1] = Math.max(h, node.size[1]);
            node.setDirtyCanvas(true);
        };
    },
});
