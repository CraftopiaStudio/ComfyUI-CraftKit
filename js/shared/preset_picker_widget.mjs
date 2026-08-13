import { app } from "../../../scripts/app.js";

// A single canvas-drawn implementation, used in both classic LiteGraph and
// Nodes 2.0 (via the WidgetLegacy.vue bridge — type: "custom" isn't a
// recognized Vue registry name, so it falls through to the bridge, same as
// the divider/status widgets in canvas_widgets.mjs). No separate DOM-widget
// path: an earlier version used addDOMWidget for Nodes 2.0, but repositioning
// that DOM widget into the middle of node.widgets (to sit under longest_side
// instead of at the end) desynced Vue's value-to-row binding for every widget
// after it on save/reload. Canvas "custom" widgets don't have that problem —
// they've been confirmed to survive reposition + reload fine — so there's no
// need for the dual-path/DOM version this node's click-only (no hover)
// interaction never actually required.
const PRESET_ROW_HEIGHT = 26;
// Hit-test area is padded a few px beyond the visible chip on every side —
// forgiving actual mouse precision, which drifts a little between press and
// release, unlike pixel-perfect synthetic clicks.
const HIT_PAD = 3;

export function createPresetPickerWidget(node, targetWidget, presets) {
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
            // Read the live node width rather than the (possibly stale-cached)
            // widgetWidth parameter — see the comment in canvas_widgets.mjs.
            const w = node?.size?.[0] || widgetWidth;
            // Nodes 2.0's WidgetLegacy bridge permanently stamps widget.width
            // from its own container onto this widget object (and never
            // clears it on unmount). Classic LiteGraph's own click hit-test
            // (getWidgetOnPos) reads widget.width — not node.size[0] — to
            // decide the clickable X range, so once this node has ever been
            // painted under Nodes 2.0, classic mode silently loses clicks on
            // the right side of a wide node forever. Keep width in sync on
            // every draw so classic's hit-test always agrees with reality.
            this.width = w;
            const margin = 14;
            const gap = 7;
            const innerW = Math.max(40, w - margin * 2);
            const n = presets.length;
            const cellW = Math.max(10, (innerW - gap * (n - 1)) / n);
            const h = Math.min(height - 2, 22);
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
                if (lx >= r.x1 - HIT_PAD && lx <= r.x2 + HIT_PAD && ly >= r.y1 - HIT_PAD && ly <= r.y2 + HIT_PAD) {
                    targetWidget.value = r.size;
                    targetWidget.callback?.(r.size, app.canvas, node);
                    node.setDirtyCanvas(true, true);
                    // Nodes 2.0's WidgetLegacy bridge only repaints its canvas
                    // via the widget's own triggerDraw() (set on it once mounted),
                    // not via setDirtyCanvas — without this the newly-active chip
                    // never highlights even though the value did change.
                    this.triggerDraw?.();
                    return true;
                }
            }
            return false;
        },
    };
    return node.addCustomWidget(widget);
}
