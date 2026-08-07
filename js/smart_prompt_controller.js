import { app } from "../../scripts/app.js";
import { createStatusWidget } from "./shared/canvas_widgets.mjs";

app.registerExtension({
    name: "Craftopia.SmartPromptController",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartPromptController") return;

        // Canvas-drawn result display — clearly an output, not an input field
        const statusWidget = createStatusWidget("— RUN TO SEE RESULT —");
        node.addCustomWidget(statusWidget);

        // Override serialize so non-serializable JS widgets (the result display)
        // are excluded from widgets_values in the saved workflow JSON. Without this,
        // LiteGraph saves null slots for these widgets which then shift all Python
        // widget values on load (configure runs before nodeCreated).
        const origSerialize = node.serialize;
        node.serialize = function () {
            const data = origSerialize.call(this);
            if (data.widgets_values) {
                data.widgets_values = this.widgets
                    .filter(w => w.serialize !== false && w.options?.serialize !== false)
                    .map(w => w.value);
            }
            return data;
        };

        // Intercept onExecuted: update our widget, hide ComfyUI's default textarea
        const origOnExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            origOnExecuted?.call(this, output);

            if (output?.text?.[0]) {
                statusWidget._text = output.text[0];

                // Collapse the default customtext widget ComfyUI adds for ui.text
                for (const w of node.widgets) {
                    if (w !== statusWidget && w.type === "customtext") {
                        w.computeSize = () => [0, -4];
                    }
                }
            }

            node.setDirtyCanvas(true);
        };
    },
});
