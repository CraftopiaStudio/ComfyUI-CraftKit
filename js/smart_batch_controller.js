import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartBatchController",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartBatchController") return;

        // Create status widget — empty name so no label shows
        const widget = node.addWidget("text", "", "", () => {});
        widget.serializeValue = () => undefined;

        // Listen for execution results
        const onExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            // Store current size before update
            const w = node.size[0];
            const h = node.size[1];

            onExecuted?.apply(this, arguments);

            if (output?.text?.[0]) {
                widget.value = output.text[0];
            }

            // Restore size so ComfyUI doesn't shrink the node
            node.size[0] = Math.max(w, node.size[0]);
            node.size[1] = Math.max(h, node.size[1]);
            node.setDirtyCanvas(true);
        };
    },
});
