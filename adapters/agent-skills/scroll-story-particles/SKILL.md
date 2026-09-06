---
name: scroll-story-particles
description: >-
  Build a scroll-driven story section where one particle field morphs through
  a sequence of shapes as the reader scrolls, with chapter copy in normal flow
  over a sticky canvas. Use for a scroll-telling hero, morphing particle
  scene, WebGL scroll animation, or story-driven landing page.
---

# Scroll story particles

Read the library document. This file is a pointer, not the content —
do not work from it and do not copy it.

## Where the library is

This file is `adapters/agent-skills/scroll-story-particles/SKILL.md` inside the
`cluer-context-library` repository, reached through a symlink in
`~/.cursor/skills` or `~/.claude/skills`. Resolve the symlink to find the
clone — the library root is three directories above this file's directory.
Do not assume a fixed path; this repository is cloned to different locations
on different machines.

```bash
LIB=$(python3 -c "import os;p=os.path.realpath(os.path.expanduser('~/.cursor/skills/scroll-story-particles'));print(os.path.abspath(os.path.join(p,'..','..','..')))")
echo "$LIB"
```

Swap `.cursor` for `.claude` when running under Claude. If neither symlink
exists, ask where `cluer-context-library` is cloned rather than guessing.

## Read, in this order

1. `$LIB/manifest.json` — the index: every document, its `description`,
   `type` and `validation_status`. Read this before opening anything else.
2. `$LIB/context/site-design-contract.md` — the contract. Always, for any
   UI work.
3. `$LIB/skills/scroll-story-particles.md` — this procedure.

Load only documents whose `type` is `craft`. Do not load `type: project`
(Helm) documents in the same session.

When a library document and the code in front of you disagree, the code wins
and the document is stale. Re-derive from the `sources` listed on it.

The canvas is an enhancement; everything the reader needs is
server-rendered.
