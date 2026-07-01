import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartBatchResize",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartBatchResize") return;

        const folderWidget = node.widgets?.find(w => w.name === "input_folder");
        if (!folderWidget) return;

        const btn = node.addWidget("button", "📁 Browse folder", null, async () => {
            try {
                const res = await fetch("/craftkit/browse_folder");
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

        // Compact preset chips for longest_side. Start from a REAL button widget
        // (so all of ComfyUI's layout/computeSize/sizing integration is correct)
        // and only override its draw + mouse. A bare custom widget with our own
        // computeSize forced the node width and broke the layout on click.
        const longestSideWidget = node.widgets?.find(w => w.name === "longest_side");
        if (longestSideWidget) {
            const PRESETS = [512, 768, 1024, 1536];

            // Per-chip click handled in the button callback (buttons route clicks
            // to their callback, not to .mouse). We read the pointer position from
            // the canvas at click time and match it against the drawn chip rects.
            const presetWidget = node.addWidget("button", "size_presets", null, (value, canvas, node) => {
                const gm = (canvas || app.canvas)?.graph_mouse;
                if (!gm) return;
                const lx = gm[0] - node.pos[0];
                const ly = gm[1] - node.pos[1];
                for (const r of presetWidget._rects) {
                    if (lx >= r.x1 && lx <= r.x2 && ly >= r.y1 && ly <= r.y2) {
                        longestSideWidget.value = r.size;
                        longestSideWidget.callback?.(r.size, app.canvas, node);
                        node.setDirtyCanvas(true);
                        return;
                    }
                }
            }, { serialize: false });
            presetWidget.serialize = false;
            presetWidget._rects = [];

            presetWidget.draw = function (ctx, node, widgetWidth, y, height) {
                const margin = 14;
                const gap = 5;
                const innerW = Math.max(40, widgetWidth - margin * 2);
                const n = PRESETS.length;
                const cellW = Math.max(10, (innerW - gap * (n - 1)) / n);
                const h = Math.min(height - 2, 18);
                const top = y + (height - h) / 2;
                const current = longestSideWidget.value;
                this._rects = [];

                ctx.save();
                ctx.font = "11px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";

                for (let i = 0; i < n; i++) {
                    const x = margin + i * (cellW + gap);
                    const active = Number(current) === PRESETS[i];

                    ctx.beginPath();
                    if (ctx.roundRect) ctx.roundRect(x, top, cellW, h, 4);
                    else ctx.rect(x, top, cellW, h);
                    ctx.fillStyle = active ? "#f28f41" : "#2a2a2a";
                    ctx.fill();
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = active ? "#f28f41" : "#555";
                    ctx.stroke();

                    ctx.fillStyle = active ? "#111" : "#ccc";
                    ctx.fillText(String(PRESETS[i]), x + cellW / 2, top + h / 2 + 0.5);

                    this._rects.push({ x1: x, x2: x + cellW, y1: top, y2: top + h, size: PRESETS[i] });
                }
                ctx.restore();
            };

            // Move preset row to right after longest_side
            const lsIdx = node.widgets.indexOf(longestSideWidget);
            const pwIdx = node.widgets.indexOf(presetWidget);
            if (pwIdx !== lsIdx + 1) {
                node.widgets.splice(pwIdx, 1);
                node.widgets.splice(lsIdx + 1, 0, presetWidget);
            }
        }

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
        const statusWidget = node.addWidget("button", "_sbr_status", null, () => {}, { serialize: false });
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
            ctx.fillText(this._text || "— RUN TO PROCESS —", widgetWidth / 2, y + height / 2);
            ctx.restore();
        };

        // Run Batch button
        const runBtn = node.addWidget("button", "▶ Run Batch", null, () => {
            app.queuePrompt(0, 1).catch(e => console.error("[SmartBatchResize] Queue failed:", e));
        }, { serialize: false });
        runBtn.serialize = false;

        // Show/hide counter_start based on use_counter toggle
        const useCounterWidget = node.widgets?.find(w => w.name === "use_counter");
        const counterStartWidget = node.widgets?.find(w => w.name === "counter_start");
        if (useCounterWidget && counterStartWidget) {
            const defaultComputeSize = counterStartWidget.computeSize;
            const updateCounterVisibility = () => {
                counterStartWidget.computeSize = useCounterWidget.value
                    ? defaultComputeSize
                    : () => [0, -4];
                node.setDirtyCanvas(true);
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
                if (w.type === "customtext") w.computeSize = () => [0, -4];
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
            }
            node.setDirtyCanvas(true);
        };

    },
});
