import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartPromptController",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartPromptController") return;

        // Canvas-drawn result display — clearly an output, not an input field
        const statusWidget = node.addWidget("button", "_spc_result", null, () => {}, { serialize: false });
        statusWidget.serialize = false;
        statusWidget._text = "";

        statusWidget.draw = function (ctx, node, widgetWidth, y, height) {
            const margin = 14;
            const innerW = widgetWidth - margin * 2;

            ctx.save();

            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(margin, y + 2, innerW, height - 4, 4);
            else ctx.rect(margin, y + 2, innerW, height - 4);
            ctx.fillStyle = "#111";
            ctx.fill();
            ctx.strokeStyle = this._text ? "#3a3a3a" : "#222";
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = this._text ? "#f28f41" : "#666";
            ctx.fillText(
                this._text || "— RUN TO SEE RESULT —",
                widgetWidth / 2,
                y + height / 2
            );

            ctx.restore();
        };

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
