# Design system contract

Read this before writing or changing any component, stylesheet, or token.
Fill the empty sections for this product. The hard rules do not change.

Stack: (framework, styling, language). Tokens live in CSS.

---

## What this site is

(One paragraph. What is the story, what is the paperwork, what is out of scope.)

---

## Hard rules

These seven rules are the contract. The same list, in this order, lives in
the context library (`context/site-design-contract.md`) and in
`.cursor/rules/design-system.mdc`. If they drift, the library has failed.

1. **No hardcoded colour.** No hex in components. No `bg-zinc-*`, `text-white`, `border-neutral-*`. Use semantic utilities (`bg-bg`, `text-ink`, `border-rule`) or `text-[var(--ink-2)]`. Colour is rebound per ground.

2. **No hardcoded strings.** Copy comes from a content module. Names and URLs come from one config file. Never type the product name into a component.

3. **Base state is the final state.** Animate *from* an offset with `backwards` and no fill-mode forwards. Never `opacity: 0` at rest. Never gate content on JS. `prefers-reduced-motion` is a hard stop and must leave the page fully legible.

4. **`--edge` is the only border allowed on an interactive control.** `--rule` and `--rule-strong` are decorative. Never remove a focus ring.

5. **Two grounds.** One dark, one paper. Every new token is bound in both. `--live` is the travelling colour; `--accent` is fixed and is the only colour a control may be. Hex is allowed only in a palette module, each literal commented with its token name, and an audit fails if they drift.

6. **Verify before claiming done.** Typecheck, lint, the design audit, identity. Then screenshot at 390 / 768 / 1440 plus reduced-motion and no-JS, and check horizontal overflow at those widths.

7. **Every control ships loading, empty, error and disabled** in the same pass. Ideal-state-only UI is not finished UI.

---

## Tokens for this product

(Bind `--bg`, `--ink`, `--accent`, `--live` poles, `--edge`, `--focus` on both grounds. Name the root classes.)

---

## Type roles

(Display, voice, body, tag, figure — faces and what they are for.)

---

## Content and identity

Copy lives in `(path)`. Names and URLs live in `(path)`. Identity check: `npm run verify:identity`.

---

## Motion and accessibility

Skip link, main target, focus ring, reduced-motion stop. Scene mount gate if there is a scene.

---

## Verification

```
npm run verify
HOST=localhost npm run shot -- / <label> 1440 900 --full
npm run shot -- / <label>-reduced 1440 900 --reduce
npm run shot -- / <label>-nojs 1440 900 --nojs
```

Look at the screenshot before claiming a change is done.

## Before you finish

- [ ] `npm run verify` clean
- [ ] No hex values or Tailwind palette colours added to a component
- [ ] New strings live in the content module, not in JSX
- [ ] New tokens bound in both grounds
- [ ] Loading, empty, error and disabled states exist for every new control
- [ ] Screenshotted at 390 / 768 / 1440, plus reduced-motion and no-JS
- [ ] Focus ring visible on every new interactive element, keyboard-tested
