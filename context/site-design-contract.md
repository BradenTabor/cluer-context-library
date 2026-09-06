---
name: 'site-design-contract'
type: 'craft'
description: 'Portable design contract for a Next.js marketing or product site: semantic colour tokens rebound across two grounds, travelling live colour, content sourced from one module, motion whose rest state is the finished page. Load for any new UI work. Do not load for Helm or infrastructure.'
validation_status: 'piloted'
last_validated: '2026-09-06'
sources:
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/DESIGN.md @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/.cursor/rules/design-system.mdc @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/app/globals.css @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/audit.mjs @ 2c3bd9d'
---

# Site design contract

## Why this document exists

A site was built whose rules lived in a design file, a Cursor rule, an audit script, and three personal skills. The next agent to open a blank repo had none of that. It would have re-derived the token bridge, the motion rest-state, and the verify board from taste, and that is how the last build spent a four-figure sum teaching the same lessons twice.

This document is the contract that load for any new UI. It is not a palette, a typeface, or a product. Those belong to the next repo's own `DESIGN.md`.

## The token bridge

Map Tailwind colour utilities onto semantic CSS variables in the global sheet:

```
--color-bg  → var(--bg)      --color-ink   → var(--ink)
--color-ink-2 / --color-ink-3
--color-rule → var(--rule)   --color-surface / --color-surface-2
--color-accent, --accent-2, --caution, --focus
```

A component written as `bg-bg text-ink border-rule` is then correct on every ground, because each ground rebinds `--bg`, `--ink`, `--rule`. The component does not know which ground it is on and must not need to.

Never write a hex value in a component. Never write `bg-zinc-900`, `text-white`, `border-neutral-800`, or any Tailwind palette colour. Use the semantic utility, or `text-[var(--ink-2)]` when Tailwind has no utility for that token.

Adding a colour means adding a token to `@theme` and binding it in every ground. If it cannot be named semantically, it is not needed.

The one sanctioned hex exception is a palette module the WebGL scene can read, because a shader cannot see CSS variables. Every literal carries a comment naming its token, and the audit fails if the two drift.

## Two grounds and travelling colour

Two grounds, not a theme switcher. One dark, one paper. Paper is a subtree class that rebinds the same token names. Every new token is declared in both blocks or it is a bug waiting for the first paper section.

Tokens by role:

- `--bg` `--surface` `--surface-2` — grounds
- `--ink` `--ink-2` `--ink-3` — text, in order of emphasis
- `--accent` / `--accent-2` — the one colour a control may be, and its hover
- `--live` — the travelling colour, mixed in OKLCH the long way round the hue wheel so it never passes through mud. Voice clauses, lead figures, the particle field.
- `--caution` `--hot` `--alarm` — status only, never decoration
- `--rule` `--rule-strong` — decorative separators only
- `--edge` — the only border on an interactive control
- `--focus` — the focus ring

`--live` is `color-mix(in oklch longer hue, var(--from), var(--to) calc(var(--phase) * 100%))`. Reproduce the same curve in TypeScript to bake a 256-wide ramp texture for the shader, and sample ~40 stops against every ground a live colour can sit on as text. Fail under 4.5:1.

`--accent` does not travel. A button that changes hue as the page scrolls is not a control, it is a decoration wearing a click handler.

`--phase` (0–1) is written onto the root of the dark ground from the story's scroll progress, in about 60 discrete steps, not every frame. Every distinct value repaints everything that uses `--live`.

## Content and identity

Components import copy only from a content module. Names, URLs and handles read from one config file. Rename means editing that file and running the identity check; it does not mean grepping the tree.

A figure changes in content once, and the story, the paperwork and the generated social image all pick it up.

Forbidden on rendered surfaces: cheapest, SLA, uptime percentages, held certifications that are only planned, trusted-by strips, fake queue positions, stock photography, press or funding claims. Scan what reaches the DOM. Server and market libraries may name those strings as data.

Every cited source records the figures actually read off the page, not just a URL. A URL proves a citation exists; quotes prove it is checkable.

## Motion and accessibility

Body text clears 4.5:1 on every ground it can sit on, including every stop of `--live`. `--edge` clears 3:1 as a control border. `--rule` is never used as text colour.

Focus rings are never removed, only styled. `:focus-visible` is 2px `var(--focus)`. Every page has a skip link and a main target.

Comparable figures use a tabular lining face.

Keyframes animate from an offset, with `backwards`, and no fill-mode forwards. The element's resting CSS is its finished state. A script failure cannot hide the headline; the headline paints on the first frame and can be the LCP element.

Never gate content visibility on JS. Never `opacity: 0` as a base state. `prefers-reduced-motion` is a hard global stop: animations collapse, the scene does not mount, the still does. Scroll-linked `--phase` may still update, because colour change is not motion.

Hero choreography stays under about 700ms. One scroller owns scrolling; do not add `scroll-behavior: smooth` beside it.

## Type roles

Five roles, no more. A display face for headlines; a voice face for one italic clause per headline, set in `--live`; a body face for running copy; a tag face (uppercase, tracked, the quietest ink) for labels; a figure face (tabular mono) for numbers that will be compared.

Display type may charge weight as it enters, but the resting weight is the base state. Lock each line's break at that resting weight before the weight moves, or the heading re-wraps and shifts everything below it.

Never size a variable-weight heading in `ch`. `1ch` is the advance of the zero glyph, which changes with weight.

## Gotchas — things that have actually broken

**`ch` on variable-weight type.** A `max-w-[14ch]` display heading was believed to cap the line. `1ch` tracks `wght`, so charging 300 to 760 grew the box about 30% and shifted the page (CLS 0.12). Use `em`.

**`opacity: 0` as a rest state.** Headlines were hidden until a reveal script ran. With JS off, or before hydration, the page was blank where the LCP should have been. Resting CSS is the finished state; animate from an offset with `backwards`.

**A masked plate with `background-color`.** axe cannot see `mask-image`. The plate read as an opaque sheet under every label and contrast failed against a colour that was not there. Paint the fill as `background-image: linear-gradient(c, c)`.

**Playwright at 127.0.0.1 against the Next.js dev server.** Turbopack refuses cross-origin chunks. The page never hydrated, the canvas never mounted, and the sweep reported a site that was not the site. Drive the dev server at `localhost`. Production `next start` is fine on either.

## Conventions

These seven rules are the contract. The same list, in this order, lives in a new site's `DESIGN.md` and in its Cursor rule. If they drift, this library has failed.

1. **No hardcoded colour.** No hex in components. No `bg-zinc-*`, `text-white`, `border-neutral-*`. Use semantic utilities (`bg-bg`, `text-ink`, `border-rule`) or `text-[var(--ink-2)]`. Colour is rebound per ground.

2. **No hardcoded strings.** Copy comes from a content module. Names and URLs come from one config file. Never type the product name into a component.

3. **Base state is the final state.** Animate *from* an offset with `backwards` and no fill-mode forwards. Never `opacity: 0` at rest. Never gate content on JS. `prefers-reduced-motion` is a hard stop and must leave the page fully legible.

4. **`--edge` is the only border allowed on an interactive control.** `--rule` and `--rule-strong` are decorative. Never remove a focus ring.

5. **Two grounds.** One dark, one paper. Every new token is bound in both. `--live` is the travelling colour; `--accent` is fixed and is the only colour a control may be. Hex is allowed only in a palette module, each literal commented with its token name, and an audit fails if they drift.

6. **Verify before claiming done.** Typecheck, lint, the design audit, identity. Then screenshot at 390 / 768 / 1440 plus reduced-motion and no-JS, and check horizontal overflow at those widths.

7. **Every control ships loading, empty, error and disabled** in the same pass. Ideal-state-only UI is not finished UI.

## Off-limits

- Do not copy a previous product's class prefix, typefaces, or palette into the next site. This is a contract, not a skin.
- Do not load `type: project` Helm documents while doing UI work, and do not load `type: craft` documents while doing Helm work.
- Do not reintroduce a direction switcher or a second shipping aesthetic "to compare". One direction ships.
- Do not vendor the last site's audit script, particle components, or shader files into this library. Rebuild them in the next repo's shape from the skills.
- Do not invent claims, certifications, or queue positions to fill a panel.

## Definition of done

A UI change is done when:

1. `npm run verify` is clean (typecheck, lint, audit, identity).
2. No hex or Tailwind palette colour was added to a component. New tokens are bound in both grounds.
3. New strings live in the content module, not in JSX.
4. Every new control has loading, empty, error and disabled states.
5. Screenshots exist at 390 / 768 / 1440, plus reduced-motion and no-JS, and both degraded modes are still legible.
6. Horizontal overflow is false at those widths.
7. Every new interactive element shows a focus ring and is reachable from the keyboard.
