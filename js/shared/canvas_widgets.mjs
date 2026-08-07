// Draw-only widgets (no mouse/click handling) shared across CraftKit nodes.
// type: "custom" is deliberate — it is not a name ComfyUI's Nodes 2.0 Vue
// widget registry recognizes, so Vue falls through to its WidgetLegacy
// bridge, which calls our draw() unmodified in both classic LiteGraph and
// Nodes 2.0. computeSize MUST return [width, height] (passing width through)
// rather than a hardcoded value — a fixed/wrong computeSize previously broke
// node layout on click when this was tried without care (see the comment on
// the preset-chip widget in smart_resize.js's git history).

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
            const lx = 14;
            ctx.save();
            ctx.font = "bold 10px sans-serif";
            ctx.textBaseline = "middle";
            ctx.textAlign = "left";
            ctx.fillStyle = "#888";
            ctx.fillText(label, lx, y + height / 2);
            const lineX = lx + ctx.measureText(label).width + 8;
            ctx.beginPath();
            ctx.moveTo(lineX, y + height / 2);
            ctx.lineTo(widgetWidth - 14, y + height / 2);
            ctx.strokeStyle = "#333";
            ctx.lineWidth = 1;
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
            ctx.fillText(this._text || placeholderText, widgetWidth / 2, y + height / 2);
            ctx.restore();
        },
    };
}
