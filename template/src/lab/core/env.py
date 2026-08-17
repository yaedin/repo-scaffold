"""Load `.env` into the process environment, with no third-party dependency.

Secrets live in `.env`, which is gitignored. `.env.example` is committed and lists
the keys without their values, so a fresh clone knows what it needs.
"""

from __future__ import annotations

import os
from pathlib import Path

from lab.core.paths import REPO_ROOT


def load(path: Path | str | None = None, *, override: bool = False) -> dict[str, str]:
    """Load key=value pairs from `.env`. Returns what was loaded.

    Existing environment variables win unless `override=True` — an explicitly
    exported variable should beat a stale file.
    """
    path = Path(path) if path else REPO_ROOT / ".env"
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if override or key not in os.environ:
            os.environ[key] = val
            loaded[key] = val
    return loaded


def require(*keys: str) -> None:
    """Fail immediately, with the full list, if any required key is missing.

    Better than discovering the third missing key after two API calls have billed.
    """
    load()
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Add them to .env (see .env.example)."
        )
