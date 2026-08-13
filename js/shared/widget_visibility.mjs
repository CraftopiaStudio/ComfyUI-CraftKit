// Dynamically show/hide a widget (e.g. a field that only makes sense when
// another toggle is on) in a way that works in BOTH classic LiteGraph and
// Nodes 2.0.
//
// Classic mode collapses a row by giving it computeSize() => [0, -4] — the
// canvas layout loop calls computeSize() every frame, so this is enough on
// its own there.
//
// Nodes 2.0 never calls computeSize() at all; its widget list is a Vue
// `shallowReactive` array (see ComfyUI's useGraphNodeManager.ts) that only
// tracks the array's own indices/length, not properties nested inside each
// widget (like widget.options.hidden). So setting widget.hidden/options.hidden
// is necessary but NOT sufficient — nothing tells Vue to re-run the computed
// that reads it. A push-then-splice-it-back no-op on node.widgets forces a
// real structural array mutation, which Vue's reactive array DOES notify on,
// causing the widget list to re-evaluate and pick up the new hidden state.
export function setWidgetVisible(node, widget, visible) {
    // Widgets don't always define their own computeSize (many rely on
    // LiteGraph's built-in default row sizing), so it can legitimately be
    // undefined — guard capture with a separate flag rather than truthiness,
    // or a later call would "capture" the already-collapsed [0,-4] function.
    if (!widget._visibilityDefaultCaptured) {
        widget._defaultComputeSize = widget.computeSize;
        widget._visibilityDefaultCaptured = true;
    }
    widget.computeSize = visible ? widget._defaultComputeSize : () => [0, -4];
    widget.hidden = !visible;
    if (!widget.options) widget.options = {};
    widget.options.hidden = !visible;

    const nudge = { name: "__visibility_nudge__", type: "custom", value: null, computeSize: () => [0, 0], draw() {} };
    node.widgets.push(nudge);
    node.widgets.splice(node.widgets.indexOf(nudge), 1);

    node.setDirtyCanvas(true, true);
}
