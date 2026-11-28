# Roadmap

## v0: the governance core

Shipped:

- lifecycle CLI: `labkit new` / `doctor` / `wave` / `close`
- generic guards: `gates`, `evidence`, `ckpt`, `gpu`, `augment`, `config`
- the project template and the method docs (`docs/methodology.md`, `docs/lessons.md`)

Not shipped: anything that launches a training or inference run.

## Next: landing in this repository

The training and evaluation pieces below land in this repository when a real project needs
one of them, and only with two-sided tests: the broken or placeholder form must go red, the
real form must go green. Nothing is ported from a private repository.

- `evalkit`, `runscript` and `crosscheck` take their starting point from the public line of
  [med-diag-lab](https://github.com/lynxpurr/med-diag-lab) (Apache-2.0); [NOTICE](NOTICE) credits it when a piece lands.
- `datacheck`, `splitkit`, `repair` and the consoles are written here from a behavior spec
  first (under `docs/specs/`).

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
  Accepted 2026-11-28. `doctor/engine` is green for the engine only when `<swift_bin> --version`
  exits 0 within 60 seconds; it is red when the file is missing or not executable, when it cannot
  be executed (a launcher whose interpreter is gone), when it exits non-zero, or when it does not
  return in time. `tests/test_lifecycle.py` carries the green form and the four red forms.
- A code-level guard against self-matching process kills (a `stop` subcommand).
- English versions of the template and the method docs.
- A PyPI release.
