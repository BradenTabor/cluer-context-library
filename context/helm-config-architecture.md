---
name: helm-config-architecture
type: project
description: How configuration is split across Cluer Helm and the Hermes sandbox, and the token-budget arithmetic that governs it. Read before changing, validating, or reasoning about any context, lane, or model setting.
validation_status: piloted
last_validated: 2026-08-27
sources:
  - infra/openshell/hermes-sandbox/config.yaml
  - infra/systemd/ollama-code-lane.override.conf
  - packages/contracts/__tests__/sandbox-model-routes.test.ts
  - scripts/commission-hermes-sandbox-appdev1.sh
  - docs/MODEL_FABRIC.md
  - docs/HERMES_HELM_HANDOFF.md
  - 'commit b06f1d6 ("Reserve output room in Hermes'' context budget", #91)'
---

# Helm config architecture

## Why this document exists

A tool was built against a verbal description of these rules and got the core
constraint backwards — it enforced a lower bound where the system enforces an
upper bound. Pointed at production it emitted seven error-severity failures
against values that are deliberately correct, and would have blocked the
commission of the config that *fixed* the 2026-08-17 outage.

The knowledge needed to avoid that already existed, in comments, spread across
two files in different directories and formats. Nothing was hidden. It was just
never in one place.

## The two config worlds — do not confuse them

Configuration is split, and the split is architectural, not accidental.

**Helm's own config — `config/`, JSON, camelCase.**
`model-routing.json`, `api-lane-planning.json`, `capacity/*.json`,
`chat-routes.json`, `compute-routes.json`, and others. This is the control
plane's config: routing, rate/concurrency/price per lane, capacity receipts.

**Hermes' sandbox config — `infra/openshell/hermes-sandbox/config.yaml`, YAML, snake_case.**
This is the executor's own config format, four directories down, and it is where
every context window and output allowance actually lives.

Consequences worth internalizing:

- **No context window is declared anywhere in `config/`.** A tool scanning the
  Helm config tree for token budgets finds nothing, correctly.
- The naming conventions differ (`contextTokens` / `maximumContextTokens` in the
  JSON world; `context_length` / `max_output_tokens` in the YAML world), so a
  single vocabulary will not match both.
- `lanes` appears in three files meaning different things, none of them a token
  window: in `api-lane-planning.json` it is rate/concurrency/price per route; in
  `capacity/*.json` it is integer counts of agent runs, validation, vision, image.

**The lane's token window is in neither.** It is
`OLLAMA_CONTEXT_LENGTH=65536` in `infra/systemd/ollama-code-lane.override.conf`
— a systemd unit, INI format. Any reasoning about window arithmetic must read a
systemd file, a YAML file, and a TypeScript test to see the whole picture.

## The context budget rule — the single most important thing here

`context_length` is the **INPUT budget**. `max_output_tokens` is added on top of
it. Setting `context_length` equal to the served window therefore asks for more
than the window holds.

The enforced constraints, from `sandbox-model-routes.test.ts`:

```
context_length + max_output_tokens  <=  laneWindow
laneWindow - context_length         >=  laneWindow / 8
```

The reservation is sized for **two** things, and the larger one is not output:

- `max_output_tokens` — the reply itself (4096).
- Hermes' own token estimator running low — it reported 52,912 for a prompt
  llama.cpp had clamped at 65,516, so it is at least 19% under. The true ratio
  is unknowable, because a clamped prompt hides its real size. The
  `laneWindow / 8` assertion is a proxy for that undercount.

Current production values on appdev1: lane window 65,536; `context_length`
40,960; `max_output_tokens` 4,096. Check them: 40,960 + 4,096 = 45,056, inside
65,536. And 65,536 − 40,960 = 24,576, above the 8,192 eighth. Both satisfied
with room.

**40960 is not a bug. It is the fix.** `commission-hermes-sandbox-appdev1.sh`
asserts `context_length == 40960` outright, with the message "context_length
must stay below the served window minus max_output_tokens."

## Gotchas — things that have actually broken

**The 2026-08-17 outage.** `context_length` was set to 65,536 against a
65,536-token lane, reasoning that the budget should be "truthful to the minimum
capacity behind this stable alias." Because `max_output_tokens` is added on top,
every request asked for 69,632. Ollama filled the window with prompt, clamped at
65,516, and left roughly twenty tokens to generate in. The model started a
`write_file` tool call, hit the ceiling mid-JSON, and llama-server rejected its
own output as "unexpected end of JSON input." Cost a night of "running it now"
with no benchmark produced.

The lesson, in the commit's own words: **"Truthful about the window is the
mistake — the budget has to be the window minus what the reply needs."**

**The coupled pair.** The lane window (systemd unit) and the Hermes budget
(sandbox YAML) are one decision in two files. The unit says so in place:
*"Those two values are one decision -- change them together."* Changing one
without the other reintroduces the outage.

**The doubly-declared lane.** `OLLAMA_CONTEXT_LENGTH=65536` appears twice in the
same unit on purpose — once as an `--env` flag the container actually receives,
once as an `Environment=` line read by
`scripts/configure-dual-ollama-appdev1.sh`. Change both, or "the assertion passes
while the model keeps running the old setting."

**"Floor" is a product noun here.** `floor-turn.ts`, `floor-sessions`,
`config/floor-crew.json` — it means the operator-facing collaboration surface,
not a numeric bound. Grepping for "floor" expecting a limit will mislead you.
The number people say aloud as "64K" is the *lane window* (65,536) and it is a
ceiling.

**A route absent from `lanes` is silently resident.** `apiLane()` is a direct
keyed lookup; a route not present in `api-lane-planning.json` is classified as
resident rather than API. That is a real semantic default and it is invisible.

**The 8K routes are deliberate.** `local-batch-fast`, `local-vision`, and
`local-review` declare 8,192, matched by `maximumContextTokens: 8192` in
`batch-planning.json`. A single global output cap was tried and rejected: 4K
truncated frontier `write_file` calls, while a frontier-sized cap left no input
room on the qualified 8K local routes.

## Conventions

**Never hardcode a model ID.** `local-project`, `frontier-code`, `chatgpt`,
`claude` are stable LiteLLM aliases. The concrete model and sampling profile are
owned by Helm's model fabric (`docs/MODEL_FABRIC.md`), not baked into the
sandbox. This is what keeps Helm and Hermes independent of the current model.

**The card is sliced, not maximized.** Ollama allocates context × parallel, so
total KV is the budget and the only question is how to slice it. On the 4090 at
q4_0, measured 0.0543 MiB/token, these all cost the same: 65,536×2, 32,768×4,
16,384×8, 131,072×1. **64K × 2 is the chosen slice** — the owner asked for
concurrency, and the factory's API lane advertises concurrency the previous
128K×1 slice could not honour.

**Verify residency after any restart.** Batching adds compute buffers beyond KV,
so headroom is thinner than KV arithmetic suggests:

```
docker exec cluer-ollama-code ollama ps      # PROCESSOR must read 100% GPU
nvidia-smi --query-gpu=memory.used --format=csv
```

Drop to 32,768 × 2 if layers spill. A lane offloading to host memory costs far
more than either the context or the concurrency buys.

**Quality evidence is a hard gate.** Hermes must advertise
`contracts: ["quality-evidence-v1"]`, and each job must emit ordered
`quality.evidence` events for every requested gate before its terminal success
event. Helm rejects success with missing or failed evidence. The marker is a
promise of validated behavior, not a readiness flag to set early.

## Off-limits

- Do not change `context_length` or `OLLAMA_CONTEXT_LENGTH` independently.
- Do not raise the reservation "because there's room" — it is sized for a
  measured undercount that has not been re-measured. Raise it only after the
  undercount is actually measured.
- Do not set `context_length` equal to the served window under any reasoning
  about truthfulness. That is precisely the 2026-08-17 failure.
- `hermes-worker.env` is not in this repo. It lives outside version control at
  `$HOME/Projects/Hermes/hermes-worker/deploy/`. Any check that needs to resolve
  `key_env` values cannot be satisfied from a repo checkout alone.

## Definition of done

A change to context, lane, or model configuration is done when:

1. Both halves of the coupled pair are updated together.
2. `sandbox-model-routes.test.ts` passes — it reads the lane out of the systemd
   unit rather than restating it, so it will catch a one-sided change.
3. The commissioner's `context_length == 40960` assertion is updated if the
   budget moved, or left alone if it did not.
4. Residency is verified after restart per the commands above.
5. If the reservation changed, the reasoning is written down in place, in the
   comment, the way the existing ones are.
