# Changelog

All notable changes to `ft-labkit` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[semantic versioning](https://semver.org/).

## [Unreleased]

### Changed

- `labkit doctor`: the engine check now runs `<swift_bin> sft -h` and is green only
  when it exits 0. It used to pass for a launcher script whose interpreter had been
  removed, and to fail only when a run started. `--version` is not used: ms-swift's
  launcher has no such flag and exits 1 with a `KeyError`.

## [0.1.0a1] — 2026-11-28

First public prerelease. v0 is the governance core: it carries the method and the
project skeleton, and nothing that launches a training or inference run.

### Added

- `labkit new`: creates a project from the built-in template (charter, plan,
  handoff, agent protocol, ledgers, data provenance), with its own `git`
  repository and a `.gitignore` that keeps training outputs out of history.
- `labkit doctor`: five environment checks, each a JSON verdict plus an exit
  code: config file, engine binary and interpreter, model directory, GPU
  (free memory and the process table), and whether the training interpreter
  can import `labkit`. It also verifies the SHA-256 of every registered data
  file without relying on the `sha256sum` command.
- `labkit wave`: inserts a preregistration block into `PLAN.md`, in Chinese or
  English (`--lang en`), and creates the wave's evidence directory.
- `labkit close`: refuses to close a wave until its verdict is filled in, the
  evidence directory is non-empty, the day's lessons batch carries a promotion
  line, and the working tree is clean. Placeholders that merely contain the
  words "pass" or "fail" do not count as a verdict, and the template's own placeholder
  lessons batch does not count as the day's batch.
- `labkit.gates`: `gold_gate`, `negative_controls` and `checks_gate`.
- `labkit.evidence`: `write_new` refuses to overwrite an existing report.
- `labkit.ckpt`: last-step computation, numeric checkpoint selection and the
  last-step hard gate.
- `labkit.gpu`: precheck (free memory against NEED, plus the process table),
  wait-and-retry, and a background memory sampler.
- `labkit.augment`: a deterministic augmentation skeleton with quota
  assertions, cross-mode deduplication, an audit hook and no random numbers.
- `labkit.config`: `labkit.toml` with `LABKIT_*` environment overrides.
- `labkit --version` prints the path of the `labkit` package that is running,
  so that two installations with the same name can be told apart.

### Notes

- Project names are lowercase letters, digits and single hyphens (1–64
  characters), because the name is also the directory and `name` of the
  project's agent skill.
- File reads and writes are always UTF-8, and console output does not fail
  under a non-UTF-8 locale.
- The training and evaluation pieces (`evalkit`, `runscript`, `datacheck`,
  `splitkit`, `crosscheck`, `repair`, the consoles) are not part of this
  release; see [ROADMAP.md](ROADMAP.md).
