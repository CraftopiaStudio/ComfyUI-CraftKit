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
        });

        // Exclude button from serialization (saves undefined placeholder to keep index alignment)
        btn.serializeValue = () => undefined;

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
            });
            presetWidget.serializeValue = () => undefined;
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
                    const active = current === PRESETS[i];

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
    },
});
