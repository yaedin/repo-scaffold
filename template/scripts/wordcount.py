"""Per-section prose word counts for the writeup.

INFORMATIONAL ONLY. This prints and exits 0, always. It is not part of `just
verify`, it has no configurable target, and it will never fail a build. Venues
differ, some have no limit at all, and a length checker that fails CI is a
checker you disable in week one.

It exists because section-level counts were recomputed by hand a dozen times
across five reduction passes of a sprint paper — the kind of tedious arithmetic
that is both trivial to automate and genuinely worth automating, because doing it
by hand is how you end up cutting from the wrong section.

What counts as prose: body text, headings excluded, and so are tables, figures,
captions, code blocks, HTML comments and link targets. Those are the parts you
cannot cut your way out of a length problem with, so counting them tells you
nothing about what to do next.

Run with `just wordcount`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRITEUP = REPO / "writeup"

#: A heading whose section (and everything under it) counts as appendix rather
#: than body. Most venues bound the body only.
APPENDIX_MARKERS = ("appendix", "supplementary", "supplement")


def strip_noncountable(md: str) -> str:
    """Remove everything that is not prose you could cut."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)  # comments
    md = re.sub(r"```.*?```", "", md, flags=re.DOTALL)  # fenced code
    md = re.sub(r"^\s*\|.*\|\s*$", "", md, flags=re.MULTILINE)  # table rows
    md = re.sub(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$", "", md, flags=re.MULTILINE)  # images
    # Captions: the convention build_paper.py relies on.
    md = re.sub(r"^\s*\*\*(Table|Figure)\s+\d+\.\*\*.*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)  # links -> their text
    md = re.sub(r"`[^`]*`", " ", md)  # inline code
    return md


def count_words(text: str) -> int:
    """Words a human would count: whitespace-separated tokens with a letter or digit."""
    return sum(1 for tok in text.split() if re.search(r"[A-Za-z0-9]", tok))


def sections(md: str) -> list[tuple[str, int, bool]]:
    """(heading, word count, is_appendix) for each `## ` section, in order.

    Text before the first `## ` is reported as "(front matter)" — the title block
    and anything above the abstract.
    """
    out: list[tuple[str, int, bool]] = []
    current, buf, in_appendix = "(front matter)", [], False

    for line in strip_noncountable(md).splitlines():
        if line.startswith("## "):
            out.append((current, count_words(" ".join(buf)), in_appendix))
            current = line[3:].strip()
            buf = []
            if any(m in current.lower() for m in APPENDIX_MARKERS):
                in_appendix = True
        elif line.startswith("#"):
            continue  # other headings are not prose and do not open a section
        else:
            buf.append(line)

    out.append((current, count_words(" ".join(buf)), in_appendix))
    return [s for s in out if s[1] or s[0] != "(front matter)"]


def main() -> int:
    sources = sorted(WRITEUP.glob("*.md")) if WRITEUP.exists() else []
    if not sources:
        print("wordcount: writeup/ has no Markdown source yet.")
        return 0

    for src in sources:
        rows = sections(src.read_text(encoding="utf-8"))
        print(f"\n{src.relative_to(REPO)}")
        width = max((len(name) for name, _, _ in rows), default=10)
        for name, words, is_appendix in rows:
            tag = "  (appendix)" if is_appendix else ""
            print(f"  {name:<{width}}  {words:>6}{tag}")

        body = sum(w for _, w, appendix in rows if not appendix)
        appendix = sum(w for _, w, appendix in rows if appendix)
        print(f"  {'-' * width}  {'-' * 6}")
        print(f"  {'body':<{width}}  {body:>6}")
        if appendix:
            print(f"  {'appendix':<{width}}  {appendix:>6}")
            print(f"  {'total':<{width}}  {body + appendix:>6}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
