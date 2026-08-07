import { app } from "../../../scripts/app.js";
import { isVueNodes } from "./nodes2.mjs";

const PRESET_ROW_HEIGHT = 22;

function createClassicPresetWidget(node, targetWidget, presets) {
    const widget = {
        name: "size_presets",
        type: "custom",
        value: null,
        serialize: false,
        options: {},
        _rects: [],
        computeSize(width) {
            return [width, PRESET_ROW_HEIGHT];
        },
        draw(ctx, node, widgetWidth, y, height) {
            const margin = 14;
            const gap = 5;
            const innerW = Math.max(40, widgetWidth - margin * 2);
            const n = presets.length;
            const cellW = Math.max(10, (innerW - gap * (n - 1)) / n);
            const h = Math.min(height - 2, 18);
            const top = y + (height - h) / 2;
            const current = targetWidget.value;
            this._rects = [];

            ctx.save();
            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";

            for (let i = 0; i < n; i++) {
                const x = margin + i * (cellW + gap);
                const active = Number(current) === presets[i];

                ctx.beginPath();
                if (ctx.roundRect) ctx.roundRect(x, top, cellW, h, 4);
                else ctx.rect(x, top, cellW, h);
                ctx.fillStyle = active ? "#f28f41" : "#2a2a2a";
                ctx.fill();
                ctx.lineWidth = 1;
                ctx.strokeStyle = active ? "#f28f41" : "#555";
                ctx.stroke();

                ctx.fillStyle = active ? "#111" : "#ccc";
                ctx.fillText(String(presets[i]), x + cellW / 2, top + h / 2 + 0.5);

                this._rects.push({ x1: x, x2: x + cellW, y1: top, y2: top + h, size: presets[i] });
            }
            ctx.restore();
        },
        mouse(event, pos, node) {
            if (event.type !== "pointerdown" && event.type !== "mousedown") return false;
            const [lx, ly] = pos;
            for (const r of this._rects) {
                if (lx >= r.x1 && lx <= r.x2 && ly >= r.y1 && ly <= r.y2) {
                    targetWidget.value = r.size;
                    targetWidget.callback?.(r.size, app.canvas, node);
                    node.setDirtyCanvas(true, true);
                    return true;
                }
            }
            return false;
        },
    };
    return node.addCustomWidget(widget);
}

function createVuePresetWidget(node, targetWidget, presets) {
    const root = document.createElement("div");
    root.style.display = "flex";
    root.style.gap = "5px";
    root.style.padding = "0 14px";
    root.style.width = "100%";
    root.style.boxSizing = "border-box";

    const buttons = presets.map((size) => {
        const btn = document.createElement("button");
        btn.textContent = String(size);
        btn.style.flex = "1";
        btn.style.padding = "4px 0";
        btn.style.borderRadius = "4px";
        btn.style.border = "1px solid #555";
        btn.style.background = "#2a2a2a";
        btn.style.color = "#ccc";
        btn.style.fontSize = "11px";
        btn.style.fontFamily = "sans-serif";
        btn.style.cursor = "pointer";
        const syncActive = () => {
            const active = Number(targetWidget.value) === size;
            btn.style.background = active ? "#f28f41" : "#2a2a2a";
            btn.style.borderColor = active ? "#f28f41" : "#555";
            btn.style.color = active ? "#111" : "#ccc";
        };
        btn.addEventListener("click", () => {
            targetWidget.value = size;
            targetWidget.callback?.(size, app.canvas, node);
            for (const b of buttons) b.syncActive?.();
            node.setDirtyCanvas(true, true);
        });
        btn.syncActive = syncActive;
        syncActive();
        root.appendChild(btn);
        return btn;
    });

    const widget = node.addDOMWidget("size_presets", "craftkit_preset_picker", root, {
        serialize: false,
        hideOnZoom: false,
    });
    // Fixed-height row, not a flexible grower — same reasoning as Pixaroma's
    // button-row DOM widget.
    widget.computeLayoutSize = undefined;
    return widget;
}

export function createPresetPickerWidget(node, targetWidget, presets) {
    return isVueNodes()
        ? createVuePresetWidget(node, targetWidget, presets)
        : createClassicPresetWidget(node, targetWidget, presets);
}
