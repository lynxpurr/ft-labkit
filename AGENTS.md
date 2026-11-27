# AGENTS.md: working on labkit with a coding agent

Read in this order: `README.md`, `ROADMAP.md`, `docs/methodology.md` (Chinese).

## What this repository is

A zero-dependency scaffold for fine-tuning experiments run by coding agents: preregistered
decision rules, append-only evidence, and gates that a machine can check. v0 is the governance
core; training and evaluation pieces are listed under "Next" in `ROADMAP.md`.

## Non-negotiables

1. **Anchor first.** A new guard reproduces a known answer before it is called usable.
   Reproducing the failing form is the strongest evidence that the check works.
2. **Gates are machine-checkable.** Exit code plus a JSON verdict. Reports for human eyes may
   exist alongside, but a gate never depends on a human reading one.
3. **Evidence is append-only.** A file under `reports/` is written once. A revised reading goes
   into a new file next to the old one.
4. **Discipline travels, conclusions don't.** Hyperparameters, mixtures and thresholds belong
   to projects, not here.
5. **No hardcoded machine-specific paths.** Anything machine-specific goes through `labkit.toml` or
   `LABKIT_*`.
6. **Invariants, not content.** Graders, augmentation rules and experiment arms stay in the
   project. Plugin points stop at callables: no DSL, no full parameter wrapping.
7. **Preregister decisions about labkit itself.** Before changing a gate or accepting a new
   piece, write the criterion and both outcomes into `ROADMAP.md` or a spec.

## Definition of done for any change

- From the repository root, `python -m unittest discover -s tests -t .` is green. The same
  suite must also pass against the installed package (CI copies `tests/` elsewhere and runs
  it after `pip install .`).
- `ruff check labkit tests tools` is clean. CI pins the ruff version; bump it deliberately.
- Every new or changed gate has two tests: the placeholder or broken form is red, the real
  form is green.
- `labkit/` imports only the standard library and itself. Text I/O names `encoding="utf-8"`,
  and console output goes through `labkit._io`, so nothing depends on the locale.
- Anything listed under "Next" in `ROADMAP.md` is implemented from a behavior spec written in
  this repository. Do not copy it in from elsewhere.
- Every file is listed in the exact file inventory, `.github/workflows/release-files.json`.
  The test suite fails on an unlisted file and on a listed file that does not exist.
- If a change alters a decision recorded in `ROADMAP.md`, append a line; never rewrite the
  old one. Add a user-visible change to the "Unreleased" section of `CHANGELOG.md`.

## Deferred pieces

Write the spec first (`docs/specs/<name>.md`: inputs, outputs, gates, edge cases, the negative
controls its tests must contain), then implement against it.

## Release checklist

Run before anything is published or tagged. Source cards and review receipts stay in the
maintainer's private records; this list is what the repository itself can show.

- [ ] The origin and distribution rights of every changed path are recorded, including any
      third-party material and its license obligations; third-party material is in `NOTICE`.
- [ ] The refs about to be published were reviewed, and a secret scan was run on them.
- [ ] `python tools/verify_dist.py dist` passes: the repository inventory equals the approved
      file list; wheel and sdist contain exactly the expected files, byte-identical to the
      committed tree; `SHA256SUMS` was written.
- [ ] The wheel was installed into a clean environment outside the checkout;
      `labkit new demo-lab` works there; the test suite passes against the installed package.
- [ ] Tests are green on every Python version in the CI matrix, on a machine without a GPU,
      and under a non-UTF-8 locale.
- [ ] The README quick start was executed as written.
- [ ] GitHub secret scanning and push protection are on, and the dependency-advisory workflow
      has run.

## Branches

`main` is the release branch and is updated only through pull requests. Work on `feature/*`
branches and merge with a merge commit. Do not rewrite the history of a branch that has been
pushed.
