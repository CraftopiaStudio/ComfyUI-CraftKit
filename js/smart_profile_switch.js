import { app } from "../../scripts/app.js";
import { createDividerWidget, createStatusWidget } from "./shared/canvas_widgets.mjs";

app.registerExtension({
    name: "Craftopia.SmartProfileSwitch",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartProfileSwitch") return;

        // Slot header dividers — visual only, not serialized
        const dividers = [];
        for (let i = 1; i <= 4; i++) {
            const div = createDividerWidget(`SLOT ${i}`);
            node.addCustomWidget(div);
            dividers.push(div);
        }

        // Status widget — shows active slot after execution
        const statusWidget = createStatusWidget("— RUN TO SEE RESULT —");
        node.addCustomWidget(statusWidget);

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
        // Guard against a lookup returning undefined (e.g. a widget converted to
        // an input) and never drop a widget we didn't explicitly place — append
        // anything unrecognized at the end instead of silently discarding it.
        const orderedWidgets = [indexWidget, ...slotWidgets, statusWidget].filter(Boolean);
        const orderedSet = new Set(orderedWidgets);
        const leftoverWidgets = node.widgets.filter(w => !orderedSet.has(w));
        node.widgets = [...orderedWidgets, ...leftoverWidgets];

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
