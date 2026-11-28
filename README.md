# ft-labkit

**A small scaffold for fine-tuning experiments that coding agents run: pre-registered decision rules, append-only evidence.**

[中文](README.zh.md)

`labkit` is a small scaffold for LLM fine-tuning projects that a coding agent runs for you.
Training frameworks (ms-swift, LLaMA-Factory, Axolotl, TRL, …) handle the training run.
labkit handles the part around it that decides whether you can trust the result:

| Failure mode | labkit's answer | Where it is enforced |
|---|---|---|
| The pass criterion is tuned after the numbers are seen | **Preregistration.** Every wave gets a written decision rule with both outcomes enumerated (`pass → …`, `fail → …`). | `labkit wave` inserts the block; `labkit close` refuses a wave whose verdict is still the placeholder. |
| Results are overwritten and re-read until they look good | **Append-only evidence.** A report is written once; re-judging writes a new file next to the old one. | `labkit.evidence.write_new` raises if the file already exists. |
| A check passes because its real path was never exercised | **Two-sided tests.** Every gate has a negative control: the placeholder or broken form must go red, the real form must go green. | The test suite, on every push. |
| The grader is always-true and nobody notices | **Gold gate + mutants.** The grader must score the gold answers perfectly and must fail on tampered answers. | `labkit.gates.gold_gate` and `negative_controls`, called by your evaluation script before any model column. |
| The same mistake keeps coming back | **A lessons ledger with promotion.** The second occurrence of the same shape must be promoted: lesson → playbook rule → skill → guard code. | `labkit close` requires the day's lessons batch to carry a promotion line; the pipeline is in `docs/lessons-distillation.md`. |
| "It finished" (the directory exists) | **Idempotency keyed on the last checkpoint**, computed from the data size and verified on selection. | `labkit.ckpt`. |

## Status: v0, the governance core

| Ships in v0 | Not in v0 yet |
|---|---|
| `labkit new / doctor / wave / close` | anything that launches a training or inference run |
| project template: charter, plan, handoff, agent protocol | evaluation pipeline, run-script generator, leak checks, template cross-check |
| `gates`, `evidence`, `ckpt`, `gpu`, `augment`, `config` | evidence browser, live base-vs-adapter console |

The missing pieces are specified in [ROADMAP.md](ROADMAP.md) and land in this repository when a
project needs them: written here from behavior specs, except `evalkit`, `runscript` and
`crosscheck`, which are ported from the public line of [med-diag-lab](https://github.com/lynxpurr/med-diag-lab)
and credited in [NOTICE](NOTICE).

**v0 is useful today if you bring your own training and evaluation scripts** and want the
governance layer around them.

## Quick start

Requires Linux, Python 3.11 or newer and `git`. No third-party dependencies. Not on PyPI yet:
install from this repository (the PyPI package called `labkit` is unrelated).

```bash
git clone https://github.com/lynxpurr/ft-labkit.git
cd ft-labkit && pip install .            # or: pip install -e .
# The interpreter you set as train_python in labkit.toml must be able to import labkit too:
# install into that environment, or export PYTHONPATH="$PWD" before the steps below.
labkit --version                         # ft-labkit 0.1.0a1 (path of the package that is running)

labkit new demo-lab                      # creates ./demo-lab from the built-in template
cd demo-lab
$EDITOR CONSTITUTION.md labkit.toml      # one-sentence task, stop conditions, local paths
labkit doctor                            # one JSON verdict per gate; all green before you start

labkit wave W1 baseline                  # inserts a preregistration block into PLAN.md
# The block is in Chinese unless you add --lang en.
# Fill in the decision rule, both outcomes, BEFORE running anything.
# ... run the experiment with your own scripts ...
labkit close W1                          # red until evidence, verdict, lessons and a clean tree exist
```

The new directory is a project of its own, with its own git repository (`labkit new` runs `git init`;
`labkit close` wants a clean tree, so commit before closing). Its `AGENTS.md` is where your coding
agent picks up the protocol, with a skill under `.agents/skills/<name>/`. The template's skill and
`tools/README.md` describe run scripts generated from a spec; that generator is on the
[roadmap](ROADMAP.md), so in v0 write those scripts yourself and follow the same rules.

Project names are lowercase letters, digits and single hyphens (1–64 characters), because the
name is also the directory and `name` of the project's agent skill.

`labkit doctor` reports five checks and exits non-zero if any is red: config file, engine binary
and interpreter, model directory, GPU (free memory plus the process table), and whether your
training interpreter can import `labkit`. The engine check runs `<swift_bin> sft -h` and is green
only when it exits 0, so a launcher script whose interpreter has been removed fails here instead of
when a run starts; `train_python` may be left empty. It also
verifies the SHA-256 of every data file registered in `data/SHA256SUMS`. Without an NVIDIA GPU
the GPU gate is red; the other readings are still reported.

If another package called `labkit` is installed or on `PYTHONPATH`, it can shadow this one:
`labkit --version` prints the path of the package that is actually running, and `labkit doctor`
warns when a configured interpreter imports a different copy.

## How a project runs

```text
doctor all green
   │
   ▼
labkit wave W1  ──►  PLAN.md: preregistered decision rule (pass → …, fail → …)
   │
   ▼
experiment + evaluation         evidence is written once into reports/W1/
   │
   ▼
labkit close W1 ──►  verdict filled · evidence present · lessons batch · promotion line · clean tree
   │
   └──►  next wave …
```

A wave, filled in (the numbers are illustrative). `labkit wave W1 baseline --lang en` inserts the
skeleton; you fill in the rule before running anything, and after the run only the verdict line
is added.

```markdown
### W1 baseline —— pending 2025-01-01
- Action: SFT the 1.7B base on 12k pairs for 3 epochs; evaluate on the 350-item held-out set
- Pre-registration: **R-W1** exact match ≥ 0.40 on held-out (greedy) + guardrails (format-valid ≥ 0.98)
  - pass → W2 scales the same recipe to the 4B base
  - fail → stop here; write up the negative result, do not add data
- Verdict (fill in after the run): pass — exact match 0.43 on held-out; readings in reports/W1/score-sft.json
```

## What is in the box

| Module | What it does |
|---|---|
| `labkit.proj` | the `labkit` CLI: `new`, `doctor`, `wave`, `close` |
| `labkit.gates` | `gold_gate`, `negative_controls`, `checks_gate`: JSON verdict plus exit code, chainable by an agent |
| `labkit.evidence` | `write_new` refuses to overwrite; `latest_by_key`; re-aggregatable schema check |
| `labkit.ckpt` | last-step computation, numeric checkpoint selection, last-step hard gate |
| `labkit.gpu` | precheck (free ≥ NEED plus the process table), wait-and-retry, background sampler |
| `labkit.augment` | deterministic augmentation skeleton: quota assertions, cross-mode dedup, audit hook, zero RNG |
| `labkit.config` | `labkit.toml` plus `LABKIT_*` environment overrides; no absolute paths in code |

The method behind these pieces is in [docs/methodology.md](docs/methodology.md) (Chinese), and the
incidents that produced each rule are in [docs/lessons.md](docs/lessons.md) (Chinese).

## Use it from your own scripts

The gates and the evidence writer are plain functions. This is the skeleton of an evaluation
script; `samples` is your held-out set and `answers` the model outputs:

```python
import sys
from labkit import evidence, gates

def judge(sample, candidate):                 # your grader: booleans only
    return {"exact": candidate.strip() == sample["answer"]}

def gold(s):
    return s["answer"]

pre = [
    gates.gold_gate(samples, gold, judge, required_true=["exact"]),
    gates.negative_controls(samples, gold, judge,
                            [("upper", lambda s, t: t.upper())], required_true=["exact"]),
]
if gates.run_gates(pre) != 0:                 # the grader itself is broken: stop here
    sys.exit(1)

records = [{"id": s["id"], "generated": evidence.stamp(), "arm": "sft",
            "summary": judge(s, answers[s["id"]])} for s in samples]
evidence.write_new_json("reports/W1/score-sft.json", records)   # written once, never overwritten
```

`run_gates` prints one JSON verdict per gate and returns a non-zero exit code when any gate fails,
so an agent can chain it. `write_new_json` writes once and raises if the file already exists.

## Design rules

- **Standard library only.** The package has zero runtime dependencies, so it runs inside any training venv.
- **Function injection, not a DSL.** Graders, augmentation rules and experiment arms live in your project.
- **No hardcoded machine-specific paths.** Everything machine-specific goes through `labkit.toml` or `LABKIT_*`.
- **UTF-8 everywhere.** Files are read and written as UTF-8 regardless of the locale, and console output never fails on encoding.
- **Discipline travels, conclusions don't.** labkit carries method; hyperparameters, mixtures and thresholds stay in each project.

## Language

The governance template and the methodology docs are written in Chinese, the author's working
language. The command-line help and messages are in Chinese as well, including the check names
inside the JSON verdicts; exit codes and the JSON structure do not depend on the language.
`labkit close` recognizes both Chinese and English keywords, and `labkit wave --lang en` inserts
an English preregistration block. Translations are welcome.

## Contributing

ft-labkit is developed by its author working with coding agents; [AGENTS.md](AGENTS.md) records
the conventions those agents follow.

Open an issue first for anything larger than a typo; see [CONTRIBUTING.md](CONTRIBUTING.md).
From the repository root, `python -m unittest discover -s tests -t .` must stay green.

## License

[Apache-2.0](LICENSE). Third-party notices: [NOTICE](NOTICE). Changes: [CHANGELOG.md](CHANGELOG.md).
