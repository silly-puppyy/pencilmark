<!-- What changed and why, in a few lines. -->

Checks (CONTRIBUTING.md):

- [ ] `python -m pytest -q -n auto tests` passes
- [ ] `python tools/golden.py check`: every record identical, or the differences are intended, described here, and
      the rewritten records are in their own commit
- [ ] a line under "Unreleased" in `CHANGELOG.md` if a card or a format changes
