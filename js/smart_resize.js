import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Craftopia.SmartResize",

    async nodeCreated(node) {
        if (node.comfyClass !== "SmartResize") return;

        const longestSideWidget = node.widgets?.find(w => w.name === "longest_side");
        if (!longestSideWidget) return;

        const PRESETS = [512, 768, 1024, 1536];

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

        // Move preset row to right after longest_side
        const lsIdx = node.widgets.indexOf(longestSideWidget);
        const pwIdx = node.widgets.indexOf(presetWidget);
        if (pwIdx !== lsIdx + 1) {
            node.widgets.splice(pwIdx, 1);
            node.widgets.splice(lsIdx + 1, 0, presetWidget);
        }
    },
});
