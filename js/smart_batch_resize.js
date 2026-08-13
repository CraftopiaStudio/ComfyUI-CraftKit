import { app } from "../../scripts/app.js";
import { createDividerWidget, createStatusWidget } from "./shared/canvas_widgets.mjs?v=3";
import { createPresetPickerWidget } from "./shared/preset_picker_widget.mjs?v=6";
import { setWidgetVisible } from "./shared/widget_visibility.mjs?v=2";

app.registerExtension({
    name: "Craftopia.SmartBatchResize",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartBatchResize") return;

        const folderWidget = node.widgets?.find(w => w.name === "input_folder");
        if (!folderWidget) return;

        const btn = node.addWidget("button", "📁 Browse folder", null, async () => {
            try {
                const res = await fetch("/craftkit/browse_folder", { method: "POST" });
                const data = await res.json();
                if (data.ok && data.path) {
                    folderWidget.value = data.path;
                    node.setDirtyCanvas(true);
                }
            } catch (e) {
                console.error("[SmartBatchResize] Browse failed:", e);
            }
        }, { serialize: false });

        btn.serialize = false;

        // Move Browse button to right after input_folder (index 1)
        const folderIdx = node.widgets.indexOf(folderWidget);
        const btnIdx = node.widgets.indexOf(btn);
        if (btnIdx !== folderIdx + 1) {
            node.widgets.splice(btnIdx, 1);
            node.widgets.splice(folderIdx + 1, 0, btn);
        }

        // Compact preset chips for longest_side.
        const longestSideWidget = node.widgets?.find(w => w.name === "longest_side");
        if (longestSideWidget) {
            const PRESETS = [512, 768, 1024, 1536];
            const presetWidget = createPresetPickerWidget(node, longestSideWidget, PRESETS);

            // Move preset row to right after longest_side
            const lsIdx = node.widgets.indexOf(longestSideWidget);
            const pwIdx = node.widgets.indexOf(presetWidget);
            if (pwIdx !== lsIdx + 1) {
                node.widgets.splice(pwIdx, 1);
                node.widgets.splice(lsIdx + 1, 0, presetWidget);
            }
        }

        // Section-header dividers — visual only, not serialized. Standalone node
        // with a lot of inputs, so grouping them keeps it scannable at a glance.
        const addSectionDivider = (beforeWidgetName, label) => {
            const target = node.widgets.find(w => w.name === beforeWidgetName);
            if (!target) return;
            const div = createDividerWidget(label);
            node.addCustomWidget(div);
            const targetIdx = node.widgets.indexOf(target);
            const divIdx = node.widgets.indexOf(div);
            node.widgets.splice(divIdx, 1);
            node.widgets.splice(targetIdx, 0, div);
        };
        addSectionDivider("longest_side", "RESIZE");
        addSectionDivider("prefix", "FILENAME");
        addSectionDivider("folder_resolution", "OUTPUT LOCATION");
        addSectionDivider("skip_if_exists", "OPTIONS");
        addSectionDivider("output_format", "OUTPUT FORMAT");

        // Override serialize so non-serializable JS widgets (Browse, presets, status,
        // run batch) are excluded from widgets_values in the saved workflow JSON.
        // Without this, LiteGraph saves null slots for these widgets which then shift
        // all Python widget values on load (configure runs before nodeCreated).
        // Invariant: Python widgets must stay in their original relative order in
        // this.widgets — JS widgets may be spliced in between, but never reorder
        // the Python ones, or the positional value assignment on load will silently
        // misalign.
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

        // Canvas-drawn status display
        const statusWidget = createStatusWidget("— RUN TO PROCESS —");
        node.addCustomWidget(statusWidget);

        // Run Batch button
        const runBtn = node.addWidget("button", "▶ Run Batch", null, () => {
            app.queuePrompt(0, 1).catch(e => console.error("[SmartBatchResize] Queue failed:", e));
        }, { serialize: false });
        runBtn.serialize = false;

        // Show/hide counter_start based on use_counter toggle
        const useCounterWidget = node.widgets?.find(w => w.name === "use_counter");
        const counterStartWidget = node.widgets?.find(w => w.name === "counter_start");
        if (useCounterWidget && counterStartWidget) {
            const updateCounterVisibility = () => {
                setWidgetVisible(node, counterStartWidget, useCounterWidget.value);
            };
            const origCallback = useCounterWidget.callback;
            useCounterWidget.callback = function (...args) {
                origCallback?.call(this, ...args);
                updateCounterVisibility();
            };
            const origOnConfigure = node.onConfigure;
            node.onConfigure = function (...args) {
                origOnConfigure?.call(this, ...args);
                updateCounterVisibility();
            };
            updateCounterVisibility();
        }

        // Hide any customtext widget already present (e.g. from a previously run workflow)
        const hideCustomText = () => {
            for (const w of node.widgets) {
                if (w.type === "customtext") setWidgetVisible(node, w, false);
            }
        };
        hideCustomText();

        // Intercept onExecuted to update status and hide the default customtext output
        const origOnExecuted = node.onExecuted;
        node.onExecuted = function (output) {
            origOnExecuted?.call(this, output);
            if (output?.text?.[0]) {
                statusWidget._text = output.text[0];
                hideCustomText();
                // setDirtyCanvas alone doesn't repaint Nodes 2.0's canvas bridge —
                // see the comment in preset_picker_widget.mjs.
                statusWidget.triggerDraw?.();
            }
            node.setDirtyCanvas(true);
        };

        // Force a full size/layout recompute now that every widget has been
        // added and repositioned. Without this, the preset-chip row's very
        // first paint can use a stale/undersized widgetWidth (from before the
        // node's final layout settled), rendering uneven or clipped chips
        // until the next unrelated redraw fixes it.
        node.setSize(node.computeSize());
        node.setDirtyCanvas(true, true);
    },
});
