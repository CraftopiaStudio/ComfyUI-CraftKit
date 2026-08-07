// Detects whether ComfyUI's "Modern Node Design (Nodes 2.0)" Vue renderer is
// active, so widgets that need genuinely different implementations per
// renderer (anything with hit-testing/hover, not just a draw() override) can
// pick the right one at node-creation time.
export function isVueNodes() {
    return !!window.LiteGraph?.vueNodesMode;
}
