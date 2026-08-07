# CraftKit Nodes 2.0 Widget Compatibility — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every custom-drawn JS widget across ComfyUI-CraftKit's 4 nodes (section dividers, status boxes, longest-side preset chips) render correctly under both classic LiteGraph canvas rendering and ComfyUI's "Nodes 2.0" (Modern Node Design / Vue) renderer, without regressing classic-mode layout or widget-value save/reload.

**Architecture:** ComfyUI's Nodes 2.0 Vue layer looks up how to render each widget by matching `widget.type` against a registry of known component names (`button`, `string`, `toggle`, `combo`, ...). CraftKit currently (ab)uses `type: "button"` for widgets that actually paint custom canvas content via a `draw()` override — Vue's registry intercepts `"button"`, renders its own generic `<button>` showing the raw internal widget name, and never calls our `draw()`. The fix has two parts:
1. **Non-interactive widgets** (dividers, status boxes): switch from `node.addWidget("button", ...)` to `node.addCustomWidget({type: "custom", ...})`. `"custom"` is not a recognized Vue registry name, so Vue falls through to `WidgetLegacy.vue`, which creates its own canvas and calls our `draw(ctx, node, widgetWidth, y, height)` unmodified — this works automatically in both renderers with one implementation, **provided** `computeSize(width)` returns `[width, height]` (passing the given width through) rather than a hardcoded value, which is confirmed by a real, currently-working reference implementation (ComfyUI-Pixaroma's Preview Image button row) and by CraftKit's own prior history (a code comment in `smart_resize.js` documents that an earlier bare-custom-widget attempt with a broken `computeSize` "forced the node width and broke the layout on click" — this plan avoids repeating that mistake by copying Pixaroma's verified working shape exactly).
2. **The interactive size-preset chip picker** (click-to-select, needs hit-testing + hover): dual-path, exactly mirroring Pixaroma's own solution to the identical problem — a canvas `addCustomWidget` with a `mouse(event, pos, node)` handler in classic mode, and a real `addDOMWidget` with actual `<button>` elements in Nodes 2.0 mode, chosen once at node-creation time via an `isVueNodes()` check.

**Tech Stack:** Vanilla JS ComfyUI frontend extensions (`app.registerExtension`), LiteGraph `LGraphNode.addCustomWidget`/`addDOMWidget` APIs, no build step (raw ES modules loaded via `WEB_DIRECTORY = "./js"`).

## Global Constraints

- Do not change any Python file (`INPUT_TYPES`, `run()`/`route()`/`control()` signatures) — this is a frontend-only fix, backend node behavior is unaffected.
- Do not change `widget.name` for any existing real (serialized) Python widget — only touches the JS-added decorative widgets (dividers, status, preset picker), which are already `serialize: false` and excluded from `widgets_values`.
- Every widget factory must keep the exact same visual appearance in classic mode as it has today (same colors `#888`/`#333`/`#f28f41`/`#2a2a2a`/`#111`/`#666`/`#ccc`/`#3a3a3a`, same fonts, same layout) — this is a compatibility fix, not a redesign.
- Preserve the existing "Python widgets must stay in their original relative order in `this.widgets`" invariant documented in each file's serialize-override comment — the splice-to-reposition logic must still work after switching widget-creation calls.
- No automated JS test harness exists in this repo. Verification is manual, via the Claude Browser MCP tool: add the node fresh, screenshot in classic mode, toggle Settings → Comfy → "Modern Node Design (Nodes 2.0)" on, reload, screenshot again, confirm no raw internal names (`_div_...`, `_sbr_status`, `size_presets`) are visible as literal button labels in either mode.
- ComfyUI must be running locally at `http://127.0.0.1:8188` for verification steps (start via `Start ComfyUI.bat` in `D:\AI\ComfyUI-Easy-Install`, or ask the user to start it — the project's `restart_comfyui` MCP tool has a known path bug on this machine, see `project_roadmap.md` memory).
- Commit after each task per the user's standing workflow (small, reviewable commits; user commits via VS Code, not this plan's `git commit` steps — treat the "Commit" step in each task as "ready to hand off for the user to commit in VS Code" rather than actually running `git commit`).

---

## File Structure

- **Create:** `js/shared/nodes2.mjs` — one helper, `isVueNodes()`, used to branch the preset-picker widget between classic and DOM implementations.
- **Create:** `js/shared/canvas_widgets.mjs` — two factories, `createDividerWidget(label)` and `createStatusWidget(placeholderText)`, both draw-only `addCustomWidget`-based widgets that work unmodified in both renderers. Replaces the hand-rolled, duplicated divider/status code currently living separately in `smart_batch_resize.js`, `smart_profile_switch.js`, and `smart_prompt_controller.js`.
- **Create:** `js/shared/preset_picker_widget.mjs` — one factory, `createPresetPickerWidget(targetWidget, presets)`, dual-path (classic canvas vs Nodes 2.0 DOM). Replaces the near-identical, duplicated preset-chip code currently hand-rolled separately in `smart_batch_resize.js` and `smart_resize.js`.
- **Modify:** `js/smart_batch_resize.js` — use all three shared factories; remove the local `addSectionDivider`, the local status-widget block, and the local preset-chip block.
- **Modify:** `js/smart_resize.js` — use `createPresetPickerWidget`; remove the local preset-chip block.
- **Modify:** `js/smart_profile_switch.js` — use `createDividerWidget` (called once per slot with `"SLOT 1"`..`"SLOT 4"` as the label) and `createStatusWidget`; remove the local divider-array and status-widget blocks.
- **Modify:** `js/smart_prompt_controller.js` — use `createStatusWidget`; remove the local status-widget block.

---

## Task 1: `isVueNodes()` helper

**Files:**
- Create: `js/shared/nodes2.mjs`
- Test: manual (Task 8 covers live verification; this task's own check is a syntax/console check)

**Interfaces:**
- Produces: `export function isVueNodes(): boolean` — used by Task 3 (`preset_picker_widget.mjs`).

- [x] **Step 1: Write the helper**

```js
// js/shared/nodes2.mjs
// Detects whether ComfyUI's "Modern Node Design (Nodes 2.0)" Vue renderer is
// active, so widgets that need genuinely different implementations per
// renderer (anything with hit-testing/hover, not just a draw() override) can
// pick the right one at node-creation time.
export function isVueNodes() {
    return !!window.LiteGraph?.vueNodesMode;
}
```

- [x] **Step 2: Verify it loads with no console errors**

In the Claude Browser MCP tool: navigate to `http://127.0.0.1:8188/`, open devtools console (`mcp__Claude_Browser__read_console_messages` with `onlyErrors: true`), confirm no new errors referencing `nodes2.mjs`. (The file isn't imported anywhere yet at this point, so this step mainly confirms ComfyUI itself is still healthy before continuing — the real import-error check happens in Task 4.)

- [x] **Step 3: Ready for commit**

```bash
git add js/shared/nodes2.mjs
git commit -m "feat: add isVueNodes() helper for Nodes 2.0 widget branching"
```

---

## Task 2: Shared divider + status widget factories

**Files:**
- Create: `js/shared/canvas_widgets.mjs`

**Interfaces:**
- Consumes: nothing (pure LiteGraph API usage).
- Produces:
  - `export function createDividerWidget(label: string): object` — a widget descriptor ready to pass to `node.addCustomWidget(...)`. Visual output identical to the current `_div_${label}` widgets in `smart_batch_resize.js`/`smart_profile_switch.js`.
  - `export function createStatusWidget(placeholderText: string): object` — a widget descriptor ready to pass to `node.addCustomWidget(...)`. Has a mutable `._text` property the caller sets in `onExecuted` (same as the existing `statusWidget._text` pattern). Visual output identical to the current `_sbr_status`/`_sps_status`/`_spc_result` widgets.

- [x] **Step 1: Write `createDividerWidget`**

```js
// js/shared/canvas_widgets.mjs
// Draw-only widgets (no mouse/click handling) shared across CraftKit nodes.
// type: "custom" is deliberate — it is not a name ComfyUI's Nodes 2.0 Vue
// widget registry recognizes, so Vue falls through to its WidgetLegacy
// bridge, which calls our draw() unmodified in both classic LiteGraph and
// Nodes 2.0. computeSize MUST return [width, height] (passing width through)
// rather than a hardcoded value — a fixed/wrong computeSize previously broke
// node layout on click when this was tried without care (see smart_resize.js
// git history / the comment on the preset-chip widget in that file).

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
```

- [x] **Step 2: Write `createStatusWidget`**

```js
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
```

- [x] **Step 3: Verify no console errors on load**

Same check as Task 1 Step 2 — file isn't imported yet, this just confirms it's syntactically valid by checking it parses (open it directly: `mcp__Claude_Browser__navigate` to `http://127.0.0.1:8188/extensions/ComfyUI-CraftKit/shared/canvas_widgets.mjs` and confirm the browser shows the raw JS text, not a 404 or a syntax-highlighted error page).

- [x] **Step 4: Ready for commit**

```bash
git add js/shared/canvas_widgets.mjs
git commit -m "feat: add shared divider/status widget factories for Nodes 2.0 compat"
```

---

## Task 3: Shared preset-picker widget factory (dual-path)

**Files:**
- Create: `js/shared/preset_picker_widget.mjs`

**Interfaces:**
- Consumes: `isVueNodes()` from `js/shared/nodes2.mjs` (Task 1).
- Produces: `export function createPresetPickerWidget(node, targetWidget, presets: number[]): object` — returns a widget already added to `node` via `addCustomWidget` (classic) or `addDOMWidget` (Nodes 2.0). The caller is responsible for repositioning it in `node.widgets` (same splice pattern the call sites already use) and does NOT need to call `node.addCustomWidget`/`addDOMWidget` itself — this factory does that internally, since the two paths need different LiteGraph APIs.

- [x] **Step 1: Write the classic-mode implementation**

```js
// js/shared/preset_picker_widget.mjs
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
```

- [x] **Step 2: Write the Nodes 2.0 DOM implementation**

```js
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
    // button-row DOM widget (see js/shared/nodes2.mjs comment).
    widget.computeLayoutSize = undefined;
    return widget;
}
```

- [x] **Step 3: Write the dispatcher**

```js
export function createPresetPickerWidget(node, targetWidget, presets) {
    return isVueNodes()
        ? createVuePresetWidget(node, targetWidget, presets)
        : createClassicPresetWidget(node, targetWidget, presets);
}
```

- [x] **Step 4: Add the `app` import needed by both paths**

Add at the top of the file: `import { app } from "../../../scripts/app.js";` (three levels up from `js/shared/` to reach ComfyUI's `scripts/` — verify this relative path against how `smart_batch_resize.js` imports it today, `import { app } from "../../scripts/app.js";`, and adjust the level count for the extra `shared/` nesting: `js/shared/preset_picker_widget.mjs` → `scripts/app.js` is `../../../scripts/app.js`).

- [x] **Step 5: Ready for commit**

```bash
git add js/shared/preset_picker_widget.mjs
git commit -m "feat: add dual-path (classic/Nodes 2.0) preset-picker widget factory"
```

---

## Task 4: Rewire `smart_batch_resize.js`

**Files:**
- Modify: `js/smart_batch_resize.js`

**Interfaces:**
- Consumes: `createDividerWidget`, `createStatusWidget` (Task 2), `createPresetPickerWidget` (Task 3).

- [x] **Step 1: Add imports**

At the top of `js/smart_batch_resize.js`, after the existing `import { app } from "../../scripts/app.js";`:

```js
import { createDividerWidget, createStatusWidget } from "./shared/canvas_widgets.mjs";
import { createPresetPickerWidget } from "./shared/preset_picker_widget.mjs";
```

- [x] **Step 2: Replace the local preset-chip block**

Find the block starting `const longestSideWidget = node.widgets?.find(w => w.name === "longest_side");` through the `if (pwIdx !== lsIdx + 1) { ... }` reposition block that follows it (this is the whole "Compact preset chips for longest_side" section). Replace the widget-creation part (everything between finding `longestSideWidget` and the "Move preset row" comment) with:

```js
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
```

- [x] **Step 3: Replace the local `addSectionDivider` function and its 5 call sites**

Delete the `addSectionDivider` function definition (the block from `const addSectionDivider = (beforeWidgetName, label) => {` through its closing `};`) and the 5 calls below it. Replace with:

```js
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
addSectionDivider("output_format", "OUTPUT FORMAT");
addSectionDivider("skip_if_exists", "OPTIONS");
```

(Note the 5th call's target changed from `"skip_if_exists"` to match the current on-disk section order — verify against the live file before applying, since Task order in this plan was written after the RESIZE→FILENAME→OUTPUT LOCATION→OUTPUT FORMAT→OPTIONS reorder; read the file first and match whatever the current 5 calls actually are, only changing the widget-creation mechanism, not the section order/labels.)

- [x] **Step 4: Replace the local status widget block**

Find `const statusWidget = node.addWidget("button", "_sbr_status", null, () => {}, { serialize: false });` through the end of its `statusWidget.draw = function (...) {...};` block. Replace with:

```js
const statusWidget = createStatusWidget("— RUN TO PROCESS —");
node.addCustomWidget(statusWidget);
```

- [x] **Step 5: Verify `onExecuted` still works unmodified**

Confirm the existing `node.onExecuted` override (later in the file) still reads `statusWidget._text = output.text[0];` — no change needed there since `createStatusWidget`'s returned object still exposes a mutable `._text` property.

- [x] **Step 6: Manual verification — classic mode**

Using the Claude Browser MCP tool: navigate to `http://127.0.0.1:8188/`, confirm Settings → Comfy → "Modern Node Design (Nodes 2.0)" is OFF, add a fresh Smart Batch Resize node, screenshot. Confirm: 5 section labels (RESIZE/FILENAME/OUTPUT LOCATION/OUTPUT FORMAT/OPTIONS) draw with the label+line style (not as buttons), the 4 preset chips (512/768/1024/1536) draw as a colored chip row and clicking one updates `longest_side`, the status box shows "— RUN TO PROCESS —" placeholder text.

- [x] **Step 7: Manual verification — Nodes 2.0 mode**

Toggle Settings → Comfy → "Modern Node Design (Nodes 2.0)" ON, reload the page, add a fresh Smart Batch Resize node, screenshot. Confirm: same 5 section labels draw correctly (not literal `_div_RESIZE` button text), the preset row now shows as real `<button>` elements and clicking one updates `longest_side` and highlights the clicked button, the status box still shows correctly.

- [x] **Step 8: Save/reload regression check (both modes)**

In whichever mode is currently active, change `longest_side` to a non-default value (e.g. click the "768" preset), save the workflow (Ctrl+S), reload the page, confirm the node reopens with `longest_side = 768` and every other widget value in its correct position (no value-shift — the serialize-override logic in this file is unchanged by this task, so this step is a regression check, not a new fix).

- [x] **Step 9: Ready for commit**

```bash
git add js/smart_batch_resize.js
git commit -m "fix: render Smart Batch Resize's dividers/status/presets correctly under Nodes 2.0"
```

---

## Task 5: Rewire `smart_resize.js`

**Files:**
- Modify: `js/smart_resize.js`

**Interfaces:**
- Consumes: `createPresetPickerWidget` (Task 3).

- [x] **Step 1: Add import**

After `import { app } from "../../scripts/app.js";`:

```js
import { createPresetPickerWidget } from "./shared/preset_picker_widget.mjs";
```

- [x] **Step 2: Replace the local preset-chip block**

Replace the entire block from `const presetWidget = node.addWidget("button", "size_presets", ...)` through the end of `presetWidget.draw = function (...) {...};` with:

```js
const presetWidget = createPresetPickerWidget(node, longestSideWidget, PRESETS);
```

Keep the `const PRESETS = [512, 768, 1024, 1536];` line above it, and keep the "Move preset row to right after longest_side" reposition block below it unchanged (it already operates on `presetWidget` by reference/position, not by how it was created).

- [x] **Step 3: Manual verification — classic mode**

Same procedure as Task 4 Step 6, but for Smart Resize: add a fresh node, confirm the preset chips draw and work.

- [x] **Step 4: Manual verification — Nodes 2.0 mode**

Same procedure as Task 4 Step 7, but for Smart Resize.

- [x] **Step 5: Save/reload regression check**

Same procedure as Task 4 Step 8, but for Smart Resize (change `longest_side` via a preset, save, reload, confirm no value-shift across `longest_side`, `multiple_of`, `interpolation`, `upscale_if_smaller`).

- [x] **Step 6: Ready for commit**

```bash
git add js/smart_resize.js
git commit -m "fix: render Smart Resize's preset picker correctly under Nodes 2.0"
```

---

## Task 6: Rewire `smart_profile_switch.js`

**Files:**
- Modify: `js/smart_profile_switch.js`

**Interfaces:**
- Consumes: `createDividerWidget`, `createStatusWidget` (Task 2).

- [x] **Step 1: Add import**

After `import { app } from "../../scripts/app.js";`:

```js
import { createDividerWidget, createStatusWidget } from "./shared/canvas_widgets.mjs";
```

- [x] **Step 2: Replace the local divider-array block**

Find the block that builds `const dividers = [];` with a `for (let i = 1; i <= 4; i++) { ... }` loop creating `_div_${i}` widgets with a per-slot `draw` closure. Replace with:

```js
const dividers = [];
for (let i = 1; i <= 4; i++) {
    const div = createDividerWidget(`SLOT ${i}`);
    node.addCustomWidget(div);
    dividers.push(div);
}
```

- [x] **Step 3: Replace the local status widget block**

Find `const statusWidget = node.addWidget("button", "_sps_status", null, () => {}, { serialize: false });` through the end of its `statusWidget.draw = function (...) {...};` block. Replace with:

```js
const statusWidget = createStatusWidget("— RUN TO SEE RESULT —");
node.addCustomWidget(statusWidget);
```

(Confirm the exact current placeholder text in the live file before applying — copy it verbatim rather than assuming, since this plan is written from a description of the file, not a fresh read of it at execution time.)

- [x] **Step 4: Verify the existing reorder logic is unaffected**

The file's `node.widgets = [indexWidget, ...slotWidgets, statusWidget]`-style reorder logic (with the null-guard/leftover-append fix from M-20) already operates on `dividers[i-1]` and `statusWidget` by reference — no change needed there since `createDividerWidget`/`createStatusWidget` still return plain objects usable the same way.

- [x] **Step 5: Manual verification — classic mode**

Add a fresh Smart Profile Switch node with Nodes 2.0 OFF, screenshot, confirm all 4 "SLOT N" dividers and the status box draw correctly (not as buttons).

- [x] **Step 6: Manual verification — Nodes 2.0 mode**

Toggle Nodes 2.0 ON, reload, add a fresh Smart Profile Switch node, screenshot, confirm the same.

- [x] **Step 7: Save/reload regression check**

Change a `label_n`/`width_n`/`height_n` value, save, reload, confirm all 13 real widget values land in their correct slots in both modes.

- [x] **Step 8: Ready for commit**

```bash
git add js/smart_profile_switch.js
git commit -m "fix: render Smart Profile Switch's SLOT dividers/status correctly under Nodes 2.0"
```

---

## Task 7: Rewire `smart_prompt_controller.js`

**Files:**
- Modify: `js/smart_prompt_controller.js`

**Interfaces:**
- Consumes: `createStatusWidget` (Task 2).

- [x] **Step 1: Add import**

After `import { app } from "../../scripts/app.js";`:

```js
import { createStatusWidget } from "./shared/canvas_widgets.mjs";
```

- [x] **Step 2: Replace the local status widget block**

Find `const statusWidget = node.addWidget("button", "_spc_result", null, () => {}, { serialize: false });` through the end of its `statusWidget.draw = function (...) {...};` block. Replace with:

```js
const statusWidget = createStatusWidget("— RUN TO SEE RESULT —");
node.addCustomWidget(statusWidget);
```

(Again, copy the live file's exact current placeholder text rather than assuming it matches Task 6's.)

- [x] **Step 3: Verify the serialize override added for M-19 still applies correctly**

This file's serialize override (added for M-19, filters `w.serialize !== false && w.options?.serialize !== false`) already excludes this widget via its `serialize: false` property — confirm `createStatusWidget`'s returned object still has `serialize: false` set (it does, per Task 2 Step 2) so no change is needed to the override itself.

- [x] **Step 4: Manual verification — classic mode**

Add a fresh Smart Prompt Controller node with Nodes 2.0 OFF, screenshot, confirm the status box draws correctly.

- [x] **Step 5: Manual verification — Nodes 2.0 mode**

Toggle Nodes 2.0 ON, reload, add a fresh Smart Prompt Controller node, screenshot, confirm the same.

- [x] **Step 6: Save/reload regression check**

Change `index` and `control_after_generate`, save, reload, confirm both land correctly in both modes (this is the exact M-19 bug this file was fixed for earlier in the session — re-verify it still holds after this widget-creation change).

- [x] **Step 7: Ready for commit**

```bash
git add js/smart_prompt_controller.js
git commit -m "fix: render Smart Prompt Controller's status box correctly under Nodes 2.0"
```

---

## Task 8: Full cross-mode verification pass + cleanup

**Files:** none (verification only, plus a final consistency check across all 4 files)

- [x] **Step 1: Grep for any remaining `addWidget("button", "_` or `addWidget("button", "size_presets"` calls**

```bash
grep -rn 'addWidget("button", "_\|addWidget("button", "size_presets"' js/
```

Expected: no matches (everything decorative/custom-drawn now goes through `addCustomWidget`/`addDOMWidget` via the shared factories; only genuinely clickable, single-purpose buttons like "Browse folder" and "Run Batch" should still use `addWidget("button", ...)`, and those are unaffected by this plan).

- [x] **Step 2: Confirm genuine functional buttons are untouched**

```bash
grep -n 'addWidget("button"' js/smart_batch_resize.js
```

Expected: exactly 2 matches — "📁 Browse folder" and "▶ Run Batch" — both real, single-click-triggers-an-action buttons that should keep using LiteGraph's native `ButtonWidget` (they render correctly as real buttons in both classic and Nodes 2.0 already, since `"button"` is a Vue-recognized type that Vue renders as an actual functional button — this is only a problem for widgets that abuse `"button"` to paint something else via `draw()`).

- [x] **Step 3: Full-node screenshot sweep, both modes**

With Nodes 2.0 OFF: place all 5 CraftKit nodes (Smart Prompt Controller, Smart Profile Switch, Smart Resize, Smart Batch Resize, Smart Resolution Multiplier) on one canvas, screenshot.

Toggle Nodes 2.0 ON, reload, repeat: place all 5 fresh nodes on one canvas, screenshot.

Compare the two screenshots side by side — confirm no node shows a literal internal widget name (`_div_...`, `_status`, `_sbr_status`, `_sps_status`, `_spc_result`, `size_presets`) as visible button text in either mode.

- [x] **Step 4: Update the project roadmap memory (no git action — this file lives outside the repo)**

Edit `C:\Users\rubzm\.claude\projects\D--AI-ComfyUI-Easy-Install-ComfyUI-custom-nodes-ComfyUI-CraftKit\memory\project_roadmap.md`, add a line under "Afgerond" noting Nodes 2.0 compatibility was added for all custom-drawn widgets, dated with today's date, mentioning the `js/shared/` module split as a new architectural pattern other future CraftKit JS work should reuse. This is a memory-file edit, not a repo file — no `git add`/`git commit` for this step.

- [x] **Step 5: Ready for the final repo commit**

All of Tasks 1–7 already produced their own commits. If any uncommitted repo changes remain at this point (e.g. a fix made during Task 8's verification sweep), stage and commit those:

```bash
git status --short
git add <any remaining changed files>
git commit -m "fix: final Nodes 2.0 compatibility touch-ups from the verification sweep"
```

If `git status --short` is empty, there is nothing to commit — Tasks 1–7's commits already cover everything.

---

## Self-Review Notes (from plan authoring)

- **Spec coverage:** all 4 JS files with custom-drawn widgets are covered (Tasks 4–7); the shared-factory extraction (Tasks 1–3) removes the duplication between `smart_batch_resize.js`'s and `smart_resize.js`'s near-identical preset-chip code, and between the divider/status code duplicated across 3 files — this was flagged as a Reuse-category improvement opportunity earlier in the session and is folded in here since this plan already touches all the relevant call sites.
- **Known risk flagged explicitly:** Task 3's classic-mode `computeSize` must return `[width, height]`, not a hardcoded value — this repo has direct prior history (a comment in `smart_resize.js`) of this exact mistake breaking node layout. Every `computeSize` in this plan follows the verified-working Pixaroma pattern.
- **Out of scope, deliberately:** `js/shared/nodes2.mjs`'s `applyAdaptiveCanvasOnly` helper (used by Pixaroma to control Parameters-sidebar-tab visibility per renderer) is NOT included — none of CraftKit's decorative widgets currently set `options.canvasOnly`, and adding sidebar-visibility control is a separate, optional cosmetic refinement, not required to fix the "widgets render as raw button text" bug. Flag as a possible follow-up if the decorative widgets turn out to clutter the Nodes 2.0 Parameters sidebar tab during Task 8's verification — if so, that's a good candidate for a small follow-up task, not a blocker for this plan.

---

## Implementation Log (2026-08-07)

Executed inline (not subagent-driven), autonomously while the user slept, then jointly debugged one regression with the user once they were back. Summary of what actually happened, including one deviation from the plan as originally written.

### What went exactly as planned

- Tasks 1–2 (`js/shared/nodes2.mjs`, `js/shared/canvas_widgets.mjs`): implemented verbatim as specified. `node --check` syntax-clean on first try.
- Task 4–7 rewiring: all 4 node JS files updated to use the shared factories. Dividers and status boxes (the `addCustomWidget`/`type:"custom"` path) worked correctly in both classic and Nodes 2.0 rendering on the **first live test**, with zero further changes needed — the `computeSize(width) → [width, height]` pattern copied from Pixaroma was exactly right.
- Environment friction, not a code bug: ComfyUI's static file server for custom-node `WEB_DIRECTORY` content does **not** pick up newly-created files (including brand-new subdirectories) without a full process restart — confirmed by testing both a new nested file and a new flat top-level file, both 404 until restart, while edits to already-existing files serve live with no restart needed. Worth remembering for any future new-file additions to this repo's `js/`.
- Mid-session environment mixup (not a code issue): partway through, port 8188 was unexpectedly being served by an unrelated second ComfyUI installation (`D:\AI\ComfyUI-AGAIN`) the user had set up separately to work around an earlier database-corruption issue. All the "files don't exist" symptoms during that window were because of testing against the wrong install, not a real serving bug. Resolved once the user pointed the real `ComfyUI-Easy-Install` instance back at port 8188.

### The regression found during verification (Task 8) — and its fix

**Symptom:** on Smart Batch Resize and Smart Resize specifically (the two nodes with the preset-chip picker), saving a workflow and reloading it under Nodes 2.0 showed every widget value shifted one row up relative to its label (e.g. "Round to multiple of" displaying `interpolation`'s value, "Interpolation method" displaying `upscale_if_smaller`'s value, and so on down the node). Smart Profile Switch and Smart Prompt Controller (dividers/status only, no preset picker) reloaded with every value correct.

**First, ruled out:** the saved workflow JSON itself. Inspected the actual `widgets_values` array in the saved `.json` file directly — it was `[1536, 8, "lanczos", true]` for Smart Resize, i.e. completely correct, right length, right order. This proved the `serialize()` override (which excludes non-serializable JS widgets from the saved array) was working correctly, and the bug was purely in how the Nodes 2.0 Vue layer re-associated the correctly-loaded values with widget rows after `nodeCreated()` ran.

**Root cause:** `createPresetPickerWidget`'s Nodes 2.0 path uses `node.addDOMWidget(...)`, and both call sites then repositioned it via `node.widgets.splice(...)` to sit directly after `longest_side` — the same reposition pattern already used safely for classic-mode's canvas-drawn preset widget and for all the `addCustomWidget`-based dividers. That pattern is safe for `addCustomWidget` widgets (bridged through `WidgetLegacy.vue`, which reads each widget's own `.value` directly) but **not** for `addDOMWidget` widgets under Nodes 2.0: splicing a DOM widget into the middle of `node.widgets` *after* `configure()` has already loaded the saved values onto the pre-existing widget objects desyncs whatever positional/reactive binding Vue uses for the widget list, shifting every widget after the splice point by one row in the display — even though each widget's underlying `.value` property is untouched and correct. This is consistent with the observed data: only nodes with a mid-list `addDOMWidget` insertion were affected; nodes with only `addCustomWidget` insertions were not.

**Fix:** in `js/smart_batch_resize.js` and `js/smart_resize.js`, the "move preset row to right after longest_side" reposition step is now skipped entirely when `isVueNodes()` is true — the DOM widget is left wherever `addDOMWidget` placed it (empirically, the end of `node.widgets`, after all real Python widgets, the status box, and the Run button). Classic mode is unaffected: its canvas-drawn preset widget still repositions normally, since that path never showed the bug.

**Verified fix, both nodes, full save → reload cycle under Nodes 2.0:**
- Smart Batch Resize: changed `longest_side` to 768 via a preset click, saved, reloaded — every one of the 18 real widgets read back correct (spot-verified via the sidebar Parameters panel plus the node's own canvas text), preset chips still rendered as real `<button>` elements at their new position (after `preview_limit`, before the status box and Run Batch button) and were confirmed clickable.
- Smart Resize: same check, `longest_side` read back correctly along with `multiple_of`/`interpolation`/`upscale_if_smaller`.
- Smart Profile Switch and Smart Prompt Controller: re-verified with a changed `index` value (7) through the same save → reload cycle as a negative control, confirming they were never affected (no `addDOMWidget` in either file) — both read back correct.

**Visual trade-off accepted:** under Nodes 2.0 specifically, the preset-chip row no longer sits directly under "Longest side (px)" — it's now at the bottom of the node, after all other settings. Classic mode keeps the original, nicer placement. Revisiting this (e.g. finding a way to splice a DOM widget safely, or moving to a different widget-list-diffing strategy) is a possible future refinement, not required for correctness.

### Net effect vs. the original plan

Tasks 1, 2, 4, 5, 6, 7 landed as specified. Task 3 (`createPresetPickerWidget`) needed one addition beyond what was originally planned: callers must guard the reposition-splice with `!isVueNodes()`. This wasn't anticipated by the original research (which correctly identified *that* a dual-path widget was needed, but not this specific interaction between splice-repositioning and Vue's post-`configure()` reactivity). Task 8's manual verification sweep is exactly what caught it — this is the reason the plan's "no automated JS test harness, verify manually" constraint insisted on an actual save → reload round-trip check per node, not just a visual glance at a freshly-added node.
- **WorkflowOrganizer is explicitly out of scope** per the user's instruction ("workflow organiser doen we later checken") — this plan touches only ComfyUI-CraftKit.
