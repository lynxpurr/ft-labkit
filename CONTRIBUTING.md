# Contributing

Open an issue first for anything larger than a typo. The conventions an agent
or a contributor is expected to follow are in [AGENTS.md](AGENTS.md).

Contribute only code, text and data that you are entitled to distribute under
the Apache License, Version 2.0. Public availability of a paper or a repository
does not grant permission to copy its code, text or datasets; resolve the
license and rights first, and record any third-party material in
[NOTICE](NOTICE). The pieces listed under "Next" in [ROADMAP.md](ROADMAP.md)
are implemented from behavior specs written in this repository, not ported.

Every file in the repository is listed individually in the exact file
inventory at `.github/workflows/release-files.json`; add new paths there in
the same change. Before opening a pull request, run from the repository root:

```bash
python -m unittest discover -s tests -t .
```

## Branches and pull requests

`main` is the release branch and is updated only through pull requests.

1. Start each change from the latest `main` on its own `feature/<short-name>`
   branch.
2. Open a pull request to `main` and wait for the checks: lint, the test
   matrix, the tests against the installed package, and the release-package
   verification.
3. Merge with a merge commit to preserve the history of what was reviewed.

Dependabot targets `main` and keeps the pinned GitHub Actions up to date.
