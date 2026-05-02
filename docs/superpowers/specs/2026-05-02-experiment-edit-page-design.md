# Experiment Template Edit Page — Design

**Date:** 2026-05-02
**Status:** Draft, awaiting user review
**Scope:** `lucid-central-command/lucid-ui` only. No orchestrator or DB changes.

## Problem

The current experiment template editor is a modal dialog (`fleet-template-editor.js`, ~917 lines) launched from the templates list and detail pages. It uses three tabs (Builder / Graph / JSON) with breadcrumb drill-down for nested parallels. Users have asked for an edit experience that mirrors the run-config page (`/experiments/<id>/run`) — full page, graph-first, with parameter-level visibility — instead of a cramped modal.

## Goals

- Replace the modal editor with a full-page edit view at `/experiments/<id>/edit`.
- Reuse the visual language of the run-config page: vertical SVG graph with the same color-coded type pills, indentation rules, and node geometry.
- Show the full step tree fully expanded by default, with collapse/expand affordances per parallel and per resolved sub-template.
- Edit any individual step via a right-side drawer that slides in over the graph. Drawer fields adapt to step type.
- Edit template-level metadata (id, name, version, description, parameters_schema, tags) via a separate Settings drawer.
- No persistent right-side panel. When no drawer is open, the graph fills the page.

## Non-goals

- No changes to the orchestrator, DB schema, or experiment engine.
- No new MQTT topics.
- No support for editing fields belonging to a *resolved* sub-template — those edits live in the sub-template's own editor.
- No drag-to-reorder across parents in this iteration. Reordering is supported within a single parent (top-level steps, or sub-steps of a parallel/template). Cross-parent moves come later.
- No new step type. The seven existing types — command, delay, parallel, topic_link, approval, wait_for_condition, template — are the full set.

## Page anatomy

```
┌─ subnav ────────────────────────────────────────────────────────────┐
│  Experiments  ›  <template-id>  ›  Edit                             │
├─ graph header ──────────────────────────────────────────────────────┤
│  Steps · <id> v<version> · N steps      [+ Add] [⚙ Settings]        │
│                                         [⤵ Collapse all] [Discard]  │
│                                                          [Save]     │
├─ graph body (scrollable) ─────────────┐                            │
│                                       │                            │
│   ┌──────────────────────┐            │                            │
│   │ setup_arena          │            │                            │
│   │ command              │            │                            │
│   └──────────────────────┘            │                            │
│            │                          │                            │
│   ┌──────────────────────┐            │       ┌─ drawer ─────────┐ │
│   │ survey_team          │            │       │ <step-name>      │ │
│   │ parallel       ▲     │            │       │ <type-pill>    × │ │
│   └──────────────────────┘            │       ├──────────────────┤ │
│            │                          │       │  edit form       │ │
│      ┌─────┴─────┐                    │       │  (per type)      │ │
│   ┌──┴──┐    ┌──┴──┐                  │       │                  │ │
│   │  …  │    │  …  │                  │       ├──────────────────┤ │
│   └─────┘    └─────┘                  │       │ Delete   Cancel  │ │
│                                       │       │           Apply  │ │
│                                       │       └──────────────────┘ │
├─ legend ────────────────────────────────────────────────────────────┤
│  Types: command  parallel  template  delay  topic_link  …           │
└─────────────────────────────────────────────────────────────────────┘
```

The graph and the drawer are siblings inside a flex container. When the drawer is closed, the graph occupies the full width. When open, the drawer is fixed at 380px on the right and the graph reflows to use the remaining space (no overlay — the graph is shifted, not covered).

## Graph rendering

Reuse the layout primitives from `fleet-run-config.js`:

- `NW = 220` × `NH = 36`, `VSTRIDE = 46`, `INDENT = 28`. (Slightly tighter than the run-config page so a fully expanded large template like `foraging-experiment` — 125 nodes, 5778px — stays readable.)
- One vertical spine per parent. Children indented `INDENT` to the right when the parent is expanded.
- Bezier-curve edges between consecutive siblings; same `<marker id="arr">` arrowhead.
- Color tokens by type — identical palette to `fleet-run-config.js`:
  - command `#3b82f6`, delay `#6b7280`, parallel `#8b5cf6`, topic_link `#14b8a6`, approval `#f59e0b`, wait_for_condition `#eab308`, template `#10b981`.
- Each node renders the step name (truncated to 28 chars) and a small monospace type label. An expansion indicator (▲ / ▼) appears on parallel and template nodes.
- Currently selected node gets a 2.2px white stroke. Expandable nodes get a 1.8px green stroke. Plain leaves get 1.2px stroke in the type color.

### Default expansion state

- All top-level steps visible.
- Parallels expanded by default.
- Templates with `resolved_steps` expanded by default.
- Per-node expansion state persisted in `localStorage` under `lucid_template_edit_<id>`.
- Toolbar buttons: `Expand all`, `Collapse all`.

### Click semantics

A click on a node always opens the drawer for that step. If the node is expandable (parallel or template with resolved_steps), the click *also* toggles its expand state — i.e., a single click both selects and toggles. Subsequent clicks while the drawer is open swap the drawer to the new step (re-toggling expand on each click). Closing the drawer (× or Escape) only deselects; it does not collapse.

This matches the user's stated behavior: "when clicked it will expand if it has subtemplates or parallel, and in both cases it will show a popup."

## Drawer

Fixed right-edge panel, 380px wide, full page height under the subnav. Header with step name + type pill + close `×`. Body with form fields. Footer with `Delete`, `Cancel`, `Apply`.

The drawer is a controlled component on top of in-memory state. `Apply` writes the edited fields back into the in-memory template tree and closes the drawer. `Cancel` discards the in-drawer edits. `Delete` removes the step from its parent and closes the drawer. None of these touch the server; only the page-level `Save` persists.

### Field set per step type

All types share: `Name`, `On failure`, `When (guard)`. The remaining fields are type-specific:

| Type | Additional fields |
|---|---|
| **command** | Agent, Component, Action, Timeout (s), Retries, Params (JSON textarea) |
| **delay** | Duration (s) |
| **parallel** | Sub-steps list (drag handle, name, type pill); `+ Add sub-step` |
| **template** | Template ID, Template parameters (key/value rows). `resolved_steps` rendered read-only with a hint "Sub-steps shown inline in the graph; edit them in the source template." |
| **topic_link** | Operation, Source topic, Target topic, Payload template, Select clause, QoS |
| **approval** | Message |
| **wait_for_condition** | Telemetry metric, Condition (JSON), Timeout (s) |

`Params (JSON)` and `Condition (JSON)` are textareas with a syntax-validation indicator (red border + inline error if `JSON.parse` fails). `Apply` is disabled while invalid.

### Sub-template steps (resolved)

When the user clicks a step that is inside a `template` node's `resolved_steps`, the drawer opens in **read-only** mode with a banner:

> "This step belongs to template `<sub-template-id>`. [Open sub-template editor →]"

The link navigates to `/experiments/<sub-template-id>/edit`. This is the only navigation away from the page; we do not silently switch templates.

## Settings drawer

A separate drawer (same chrome, swapped content) opened by the toolbar `⚙ Settings` button. Contains template-level metadata:

- `ID` (read-only after creation; editing the id is not supported in this iteration)
- `Name`, `Version`, `Description`, `Tags` (chip input)
- `Parameters schema` table: each row has name, type (select), default, description, required (checkbox); `+ Add parameter` row at the bottom; `×` to remove.

Settings drawer `Apply` writes the metadata into the in-memory template; `Save` on the page header persists.

## Add step affordance

The toolbar `+ Add` opens a small inline picker (popover under the button) with the seven step types. Picking one appends a new step at the end of the **top-level** list with a sensible default name (`new-<type>-<n>`) and opens its drawer for immediate editing.

To add a sub-step inside a parallel or a template (rare for templates), use the `+ Add sub-step` button inside that step's drawer.

## Save flow

1. User clicks page-header `Save`.
2. Build the request body from the in-memory template:
   - `id`, `name`, `version`, `description`, `tags` from the metadata.
   - `parameters` from `parameters_schema`.
   - `steps` from the top-level `steps` array, **stripped of `resolved_steps` and `resolved_parameters`** (those are derived fields produced by `/resolve`, not part of the source-of-truth definition).
3. `POST /api/experiments/templates` with the body. (The endpoint is upsert on `id`.)
4. On `201`: toast `"Template saved"`, refresh local state from the response, do not navigate.
5. On error: toast the error detail, leave the form dirty.

`Discard` reloads the template from the server and resets the in-memory state.

A small "● unsaved changes" indicator appears in the header whenever the in-memory tree differs from the last-saved snapshot. Reload-prompt via `beforeunload` when dirty.

## Routes & files

### Server

- `app/routes/ui.py` — add:
  ```python
  @router.get("/experiments/{template_id}/edit", response_class=HTMLResponse)
  def experiment_template_edit(request: Request, template_id: str):
      ctx = _ctx(request, page_id="experiment_template_edit", template_id=template_id)
      return templates.TemplateResponse(request=request, name="experiment_template_edit.html", context=ctx)
  ```

### Templates

- `app/web/templates/experiment_template_edit.html` — new. Mirrors `experiment_run_config.html` structure. Sub-nav breadcrumbs end at `Edit`. Loads `fleet-template-edit.js`.

### Static

- `app/web/static/fleet-template-edit.js` — new module, IIFE pattern matching `fleet-run-config.js`. Exposes nothing globally; reads `LUCID.templateId`. Sections:
  - `init()` — fetch `/api/experiments/templates/<id>/resolve`, populate state, render.
  - `_state` — `{ template, dirty, expandedSubs, drawerStep, drawerKind ('step' | 'settings' | null) }`.
  - `renderGraph()` — adapted from `fleet-run-config.js`. Same SVG primitives, slightly tighter geometry. Adds the click-toggles-expand-and-selects behavior.
  - `renderDrawer()` — switch on `drawerKind` and step type. Builds the per-type form. Returns the same chrome.
  - `renderToolbar()` — adds Add / Settings / Expand all / Collapse all / Discard / Save.
  - `applyDrawer()`, `cancelDrawer()`, `deleteStep()` — drawer footer actions.
  - `save()` — strips resolved_* fields, POSTs, toasts.
- `app/web/static/styles.css` — add a new `.te2-*` scope for this page (the existing `.te-*` scope belongs to the modal, which we'll retire later). Re-uses `--accent`, `--surface`, `--surface-2`, `--border`, `--muted` tokens. Drawer geometry mirrors the run-config detail panel.

### Wiring up

- `app/web/static/fleet-experiments.js` (templates list page) — change the row "Edit" button to navigate to `/experiments/<id>/edit` instead of opening the modal.
- `app/web/static/fleet-experiment-template.js` (template detail page) — change the "Edit" button likewise.
- `fleet-template-editor.js` — keep on disk for one release as a fallback; remove the `<script src="...">` includes from `experiments.html` and `experiment_template.html`. Delete the file once the new page is shipped and confirmed.

## Data flow

```
GET /api/experiments/templates/<id>/resolve
        ↓
in-memory: { template (with resolved_steps), expandedSubs, drawerStep }
        ↓ render
graph (SVG) + drawer (per drawerKind)
        ↑ user edits
in-memory mutated; dirty flag set
        ↓ Save
strip resolved_* fields → POST /api/experiments/templates → toast → reload
```

Resolved fields are kept *only* in the rendering layer. The save serializer walks the tree and emits a clean `{steps: [...]}` array.

## Visual reference

Final design mockup at `.superpowers/brainstorm/27915-1777720024/content/final-design.html` shows the full foraging-experiment template rendered in this layout (125 nodes, 4 levels deep) with the drawer open on `ping_all_agents`.

## Risks & mitigations

- **Long graph (5000+px)**: covered by native page scroll and the `Collapse all` toolbar button. No virtualization needed at this scale.
- **Drawer overlap on narrow viewports**: minimum supported width is 1024px (matches the rest of the LUCID UI). Below that, the drawer becomes a modal centered on screen — same fields, just laid out differently. Out of scope for v1; we'll punt mobile to a follow-up.
- **Unsaved-changes loss**: `beforeunload` prompt + visible dirty indicator. Discard prompts confirmation when dirty.
- **Resolved sub-step editing confusion**: explicit read-only banner with a link to the source template. Avoids the trap of users editing what they think is the parent template but is actually substituted.
- **Modal editor regression risk**: keeping `fleet-template-editor.js` on disk for one release lets us flip back without code changes if the new page misbehaves.

## Testing

- Manual: load `/experiments/foraging-experiment/edit`, walk through every step type, edit each, save, reload, verify persistence. Specifically exercise:
  - Editing a top-level command's params JSON.
  - Adding a new parallel and dragging two sub-steps into it.
  - Editing a template step's template_params.
  - Deleting a sub-step inside a parallel.
  - Discarding edits after dirtying every field type.
- No new unit tests for the orchestrator (no orchestrator changes). The `POST /api/experiments/templates` upsert path is already covered.

## Out of scope, named for future iterations

- Cross-parent drag-and-drop (move a step between parallels).
- Template-id rename (requires DB migration of references).
- Visual diff of pending edits vs. last saved.
- Mobile / narrow-viewport layout.
- Inline JSON-mode toggle (hand-edit the raw template JSON).
- A dedicated "validate" button that runs the orchestrator's pre-flight checks without saving.
