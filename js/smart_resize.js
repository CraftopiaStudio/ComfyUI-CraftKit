import { app } from "../../scripts/app.js";
import { createPresetPickerWidget } from "./shared/preset_picker_widget.mjs?v=2";
import { isVueNodes } from "./shared/nodes2.mjs?v=2";

app.registerExtension({
    name: "Craftopia.SmartResize",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartResize") return;

        const longestSideWidget = node.widgets?.find(w => w.name === "longest_side");
        if (!longestSideWidget) return;

        const PRESETS = [512, 768, 1024, 1536];
        const presetWidget = createPresetPickerWidget(node, longestSideWidget, PRESETS);

        // Override serialize to exclude the non-serializable preset widget from
        // widgets_values — same drift fix as SmartBatchResize (see that file for details).
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

        // Move preset row to right after longest_side — classic mode only.
        // Under Nodes 2.0, splicing the DOM widget into the middle of
        // node.widgets after configure() has already run desyncs Vue's
        // value-to-row binding for every widget after it (see the comment in
        // smart_batch_resize.js for the full explanation).
        if (!isVueNodes()) {
            const lsIdx = node.widgets.indexOf(longestSideWidget);
            const pwIdx = node.widgets.indexOf(presetWidget);
            if (pwIdx !== lsIdx + 1) {
                node.widgets.splice(pwIdx, 1);
                node.widgets.splice(lsIdx + 1, 0, presetWidget);
            }
        }

        // Force a full size/layout recompute now that the preset widget has
        // been added and repositioned — see the comment in
        // smart_batch_resize.js for why this is needed.
        node.setSize(node.computeSize());
        node.setDirtyCanvas(true, true);
    },
});
