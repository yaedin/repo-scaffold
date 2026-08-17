"""Fill in project metadata across the repo. Run once, right after copying the template.

    just init --name my-project --title "My Project" --description "One sentence."

Or run it bare for interactive prompts:

    just init

The package stays named `lab` forever — deliberately. Renaming the package on
every new project means every import path churns, every code example in AGENTS.md
goes stale, and muscle memory resets. `from lab.core import ...` works identically
in every project you will ever start from this template.

The placeholder strings this replaces are also what `publish-check` looks for, so
a repo that was never initialised cannot be accidentally published.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_NAME = "scaffold-project"
PLACEHOLDER_TITLE = "Untitled Research Project"
PLACEHOLDER_DESC = "A research project. Replace this line via `just init`."
PLACEHOLDER_AUTHOR = "Yasin Edin"

# Files that carry project identity. Missing files are skipped, not fatal.
TARGETS = [
    "README.md",
    "AGENTS.md",
    "CLAIMS.md",
    "CITATION.cff",
    "LICENSE",
    "pyproject.toml",
    "writeup/paper.md",
    "docs/index.md",
]


def prompt(label: str, default: str) -> str:
    got = input(f"{label} [{default}]: ").strip()
    return got or default


def slugify(title: str) -> str:
    return "-".join("".join(c if c.isalnum() or c in " -" else "" for c in title).split()).lower()


def main() -> int:
    ap = argparse.ArgumentParser(description="Initialise project metadata.")
    ap.add_argument("--name", help="package/repo slug, e.g. secret-loyalties")
    ap.add_argument("--title", help='human title, e.g. "Detectable but Not Attributable"')
    ap.add_argument("--description", help="one sentence, used in pyproject and CITATION")
    ap.add_argument("--author", help="your name as it should appear in citations")
    ap.add_argument("--yes", action="store_true", help="skip confirmation")
    args = ap.parse_args()

    interactive = not any([args.name, args.title, args.description])
    title = args.title or (
        prompt("Project title", PLACEHOLDER_TITLE) if interactive else PLACEHOLDER_TITLE
    )
    name = args.name or (prompt("Repo slug", slugify(title)) if interactive else slugify(title))
    description = args.description or (
        prompt("One-sentence description", PLACEHOLDER_DESC) if interactive else PLACEHOLDER_DESC
    )
    author = args.author or (
        prompt("Author", PLACEHOLDER_AUTHOR) if interactive else PLACEHOLDER_AUTHOR
    )

    replacements = {
        PLACEHOLDER_NAME: name,
        PLACEHOLDER_TITLE: title,
        PLACEHOLDER_DESC: description,
        PLACEHOLDER_AUTHOR: author,
        "{{YEAR}}": str(datetime.date.today().year),
        "{{DATE}}": datetime.date.today().isoformat(),
    }

    print("\nWill apply:")
    for k, v in replacements.items():
        if k != v:
            print(f"  {k!r} -> {v!r}")

    if not args.yes and interactive and input("\nProceed? [Y/n]: ").strip().lower() in {"n", "no"}:
        print("aborted.")
        return 1

    touched = []
    for rel in TARGETS:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = original = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            touched.append(rel)

    print(f"\ninit: updated {len(touched)} file(s): {', '.join(touched) or 'none'}")
    print("init: the Python package stays `lab` — imports never change between projects.")
    print("init: next steps ->  just verify   then write experiments/e01_<your-question>/spec.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
