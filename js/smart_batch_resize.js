import { app } from "../../scripts/app.js";
import { createDividerWidget, createStatusWidget } from "./shared/canvas_widgets.mjs?v=3";
import { createPresetPickerWidget } from "./shared/preset_picker_widget.mjs?v=6";
import { setWidgetVisible } from "./shared/widget_visibility.mjs?v=2";

// Approved folders live in ComfyUI's own settings store, so approving one is a
// plain settings write from the frontend: no CraftKit route, no helper process.
// The id must stay identical to SETTING_KEY in craftkit_folder_guard.py.
const SETTING_ID = "CraftKit.AllowedFolders";

function getSetting(id) {
    try {
        if (app.extensionManager?.setting?.get) return app.extensionManager.setting.get(id);
    } catch (e) { /* older frontend, fall through */ }
    try {
        return app.ui?.settings?.getSettingValue?.(id);
    } catch (e) {
        return undefined;
    }
}

async function setSetting(id, value) {
    if (app.extensionManager?.setting?.set) return await app.extensionManager.setting.set(id, value);
    return await app.ui.settings.setSettingValue(id, value);
}

// ';' is the separator (no path contains one); newlines are accepted for
// anyone who pastes a list into the settings field by hand. Mirrors
// _split_folders() in craftkit_folder_guard.py.
function splitFolders(value) {
    const parts = Array.isArray(value)
        ? value
        : String(value ?? "").replace(/\r/g, "\n").replace(/;/g, "\n").split("\n");
    return parts.map(cleanPath).filter(Boolean);
}

function cleanPath(p) {
    let s = String(p ?? "").trim().replace(/^["']+|["']+$/g, "").trim();
    // Strip a trailing separator, but never turn "D:/" into "D:".
    while (s.length > 3 && (s.endsWith("/") || s.endsWith("\\"))) s = s.slice(0, -1);
    return s;
}

app.registerExtension({
    name: "Craftopia.SmartBatchResize",

    settings: [
        {
            id: SETTING_ID,
            category: ["CraftKit", "Folders", "Approved folders"],
            name: "Approved folders",
            tooltip:
                "Folders Smart Batch Resize is allowed to read and write, separated by ';'. " +
                "Subfolders are included. Use the 'Approve folder' button on the node to add one. " +
                "ComfyUI's own input/output/temp folders always work without being listed here.",
            type: "text",
            defaultValue: "",
        },
    ],

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartBatchResize") return;

        const folderWidget = node.widgets?.find(w => w.name === "input_folder");
        if (!folderWidget) return;

        const APPROVE_LABEL = "✅ Approve folder";
        const btn = node.addWidget("button", APPROVE_LABEL, null, async () => {
            const flash = (label) => {
                btn.label = label;
                btn.name = label;
                node.setDirtyCanvas(true);
                setTimeout(() => {
                    btn.label = APPROVE_LABEL;
                    btn.name = APPROVE_LABEL;
                    node.setDirtyCanvas(true);
                }, 1800);
            };

            const folder = cleanPath(folderWidget.value);
            if (!folder) {
                flash("⚠ Paste a path first");
                return;
            }
            try {
                const existing = splitFolders(getSetting(SETTING_ID));
                const known = existing.some(f => f.toLowerCase() === folder.toLowerCase());
                if (known) {
                    flash("✔ Already approved");
                    return;
                }
                await setSetting(SETTING_ID, [...existing, folder].join(";"));
                flash("✔ Folder approved");
            } catch (e) {
                console.error("[SmartBatchResize] Could not approve folder:", e);
                flash("⚠ Approve failed (see console)");
            }
        }, { serialize: false });

        btn.serialize = false;

        // Move Approve button to right after input_folder (index 1)
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

        // Override serialize so non-serializable JS widgets (Approve, presets, status,
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
