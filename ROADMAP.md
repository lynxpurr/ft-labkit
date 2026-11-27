# Roadmap

## v0: the governance core

Shipped:

- lifecycle CLI: `labkit new` / `doctor` / `wave` / `close`
- generic guards: `gates`, `evidence`, `ckpt`, `gpu`, `augment`, `config`
- the project template and the method docs (`docs/methodology.md`, `docs/lessons.md`)

Not shipped: anything that launches a training or inference run.

## Next: implemented here from behavior specs

The training and evaluation pieces below are not ported from anywhere. Each one gets a
behavior spec in this repository first (under `docs/specs/`), and is then implemented from
that spec when a real project needs it. A piece lands only with two-sided tests: the broken
or placeholder form must go red, the real form must go green.

| Piece | Behavior | Needed when |
|---|---|---|
| `evalkit` | A four-stage pipeline, prepare → infer → score → table. Everything domain-specific is injected as functions (grader, gold target, aggregation, data loading, prompts). A gold self-check gate and mutant negative controls run before any model column. Outputs are append-only evidence files with per-row detail fields so they can be re-aggregated later. | the first model evaluation |
| `runscript` | Generates a run script from a JSON spec. The script carries five gates: an unknown tier or arm fails loudly; idempotent skip keyed on the last-step checkpoint; a GPU precheck that refuses to start below NEED; a background memory sampler that is killed on exit; a post-run check of the argument snapshot and the last checkpoint. | the first training run |
| `datacheck` | Leakage checks across train, holdout and external sets, plus a row-level self-check to run after any data transformation. | the first dataset build |
| `splitkit` | A deterministic group-wise split (no RNG), collision removal before splitting, and a size gate. | the first dataset split |
| `crosscheck` | Verifies that what the training framework actually encodes matches the official chat template (verbatim text and mask boundaries); preference-pair checks for DPO. | before the first SFT or DPO run |
| `repair` | A schema self-repair loop for model output: validate → apply a batch of deterministic actions → re-validate, with a round cap; stops on uncovered shapes. | the first structured-output deployment |
| `console`, `console_live` | An evidence browser (zero GPU) and a live base-versus-adapter comparison page. | after `evalkit` |
| skills and installer | An agent skill that routes labkit actions. | after `evalkit` and `runscript` |

## Candidates

- `doctor` engine gate: smoke the binary (`--version`) instead of checking existence and the exec bit.
- A code-level guard against self-matching process kills (a `stop` subcommand).
- English versions of the template and the method docs.
- A PyPI release.
