import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartProfileSwitch",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartProfileSwitch") return;

        // Slot header dividers — visual only, not serialized
        const dividers = [];
        for (let i = 1; i <= 4; i++) {
            const div = node.addWidget("button", `_div_${i}`, null, () => {}, { serialize: false });
            div.serialize = false;
            const num = i;
            div.draw = function (ctx, node, widgetWidth, y, height) {
                const lx = 14;
                const label = `SLOT ${num}`;
                ctx.save();
                ctx.font = "bold 10px sans-serif";
                ctx.textBaseline = "middle";
                ctx.textAlign = "left";
                ctx.fillStyle = "#888";
                ctx.fillText(label, lx, y + height / 2);
                const lineX = lx + ctx.measureText(label).width + 8;
                ctx.beginPath();
                ctx.moveTo(lineX, y + height / 2);
                ctx.lineTo(widgetWidth - 14, y + height / 2);
                ctx.strokeStyle = "#333";
                ctx.lineWidth = 1;
                ctx.stroke();
                ctx.restore();
            };
            dividers.push(div);
        }

        // Status widget — shows active slot after execution
        const statusWidget = node.addWidget("button", "_sps_status", null, () => {}, { serialize: false });
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

        // Reorder: index, [div1, label_1, w_1, h_1], ..., [div4, label_4, w_4, h_4], status
        const indexWidget = node.widgets.find(w => w.name === "index");
        const slotWidgets = [];
        for (let i = 1; i <= 4; i++) {
            slotWidgets.push(
                dividers[i - 1],
                node.widgets.find(w => w.name === `label_${i}`),
                node.widgets.find(w => w.name === `width_${i}`),
                node.widgets.find(w => w.name === `height_${i}`),
            );
        }
        node.widgets = [indexWidget, ...slotWidgets, statusWidget];

        // Serialize override — keeps non-serializable widgets out of widgets_values
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

        // onExecuted — update status, hide default customtext textarea
        const origOnExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            origOnExecuted?.call(this, output);
            if (output?.text?.[0]) {
                statusWidget._text = output.text[0];
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
