# Agent notes

Read `/Users/taborsmac/repos/cluer-context-library/manifest.json` first. It
lists every document with its `description`, `type`, `validation_status` and
`path`. Load only what this task needs.

- Load documents whose `type` is `craft` for UI and site work.
- Load documents whose `type` is `project` for Helm.
- Do not load both in the same session.

For UI work, start with
`context/site-design-contract.md`. Then load the matching skill:

- visual sign-off, iteration pass, design QA → `skills/design-preflight.md`
- scroll-telling hero, particle field, WebGL story → `skills/scroll-story-particles.md`
- admin desk, ops console, CRM board → `skills/instrument-desk.md`
- standing up audit / shot / sweep in this repo → `skills/verification-harness.md`

This repo's design contract is `DESIGN.md`. Its Cursor rule is
`.cursor/rules/design-system.mdc` (copied from the kit's
`.cursor-rules/design-system.mdc`). The seven hard rules in those two files
must match the library contract. If they drift, stop and align them.

When a library document and this repo's code disagree, the code wins and the
document is stale. Re-derive from the `sources` listed on the document.
