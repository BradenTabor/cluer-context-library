# Cluer context library

Shared context and skills for AI agents.

This repository holds documents, an index, and a validator. That is all it
holds. It does not run agents, orchestrate anything, or import skills from
elsewhere. Something else reads from here and decides what to do.

It has two jobs:

- **Helm config** — how the Cluer Helm stack is actually configured, so the
  next change does not recreate the 2026-08-17 outage. Reference example:
  [`context/helm-config-architecture.md`](context/helm-config-architecture.md).
- **Site craft** — the portable design contract, pre-flight, particle story,
  instrument desk, and verification harness derived from a production Next.js
  site, so the next website or app does not re-learn them from scratch.

The Helm document is the reference for how to write another one. Read it
before adding a document. Site-craft documents sit beside it; they do not
rewrite it.

## How an agent uses it

Read `manifest.json` first. It lists every document with its `description`,
`type`, `validation_status` and `path`, so an agent can decide what is worth
loading without opening anything. Then load only the documents it needs.

- Load documents whose `type` is `craft` for UI and site work.
- Load documents whose `type` is `project` for Helm.
- Do not load both in the same session.

```json
{
  "name": "helm-config-architecture",
  "path": "context/helm-config-architecture.md",
  "type": "project",
  "description": "How configuration is split across Cluer Helm and the Hermes sandbox ...",
  "validation_status": "piloted",
  "last_validated": "2026-08-27",
  "sources": ["infra/openshell/hermes-sandbox/config.yaml", "..."]
}
```

Two fields decide whether to act on what you read. `validation_status` says how
far the document has been checked. `sources` says which files, tests and commits
it was derived from — when a document and the code disagree, the code wins and
the document is stale.

## Layout

```
context/      documents about how a system is built and why
  _TEMPLATE.md
  helm-config-architecture.md     type: project
  site-design-contract.md         type: craft
skills/       procedures an agent follows
  design-preflight.md
  scroll-story-particles.md
  instrument-desk.md
  verification-harness.md
adapters/     thin Agent Skills pointers for Cursor and Claude
  agent-skills/<name>/SKILL.md
templates/    scaffolding copied into a future project, never into an existing one
  new-site/DESIGN.md
  new-site/AGENTS.md
  new-site/CLAUDE.md
  new-site/.cursor-rules/design-system.mdc
scripts/
  validate.py
  build_manifest.py
  selftest.py
  doclib.py
  install-adapters.sh   default --dry-run; --apply creates the symlinks
.github/workflows/validate.yml   the same three checks, on every push
manifest.json the index: every document, what it covers, how far it is trusted
```

`adapters/` and `templates/` are not structure-checked. They are credential-scanned.

## Setting this up on a machine

```bash
git clone git@github.com:<you>/cluer-context-library.git
cd cluer-context-library
scripts/install-adapters.sh --dry-run    # shows what would be linked
scripts/install-adapters.sh --apply      # creates the symlinks
```

That symlinks `adapters/agent-skills/*` into `~/.cursor/skills` and
`~/.claude/skills`, so every new Cursor or Claude chat on that machine loads
the five skills automatically. Nothing needs to be pasted into a chat.

The clone can live anywhere. Each adapter resolves its own symlink to find the
library root, so the path is never hardcoded. `--apply` refuses to replace a
real directory or a symlink pointing somewhere else, and reports which name it
refused; it never deletes anything. Restart Cursor if the skills do not appear.

To take a machine back off the library, delete the symlinks in those two
directories. Nothing else on the system was touched.

## Starting a new site

Copy `templates/new-site/` into the new repo. Point `AGENTS.md` at this
library's `manifest.json`. Rename `.cursor-rules/` to `.cursor/rules/` so
Cursor picks up the rule. Fill `DESIGN.md` for that product. The seven hard
rules in `DESIGN.md`, the Cursor rule, and `context/site-design-contract.md`
must stay the same list in the same order.

You do not need to paste anything into the agent chat. If the adapters are
installed on that machine, the five skills are already loaded and will invoke
themselves when the work matches their description.

## Validation states

Every document declares one of three, and `manifest.json` carries it through so
an agent can weigh a document before trusting it.

| State | Means | How to treat it |
| --- | --- | --- |
| `unvalidated` | Written down, never checked against the running system. | A lead. Verify against `sources` before acting on any specific claim. |
| `piloted` | Checked against the real system at least once, on `last_validated`. | Act on it. Re-confirm individual numbers that would be expensive to get wrong. |
| `proven` | Has been relied on repeatedly and held up. | Act on it without re-deriving. |

`last_validated` is the date the check actually happened, not the date the file
was edited. It may be blank only while a document is `unvalidated`, because
there is no honest date to put there yet. Moving a document up a state means
re-checking it against `sources` and updating that date; if you cannot, move it
back down instead of letting it drift.

These thresholds are a starting point. Replace them with whatever promotion rule
the team actually wants to enforce.

## Adding a document

```bash
cp context/_TEMPLATE.md context/my-topic.md   # or skills/my-topic.md
$EDITOR context/my-topic.md
python3 scripts/validate.py --strict
python3 scripts/build_manifest.py
```

The filename is the identifier: `name` in the frontmatter must match it exactly.
Start at `validation_status: unvalidated` with `last_validated` blank, and
promote it once it has been checked. Quote every frontmatter value. YAML ends a
plain scalar at whitespace-then-`#`.

Write it the way the reference document is written. Every gotcha in it is
something that actually broke, with what was believed, what is true, and what it
cost. A list of hypothetical risks is not worth loading into a context window.

## Validating

```bash
python3 scripts/validate.py                   # exit 1 on any error
python3 scripts/validate.py --strict          # warnings fail too
python3 scripts/validate.py --json            # machine-readable findings
python3 scripts/validate.py --max-age-days 180
python3 scripts/build_manifest.py --check     # fails if the index is stale
python3 scripts/selftest.py                   # checks the validator itself
```

`.github/workflows/validate.yml` runs the first, third and fourth of those on
every push and pull request, twice — once with PyYAML installed and once
without, because the two frontmatter parsers have to agree. A malformed
document, a stale `manifest.json`, or anything that looks like a credential
fails before it lands. On the first of each month it also runs
`--max-age-days 180`, which fails when a `piloted` or `proven` document has
not been re-checked in six months. Re-validate it and bump `last_validated`,
or move it back down to `unvalidated` — do not let it drift.

Structure checks run on every `.md` under `context/` and `skills/`: frontmatter
parses as YAML, the required fields are present and well formed,
`validation_status` is one of the three states, `name` matches the filename, and
the required sections all exist. A heading may carry a subtitle after an em dash
— `## Gotchas — things that have actually broken` satisfies `Gotchas`.

The credential scan runs wider, over every text file in the repository, because
a leaked key matters wherever it lands. It looks for vendor-prefixed tokens
(`sk-`, `ghp_`, `AKIA`, and others), private key blocks, long hex and base64
blobs with high Shannon entropy, and sensitive names such as `API_KEY` or
`PASSWORD` assigned a literal value. Any hit is an error and fails the run.

False positives are the real risk with a scanner like this: one that cries wolf
gets ignored, and then it is worse than nothing. If a match is wrong, append
`pragma: allow-secret` to the line — and add the case to `scripts/selftest.py`
so the exemption is a permanent test rather than a one-off.

Files whose name starts with `_` are treated as templates. They are structurally
checked, so the template cannot drift away from what the validator wants, but
they are left out of `manifest.json`.

## Requirements

Python 3.9 or newer, standard library only. PyYAML is used for frontmatter when
it is installed; otherwise a strict built-in subset parser handles the shape the
template uses and raises on anything richer rather than guessing. Both paths are
covered by `scripts/selftest.py` and produce identical results on the documents
here. Install it with `pip install pyyaml` if you want full YAML support.
