"""Reusable machinery for this repo's experiments.

`lab.core`     — plumbing every experiment needs: paths, seeds, manifests, records, env.
`lab.analysis` — statistics and data-integrity checks.
`lab.check`    — the linter that keeps CLAIMS.md and AGENTS.md honest.

Nothing in here is project-specific. Project-specific code belongs in
`experiments/<name>/`. If a helper proves useful in a second experiment, that is
the signal to move it here.
"""

__version__ = "0.1.0"

# Windows defaults stdout to the locale codepage (cp1252), which cannot encode the
# characters research reports are actually written in — Δ, ×, ℓ, ≈. A `print` of
# "Δ=+14.4%" then raises UnicodeEncodeError and takes the whole run down. This is
# not hypothetical: it is how the three-OS CI matrix earned its keep.
#
# Reconfiguring here covers every entry point that imports `lab`. Entry points
# that do not are covered by PYTHONIOENCODING/PYTHONUTF8 in the CI workflow, and
# the file-writing half is covered by passing encoding="utf-8" at every call site
# (ruff PLW1514 catches the ones it can infer; see pyproject.toml for its limits).
import sys as _sys

for _stream in (_sys.stdout, _sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (ValueError, OSError):  # detached or already-wrapped stream
            pass
