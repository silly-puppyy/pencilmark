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
- **Major** (2.0.0): a breaking change to a format (`format_version` goes up) or to the Python API.
- For a trial run, use a release candidate (`1.1.0rc1`): it installs only when asked for by number.

## 2. Prepare main

1. The version goes in two places: `pyproject.toml` (`version`) and `src/pencilmark/__init__.py` (`__version__`).
   Cards read it from `__version__`; the golden records leave it out, so they do not change.
2. In `CHANGELOG.md`, rename "## Unreleased" to "## 1.1.0 (date)" and start a new empty "## Unreleased" above it.
3. Run the full checks on a fresh install:

   ```
   pip install -e .
   python -m pytest -q -n auto tests
   python tools/golden.py check
   ```

4. Build the docs (`npm run build` in `website/`, after `tools/gen_api_md.py` and `tools/gen_swatches.py`) and fix any
   broken link.
5. Commit and push to main.

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
