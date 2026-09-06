---
name: 'design-preflight'
type: 'craft'
description: 'Three-pass design pre-flight for a Next.js site: static audit, screenshot review at 390 / 768 / 1440, then production-build axe, CLS, overflow, reduced-motion and no-JS. Use before calling visual work done, or when asked for an iteration pass, design QA, or a green board.'
validation_status: 'piloted'
last_validated: '2026-09-06'
sources:
  - '/Users/taborsmac/.cursor/skills/design-preflight/SKILL.md'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/DESIGN.md @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/audit.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/sweep.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/shot.mjs @ 2c3bd9d'
---

# Design preflight

## Why this document exists

Visual work was signed off from the code. Layout shift, axe contrast on a masked plate, and a page that never hydrated under Playwright all shipped past a "looks fine in the editor" review. The pre-flight exists so the next site cannot call UI done without looking at the screenshots and running the board.

Load this with `context/site-design-contract.md`. For standing the scripts up in a new repo, load `skills/verification-harness.md`.

## Pass structure

Three iteration passes, then a green board. Never call visual work done from the code alone.

1. **Pass 1 — does it hold?** Screenshot every section at 390 / 768 / 1440, plus reduced-motion and no-JS. Fix clipping, crowding, wrapping, overlap.
2. **Pass 2 — complexify.** Add the detail that makes it feel instrumented (readouts, indices, tickers, plates, pointer response). Re-shoot.
3. **Pass 3 — measure.** Production build. Run the full board below. Fix every red item at its root, rebuild, rerun until zero.

## Static gate

No browser, no server, seconds:

```
npm run verify
```

That is typecheck, lint, the design audit, and identity. Audit checks worth having, described rather than vendored:

- No hex and no Tailwind palette colour in components. Scene palette literals must match the token named in their comment.
- Every ink token clears 4.5:1 and `--edge` clears 3:1 against every ground, in every token block, parsed separately. A token that is fine on dark and fails on paper is a fail.
- If a colour travels (`color-mix` by scroll), reproduce the curve and sample about 40 stops against every ground it can be text on.
- Decorative rules never used as text colour.
- Prices, specs, and the product name never typed into a component.
- Forbidden marketing claims scanned on rendered surfaces only.
- No keyframe rests at an offset. A global reduced-motion stop exists.
- Every rate row carries a source and a date. Every cited source records the figures actually read off the page.

## Browser board

Run against a **production** build, not the dev server, on a spare port. Dev-server caveat: drive Playwright at `localhost`, not `127.0.0.1`, or Turbopack blocks the chunks and nothing hydrates. Production `next start` is fine on either.

Walk every route at 375 / 768 / 1440 / 2560. Then reduced-motion. Then no-JS. Collect axe (serious and critical), horizontal overflow, CLS with attribution, keyboard (skip link plus a focus ring on every stop), LCP / TBT, and whether the form still submits.

Budgets that have held: LCP under 2.5 s (aim under 1 s on a throttled production build), CLS at 0, scroll median near 16 ms, axe serious/critical at 0, overflow at 0.

A screenshot script with `--full`, `--reduce`, `--nojs`, and `--at=` for a section turns "is this legible" into one command. Look at the image before claiming the change is done. Output belongs in a gitignored `shots/` directory. Report HTTP status so a deliberate 404 frame reads as a 404 rather than as a broken page.

## Diagnosing the usual reds

These are failures that already happened, with the fix that landed.

- **axe contrast against an impossible background.** A `mask-image` plate with `background-color`. axe cannot see masks. Paint the colour as `background-image: linear-gradient(c, c)`.
- **axe contrast flickering on one label.** The blink animation was on the text, not the dot. Animate a pseudo-element only.
- **CLS of 0.1 at one width only.** `max-w-[Nch]` on a variable-weight heading. `ch` tracks weight. Use `em`.
- **CLS from headings as they animate.** Weight change re-wraps lines. Lock lines at rest weight first. Strip HTML comment nodes and `normalize()` before measuring — React SSR inserts comment markers between adjacent text nodes.
- **CLS specks from a nav readout.** Text length changes. `whitespace-nowrap overflow-hidden`.
- **"no acknowledgement" on submit.** The success view contained another form with the same input name. Assert on a field unique to the primary form.
- **TBT high, LCP fine.** Scene geometry built on the main thread after idle. Acceptable if deferred; otherwise chunk shape generation.
- **"hue travelled 0 degrees".** Progress was read from the document, not the pin host. Put the pin-host marker on the story section.

## Attribution probe for CLS

Register a `PerformanceObserver` for `layout-shift` with `buffered: true` inside Playwright `addInitScript`. Record each source node's tag and class and its previous-to-current rect. Walk the page in 0.8 vh steps and print. It names the element in seconds, which is cheaper than guessing from a screenshot.

## Gotchas — things that have actually broken

**Playwright at 127.0.0.1 against Turbopack.** Believed equivalent to `localhost`. The page never hydrated. Cost a sweep that certified a site nobody could use. Use `localhost` on the dev server.

**`mask-image` plus `background-color`.** Believed the plate was decorative and contrast would ignore it. axe treated it as an opaque sheet. Cost a board that could not go green until the fill was a gradient of the same stop twice.

**`ch` on a charging headline.** Believed it was a character cap. CLS 0.12 at one width. Use `em`. Cost a layout-shift hunt that only reproduced at 1440.

## Conventions

- Never call visual work done from the code alone. Look at the screenshots.
- Production build for the measure pass. The dev server is for Pass 1 only, and only via `localhost`.
- Fix red items at the root. Do not disable an axe rule, bump a budget, or screenshot around a clip.
- Temp probe scripts get deleted. Throwaway servers get stopped.
- The seven hard rules in `context/site-design-contract.md` still apply. This skill does not replace them.

## Off-limits

- Do not vendor the last site's `audit.mjs` into the next repo unchanged. The checks are the contract; the file names, class prefixes, and content paths are not.
- Do not skip `--reduce` or `--nojs` because "it is only a copy change". Copy reflows.
- Do not treat a green typecheck as a green board.

## Definition of done

1. `npm run verify` clean, production build clean.
2. Sweep: 0 problems. Perf: CLS 0, LCP inside budget.
3. Screenshots reviewed at 390 / 768 / 1440, plus reduced-motion and no-JS.
4. New strings in the content module, new tokens in every ground.
5. Temp probe scripts deleted; throwaway servers stopped.
