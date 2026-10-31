# Security

## Reporting a problem

Report a security problem privately: on GitHub, open the repository's **Security** tab and choose **Report a
vulnerability** ([direct link](https://github.com/silly-puppyy/pencilmark/security/advisories/new)). Only the
maintainers see the report. Please do not open a public issue for it.

Say what you found, how to reproduce it (a puzzle file or link helps), and which version (`pencilmark.__version__`).
You will get an answer in the report thread; a fix is released as a new version with a note in the changelog.

## What counts

pencilmark reads puzzle files and links from anywhere, so a problem in reading untrusted input is a security problem:
a file or link that crashes the process, hangs it without the time limits stopping it, uses unbounded memory, or makes
pencilmark fetch something other than the puzzle the link names. Wrong grades and wrong explanations are ordinary bugs;
report those as issues.

## Supported versions

The latest release on PyPI. Fixes are not backported to older versions.
