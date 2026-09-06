---
name: _TEMPLATE
type: project
description: One sentence on what this covers and when an agent should read it. Replace this.
validation_status: unvalidated
last_validated:
sources:
---

# Title

<!--
Copy this file to context/<name>.md or skills/<name>.md and fill it in.

Rules the validator enforces:
  - `name` must equal the filename without .md
  - `validation_status` is one of: unvalidated | piloted | proven
  - `last_validated` is YYYY-MM-DD, and may only be blank while unvalidated
  - the five section headings below must all be present
  - `sources` is a list of the files, tests, and commits this was read out of

A heading may carry a subtitle after an em dash — the validator matches on the
part before it, so `## Gotchas — things that have actually broken` is fine.

Delete these comments when you fill the file in.
-->

## Why this document exists

<!-- The specific failure or near-miss that made this worth writing down. What
went wrong, or would have, because this knowledge was spread across files. -->

## <Body section>

<!-- Replace with as many H2 sections as the subject needs. These carry the
actual content: how the thing is structured, what the rules are, the arithmetic,
the values in production right now. Name them for what they say, not generically. -->

## Gotchas — things that have actually broken

<!-- Only things that have actually broken, or would have. Each one: what was
believed, what is true, what it cost. Not a list of hypothetical risks. -->

## Conventions

<!-- The standing rules a change has to respect, and why each exists. -->

## Off-limits

<!-- Things not to change, with the reason. Include anything that cannot be
resolved from a repo checkout alone. -->

## Definition of done

<!-- Numbered. What must be true before a change in this area is finished:
which tests pass, which assertions get updated, what gets verified by hand. -->
