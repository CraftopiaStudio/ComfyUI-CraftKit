// Draw-only widgets (no mouse/click handling) shared across CraftKit nodes.
// type: "custom" is deliberate — it is not a name ComfyUI's Nodes 2.0 Vue
// widget registry recognizes, so Vue falls through to its WidgetLegacy
// bridge, which calls our draw() unmodified in both classic LiteGraph and
// Nodes 2.0. computeSize MUST return [width, height] (passing width through)
// rather than a hardcoded value — a fixed/wrong computeSize previously broke
// node layout on click when this was tried without care (see the comment on
// the preset-chip widget in smart_resize.js's git history).
//
// draw() intentionally ignores its own `widgetWidth` parameter and reads
// `node.size[0]` instead. LiteGraph caches a `.width` on custom-typed widget
// objects the first time it lays them out and reuses that cached value on
// later draws — for a widget added before the node reaches its final size
// (e.g. before later Python widgets are added, or before an explicit
// node.setSize() call), that cache goes stale and draw() keeps receiving the
// old, too-narrow width forever, making the divider line/status box stop
// partway across the node instead of spanning it. node.size[0] is always
// live, so reading it directly sidesteps the stale cache entirely.

const DIVIDER_HEIGHT = 20;

export function createDividerWidget(label) {
    return {
        name: `_div_${label}`,
        type: "custom",
        value: null,
        serialize: false,
        options: {},
        computeSize(width) {
            return [width, DIVIDER_HEIGHT];
        },
        draw(ctx, node, widgetWidth, y, height) {
            const w = node?.size?.[0] || widgetWidth;
            const margin = 14;
            const gap = 8;
            ctx.save();
            ctx.font = "bold 10px sans-serif";
            ctx.textBaseline = "middle";
            ctx.textAlign = "center";
            const cy = y + height / 2;
            const cx = w / 2;
            const textW = ctx.measureText(label).width;
            ctx.fillStyle = "#888";
            ctx.fillText(label, cx, cy);
            // #555 rather than a more subtle #333 — Nodes 2.0 renders this canvas
            // at 2x internal scale and then CSS-scales it again with the graph
            // zoom, which softens a thin line enough that #333 became invisible
            // there (classic mode draws at native resolution and stayed sharp).
            ctx.strokeStyle = "#555";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(margin, cy);
            ctx.lineTo(cx - textW / 2 - gap, cy);
            ctx.moveTo(cx + textW / 2 + gap, cy);
            ctx.lineTo(w - margin, cy);
            ctx.stroke();
            ctx.restore();
        },
    };
}

const STATUS_HEIGHT = 24;

export function createStatusWidget(placeholderText) {
    return {
        name: "_status",
        type: "custom",
        value: null,
        serialize: false,
        options: {},
        _text: "",
        computeSize(width) {
            return [width, STATUS_HEIGHT];
        },
        draw(ctx, node, widgetWidth, y, height) {
            const w = node?.size?.[0] || widgetWidth;
            const margin = 14;
            const innerW = w - margin * 2;
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
            ctx.fillText(this._text || placeholderText, w / 2, y + height / 2);
            ctx.restore();
        },
    };
}
