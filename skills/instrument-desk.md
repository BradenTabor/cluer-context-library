---
name: 'instrument-desk'
type: 'craft'
description: 'Build a dense internal admin surface that reads like a bank of instruments: one row set, one projection shared by SVG and WebGL, URL-only view state, a hold channel between list and scene. Use for an admin dashboard, ops console, CRM board, or a 3D chart wired to real rows.'
validation_status: 'piloted'
last_validated: '2026-09-06'
sources:
  - '/Users/taborsmac/.cursor/skills/instrument-desk/SKILL.md'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/DESIGN.md @ 2c3bd9d'
---

# Instrument desk

## Why this document exists

Admin surfaces collapse into dashboard templates: three cards, a chart that does not match the table, filters that live in React state and die with JS off. A desk people use every day has to be the opposite. Two ideas carry it: everything derives from the same rows, and the enhancement is registered exactly over the thing it replaces.

This was built once as a pipeline board with a sounding field. The next desk will have different rows. The shape does not change.

## Architecture

Copy this shape, not the class names.

```
app/admin/
  layout.tsx        rail: mark, nav, store pip, timestamp
  page.tsx          the board — reads once, derives everything, renders
  derive.ts         PURE. rows in, instrument readings out. no I/O, no JSX
  format.ts         PURE. stored value → the label the client actually saw
  admin.css         the desk's own token block, scoped to the desk root
  r/[reference]/    the dossier: one row, read in full, actions in a rail
components/admin/
  project.ts        THE projection. one file. SVG and WebGL both import it
  Chart.tsx         server SVG still — the real picture, not a placeholder
  ChartMount.tsx    gate: in-view + idle + WebGL + not reduced-motion
  Scene.tsx         r3f scene, same numbers through the same projection
  ChartTicks.tsx    axis labels as HTML, rendered twice from one definition
  view.ts           filter + search + sort as one object, one link builder
  hold.ts           which row is being pointed at, shared by list and scene
```

`page.tsx` reads the store once and hands the same array to every instrument. If the chart, the bars and the table can disagree about what is on screen, one of them is lying and nobody knows which.

## The four questions

Order the board so it answers, top to bottom:

1. Is anything wrong? — notices, store pip
2. Where does the desk stand? — a strip of single figures
3. What does it look like? — the scene, and who is waiting, side by side
4. What is actually in it? — the instrument bank, then every row

Only the view counters are global. Everything else reads the filtered rows, so narrowing the board narrows the whole page.

## Type and plates

Three roles, no more. A display face (a real serif or a wide grotesk) for figures only; a mono for everything else, because a desk is columns of values and mono makes them line up for free; and a tag — 0.625rem, 0.14em tracking, uppercase, `--ink-3` — for every label on the page.

```
.plate     surface, hairline, corner ticks at two opposite corners
.tag       the label role. never larger, never a different colour
.figure    display face, tabular-nums, about 2rem, with a small unit beside it
```

Corner ticks (two 8px L-brackets, opposite corners) do more for the instrument read than any amount of gradient. `--edge` is the only border allowed on an interactive control; plate hairlines are decorative.

## One projection, two renderers

The single highest-leverage decision. Put the axonometric maths in one module and let both the SVG and the scene call it.

Export a view size, `project(u, v, w)`, `percent` for HTML overlays, `basis` for pointer tilt, and `paintOrder` for the painter's algorithm. Size the basis so the extremes cannot leave the frame: tallest mark at the far corner, near corner of the plane at the bottom.

The scene's orthographic frustum must reproduce SVG's `preserveAspectRatio="xMidYMid meet"`, and the frame must be held at the viewBox's aspect ratio. Then a percentage is a pixel and the cross-fade shows nothing moving. Recompute the frustum only when the canvas resized.

Set `cam.top = h/2 - halfH` and `cam.bottom = h/2 + halfH` — top below bottom in value terms flips Y, so chart space and SVG space are the same coordinates and you never need a second variant of `project`.

Axis labels are HTML, not SVG text. Glyphs drawn into the still vanish the moment the canvas fades in. Render the ticks once inside the mount's still (so they fade out with it) and once inside the scene, which re-places each node from its live basis every frame. Labels that watch the plane turn without them are the tell that this is a toy.

## The gate

Never mount the scene eagerly. In view (rootMargin 200px), not reduced-motion, WebGL, `hardwareConcurrency >= 4`, not `saveData`, then `requestIdleCallback` to import the scene with a timeout around 2600ms. Cross-fade only on the first real frame, with a ~1.4s fallback that keeps the still.

A scene whose `frameloop` is gated on `inView` stops drawing and blanks the canvas when it scrolls away. Any interaction that scrolls the page will therefore appear to break the chart. Put linked controls beside the scene, not below it.

## View state lives in the URL

Filter, search and sort in one object, one link builder, no client state. Omitting defaults yields the plain desk URL. The same column twice flips direction. Unknown sort keys fall back to the default.

Write comparators so the first click gives the interesting order: the biggest request, the longest wait, the deepest row. Ascending is the second click. Do this by writing the comparator backwards and applying `dir = asc ? 1 : -1`. Break ties on the reference so the order is never unstable.

Column headings are links with `aria-sort` on the `th`, plus an sr-only phrase saying what activating them does. Keep the sort glyph in the DOM in every state (a diamond when off) or the whole header row shuffles.

The search form carries the current filter and sort as hidden inputs. Searching must narrow the board, not reset it.

## The hold channel

A module store, about 30 lines, no context: `hold(ref)`, `subscribe(fn)`. Three sibling client islands inside a server-rendered page have no common wrapper worth creating.

A bridge wraps any list, delegates `pointerover` / `pointerleave` on the container, and reads `data-ref` off the closest marked row. No per-row JavaScript; the list stays a server component.

Highlight by attribute write, never re-render. A 200-row table that re-renders on pointer move is the slowest thing on the page.

The scene keeps the index in a ref and seeds the frame loop's pick with it. Guard against echo: ignore a broadcast that names the bead you are already holding. Do not scroll to the held row. Sweeping the pointer across the plot would drag the list along underneath it.

Put the bridge on the list that is beside the scene. That is where a card and its mark are on screen together.

## Controls and empty states

Server actions plus plain forms, so every action works with JS off. A submit component using `useFormStatus` sets `disabled`, `aria-busy`, `data-pending`. Do not swap the label for a longer gerund — the button changes width. Run a hairline under it instead. Under `prefers-reduced-motion` the global reset finishes that animation in a millisecond; re-state it as a static full-width bar or the busy button looks idle.

`useFormStatus` reports nothing for a GET form. Leave those as plain buttons rather than implying a state that cannot happen. Derive the next state on the server from the current row. Never trust a stage posted by a stale page.

Empty states are content, not fallbacks. Coverage of zero open rows is an em dash, not 100%. A perfect score for an empty view teaches people to stop reading the panel. Pad ranked distributions to a fixed number of blank slots so a row of plates keeps one height. Empty copy names the reason and the way out.

## Gotchas — things that have actually broken

**Empty coverage reporting 100%.** Believed "none failing" was a perfect score. With zero open rows it printed 100% and trained people to ignore the panel. Cost a lying instrument. Coverage of nothing is an em dash.

**Figure and unit both carrying the number.** `value={n}` with `unit` set to a string that started with the same digits printed the figure twice ("12 12 seats"). Strip the unit off the label first. For every figure, assert the unit does not start with the value.

**Seeded references that fail the app's own validator.** A seeded row whose reference failed `isReference()` had a dossier that 404d. Seed data must pass production checks. Clamp `updatedAt >= createdAt` or a row last moved before it arrived reads as a bug.

**Login art under the protected prefix.** An image the login page needed lived at the protected path, so the page that exists to get you past the 401 itself 401d.

**`frameloop` gated on `inView`.** Scrolling to the table blanked the chart. Linked controls sit beside the scene.

**Dropping a leading zero with `.toFixed(2).slice(1)`.** Prints `1.00` as `.00` and puts the bottom of the scale back at the top. Use `.replace(/^0/, "")`.

**Mutating a ref that arrived as a prop.** The React Compiler rejects it. Pass the value up and let the owner write.

**`dt` / `dd` wrapped for layout.** They must be direct children of `dl`. `display: contents` on the wrapper if a wrapper is needed. axe is right.

**A scrolling table without `role="region"`, an accessible name, and `tabIndex={0}`.** Rows past the fold belonged to mouse users only.

## Conventions

- One row set. Derive in a pure module. Format in a pure module. Do not re-read the store per instrument.
- One projection. SVG and WebGL import it. Axis labels are HTML.
- View state is the URL. JS off still filters, sorts, and searches.
- Highlight by attribute write.
- The seven hard rules in `context/site-design-contract.md` still apply. The desk may bind its own token block; it does not invent a third ground system.

## Off-limits

- Do not add client state for filter, search, or sort.
- Do not scroll the list when the plot is held.
- Do not put assets the unauthenticated page needs behind the authenticated prefix.
- Do not vendor the last desk's seed data, reference format, or class prefix.

## Definition of done

A desk change is done when a production-build sweep, not the dev server, shows:

1. Filters: follow a chip link with JS off; row count changes; one chip carries `aria-current`.
2. Sort: follow a heading link with JS off; the column is ordered; exactly one `th` claims `aria-sort`.
3. Pick: sweep the pointer across the plot until a bead responds; the label holds a well-formed reference and got a position.
4. Link: holding a mark marks its card, and hovering a card lights its mark.
5. Pending: intercept the action, delay, abort; assert `data-pending` and `disabled`. Aborting means the sweep never edits a row.
6. WebGL: canvas present, context not lost, drawing buffer non-zero, axis labels still exist once the scene has taken over. Or the still remains, which is also success.
7. Readings: the deepest step of any gauge reads its true maximum, and no figure repeats its own unit.
8. Overflow: exempt horizontal scrollers by computed `overflow-x` on ancestors, not by class name.
9. Screenshots exist with `--pick`, `--holdcard`, `--pending`, `--reduce`, `--nojs` where those flags apply, and they report HTTP status.
