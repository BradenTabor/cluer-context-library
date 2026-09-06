---
name: 'verification-harness'
type: 'craft'
description: 'Stand up the design verification harness in a new repo: static audit, identity check, screenshot script, route sweep, and the npm scripts that wire them. Use when starting a site that must enforce the design contract, or when the next project would otherwise rebuild this tooling from memory.'
validation_status: 'piloted'
last_validated: '2026-09-06'
sources:
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/audit.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/shot.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/sweep.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/verify-identity.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/scripts/drift.mjs @ 2c3bd9d'
  - '/Users/taborsmac/CluerGPUwebsite(re-name)/package.json @ 2c3bd9d'
---

# Verification harness

## Why this document exists

The contract in `context/site-design-contract.md` is only as strong as the scripts that fail the build when it is broken. Those scripts were written against one site's folders, class names, and content files. Copying them into the next repo makes them pass on the old shape and miss the new one. Rebuilding them from memory is how a four-figure sum gets spent twice.

This skill is the rebuild recipe. Load it when the next repo has no `npm run verify`. Load `skills/design-preflight.md` when the scripts exist and a change needs to go green.

## Wire the npm scripts first

In `package.json`, before any of the files exist, reserve the names so the rest of the repo can call them:

```
"audit": "node scripts/audit.mjs",
"verify:identity": "node scripts/verify-identity.mjs",
"shot": "node scripts/shot.mjs",
"check:sweep": "node scripts/sweep.mjs",
"check:drift": "node scripts/drift.mjs",
"check:scroll": "node scripts/scroll.mjs",
"perf": "node scripts/perf.mjs",
"verify": "npm run typecheck && npm run lint && npm run audit && npm run verify:identity"
```

Add schema or other gates to `verify` only once they exist. `shots/` is gitignored. Playwright and `@axe-core/playwright` are devDependencies. None of this ships.

## Static audit

`scripts/audit.mjs` is a walk of `app`, `components`, `lib`, `content`, `config` for `.ts`, `.tsx`, `.css`. It prints `ok` or `FAIL` per check and exits 1 if any fail. Rebuild these checks against the next repo's folders. Do not import the last file.

**No hardcoded colour in components.** On each `.tsx` line, ignore comments. Fail on a hex colour (except URL-encoded `%23`) and on Tailwind palette utilities (`bg-zinc-900`, `text-white`, `border-neutral-800`, and the rest of that scale). Palette modules named `palette.ts` are exempt here; the next check owns them.

**Scene palettes match their CSS tokens.** Each `palette.ts` names its sheet with `@sheet filename.css` in the header, or the parent directory names it. Every `"#rrggbb" /* --token */` must equal that token's declared hex in the sheet.

**Contrast on every ground.** Parse each ground's token block separately (`selector {` … next `\n}`). For every ink token present, require 4.5:1 against every text ground (`--bg`, `--surface`, `--surface-2`, and any extra plate ground). `--edge` requires 3:1. Implement WCAG sRGB relative luminance in the script; do not shell out. A token missing from a block is skipped, not failed — bind new tokens in every block so they get checked.

**Travelling colour.** If `--live` is a long-hue `color-mix` between two poles, reproduce the mix in the script (OKLCH, longer hue, ~40 stops) and require 4.5:1 against every text ground in every block that declares the poles.

**Decorative tokens are not text.** Fail `text-[var(--rule)]` and `text-[var(--rule-strong)]` unless the element is `aria-hidden`.

**No literals in components.** Prices (`$12.00` shapes) and the project's own spec numbers must live in `content/`. Comments are exempt. Keep a short allowlist of numbers that really are CSS or arithmetic.

**No forbidden claims on rendered surfaces.** Scan `app` and `components` for cheapest, SLA, uptime percentages, held certifications, trusted-by, fake queue positions, stock photography, press or funding claims. Skip server and market libraries. A roadmap file that names certifications as planned is exempt for that pattern only.

**Identity.** The product name appears only in the config file. The identity script below is the dedicated check; the audit may repeat a cheap version.

**Sources.** Every rate row carries a source and a date. Every external source records the figures actually read off the page (`quotes[]` or equivalent). A URL without quotes is how a wrong citation passes.

**Motion rest state.** Fail `animation: … forwards`. Fail an `animation:` that is not `none`, not `infinite` / `steps(`, and lacks `backwards`. Fail `opacity: 0` as a resting declaration outside `@keyframes`, except a visually hidden native input. Require a global `@media (prefers-reduced-motion: reduce)` block that zeros animation duration.

**Forms work without motion.** The reservation (or equivalent) form does not import a motion or 3D library, has a native POST, and does not rely on JS for the success path.

Walk, check, print, exit. That is the whole file.

## Identity

`scripts/verify-identity.mjs` reads the active name and the candidate names out of the one config file (a `NAME_CANDIDATES` list plus `name:`). It walks the source tree and fails if any candidate appears as a word outside that file. The script itself is skipped so it can print the names.

Warnings (non-zero does not fail): domain still `example.com`, empty social handles, empty env example keys. Those are launch placeholders.

Run it after a rename and in CI before a deploy. `verify` includes it.

## Screenshot script

`scripts/shot.mjs` takes a route, a label, optional width and height, and flags. It writes `shots/<label>.png` and prints JSON: `path`, `landed` (path after redirects), `status`, console errors, and metrics (`hasHorizontalOverflow`, scroll size). Wait for `load`, not `networkidle` — the dev server keeps an HMR socket open forever.

Flags that earned their keep:

- `--full` — walk the page in 0.7 vh steps so scroll-triggered reveals have fired, then full-page capture.
- `--reduce` — `reducedMotion: "reduce"`.
- `--nojs` — `javaScriptEnabled: false`. Skip `document.fonts.ready` and every `evaluate`; they hang until the promise is collected.
- `--at=` — scroll a selector into view before capture.
- `--pending` — intercept the mutating POST, delay, abort, click submit, photograph `data-pending`. Aborting means a review pass never edits a row.
- `--holdcard` / `--pick` — desk-only: hover the first marked card, or sweep the pointer across the chart hull until a bead reports held.

`HOST` defaults must be overridable. Against `next dev`, set `HOST=localhost`. Against `next start`, either host is fine. Basic auth goes on `context.extraHTTPHeaders`; Playwright's `httpCredentials` does not cover the initial document navigation. Prefer reading credentials from the environment (`node --env-file=.env.local`) so they never appear on a command line.

A page meant to 404 will log a failed-resource error for its own document. Filter that when `status === 404` so the frame is scored as a 404.

## Route sweep

`scripts/sweep.mjs` drives every public route through every viewport and every degradation mode. It is not a screenshot. It reports console errors, horizontal overflow, layout shift, heading order, contrast (axe), focus order, and whether the form survives with JavaScript off.

Width set: 375, 768, 1440, 2560. `--quick` is 1440 only.

Overflow: `documentElement.scrollWidth > innerWidth + 1`. Exempt elements inside a horizontal scroller by **computed** `overflow-x` on ancestors (`auto` or `scroll`), not by class name. A guard written against `overflow-x-auto` stops working the day someone writes `overflow-auto`. Also skip `position: fixed`.

CLS: register a `PerformanceObserver` for `layout-shift`, walk 0.8 vh, sum entries without `hadRecentInput`. Aim at 0.

No-JS pass: open with `javaScriptEnabled: false`, confirm the form fields and the primary copy are in the DOM, and submit if there is a native POST.

Keyboard pass: tab from the skip link through every interactive control. Each stop shows a focus ring (`outline` or box-shadow using `--focus`).

A desk behind credentials is a second script, not a flag that silently skips. It adds filter, sort, pick, link, pending, webgl, and readings (see `skills/instrument-desk.md`). Credentials never print.

## Colour drift and scroll budget

If `--live` travels, a drift script scrolls the pin host in tenths, reads the resolved live colour off a probe element (custom properties return the token, not the mix), and asserts hue keeps moving the long way and does not reverse. Progress must be read from the pin host. "Hue travelled 0 degrees" means it was read from the document.

A scroll script records frame intervals while scrolling the story. Median near 16 ms. This runs against a production build.

## Production measure pass

Pass 3 of the pre-flight is not the dev server:

1. `npx next build && npx next start --port 4320` in one job.
2. Sweep, perf, drift, scroll against that port.
3. Stop the server. Delete probe scripts.

Perf: FCP / LCP / CLS / TBT, 4x CPU throttle. A deferred WebGL chunk may raise TBT after load; that is the scene arriving on idle, which is where it was put. LCP and CLS still have to clear.

## Gotchas — things that have actually broken

**Playwright at 127.0.0.1 against `next dev`.** Believed equivalent to `localhost`. Turbopack refused the chunks. Hydration never ran. The sweep certified a dead page. Set `HOST=localhost` for the dev server.

**`networkidle` as the wait.** The HMR socket never goes idle. Captures hung until timeout. Wait for `load`.

**`evaluate` under `--nojs`.** Every `page.evaluate` hangs until its promise is collected. Gate those calls. A no-JS capture is about whether the page is legible without scripting.

**Overflow guard keyed to a class.** `overflow-x-auto` was the exemption. A later `overflow-auto` overflowed at 375 and the sweep stayed green. Use computed style on ancestors.

**Identity check that listed the name in components "just this once".** The next rename missed those files. The script exists because memory does not.

**Axe on a `mask-image` plate.** Contrast failed against a background that was not there. See `skills/design-preflight.md`. The harness does not special-case it; the component changes.

## Conventions

- `verify` is the static gate and runs without a server. Browser checks are named `shot`, `check:sweep`, `check:drift`, `perf`.
- Production build for measure. Dev server for screenshots during Pass 1, via `localhost`.
- Scripts print enough to act (path, status, the failing selector) and never print credentials.
- The seven hard rules in `context/site-design-contract.md` are what these scripts enforce. A check with no matching rule is noise; a rule with no check will rot.

## Off-limits

- Do not copy the last site's `audit.mjs` into the next repo. Folder names, class prefixes, spec numbers, and form component names will silently skip or silently pass.
- Do not put live credentials in the script, in argv that gets logged, or in the library.
- Do not add these scripts to the production bundle.
- Do not lower a budget to go green.

## Definition of done

The harness exists in the next repo when:

1. `npm run verify` runs typecheck, lint, audit, and identity, and exits 0 on a clean tree.
2. `npm run audit` fails if a component gains a hex colour, a Tailwind palette class, a product-name literal, a forbidden claim, or an `opacity: 0` rest state.
3. `npm run shot` writes a PNG and JSON including `hasHorizontalOverflow` and `status`, and supports `--reduce` and `--nojs`.
4. `npm run check:sweep` covers every public route at 375 / 768 / 1440 / 2560 plus reduced-motion and no-JS, and exits non-zero on axe serious/critical or overflow.
5. Against `next dev`, documented invocation uses `HOST=localhost`.
6. `shots/` is gitignored. Credentials are read from the environment.
