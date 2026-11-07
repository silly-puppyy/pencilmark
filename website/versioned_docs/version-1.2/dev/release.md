---
title: Release a version
description: The steps from a finished main branch to a new version on PyPI.
---

# Release a version

A release is a GitHub release: publishing it builds the wheels and uploads them to PyPI through trusted publishing.
Nothing reaches PyPI from an ordinary push, and a version number on PyPI can never be reused, so check everything
before the last step.

## 1. Choose the number

- **Patch** (1.0.1): bug fixes that change no card value.
- **Minor** (1.1.0): anything that changes card values (difficulty, time, band, contains, issues, explanations) or
  adds a feature. The card's meaning is fixed in 1.x; a value change needs a minor version and a CHANGELOG line.
- **Major** (2.0.0): a breaking change to a format (`format_version` goes up) or to the Python API, once people
  depend on them. Until then (1.x so far), breaking changes go into a minor version, without aliases, each listed
  under "Breaking" in the CHANGELOG.
- For a trial run, use a release candidate (`1.1.0rc1`): it installs only when asked for by number.

## 2. Prepare main

1. The version goes in two places: `pyproject.toml` (`version`) and `src/pencilmark/__init__.py` (`__version__`).
   Cards read it from `__version__`; the golden records leave it out, so they do not change. The reference cards in
   `tests/fixtures/variants.json` keep it: change their `"version"` too.
2. In `CHANGELOG.md`, rename "## Unreleased" to "## 1.1.0 (date)" and start a new empty "## Unreleased" above it.
3. Freeze the docs of this release: `python tools/tasks.py prepare` (the generated pages are part of a version), then
   in `website/`, `npx docusaurus docs:version 1.2` (it copies `docs/` to `versioned_docs/version-1.2` and the sidebar to
   `versioned_sidebars/`). In `website/docusaurus.config.js` set `lastVersion: '1.2'`, add `'1.2': {label: '1.2'}` to
   `versions`, and label the current docs as the next one (`'1.3-dev'`). Readers then land on the released docs; the
   version menu reaches the others, and the next release's docs stay under `/next/`.
4. Commit, then on a fresh install (`pip install -e .`) run `python tools/tasks.py release 1.1.0`. It checks that both
   version numbers say 1.1.0, that the CHANGELOG has its section and an empty "Unreleased", and that nothing is
   uncommitted; then it runs the quick suite, the doc examples, the golden check and the docs build (which fails on a
   broken link). It changes nothing; fix what it reports and run it again.
5. Push to main.

## 3. Test on every platform

Push a tag `v1.1.0`. The `tests` workflow runs the suite on Linux (oldest and newest supported Python), Windows and
macOS; the reference cards must come out identical everywhere. Fix anything that fails before going on.

## 4. Publish

Create a GitHub release from the tag, with the CHANGELOG section as its notes. Publishing it starts the `wheels`
workflow: it builds the wheels and the source distribution, smoke-tests each wheel, and uploads them to PyPI. Then
check from a clean environment:

```
pip install pencilmark==1.1.0
python -c "import pencilmark; print(pencilmark.__version__)"
```
