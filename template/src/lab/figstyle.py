"""One figure style, applied everywhere, so figures look like a paper.

Matplotlib's defaults are recognisable as defaults: DejaVu Sans, heavy gridlines,
the tab10 palette, raster output. A reader who has seen a hundred plots reads that
combination as "script output" rather than "figure", which costs credibility the
underlying analysis has already earned. Every figure in the sprint that produced
this scaffold shipped in default tab10 blue/orange, and it was the cheapest
avoidable weakness in the submission.

Four decisions worth stating, because each one is a question you would otherwise
re-answer per figure:

**Vector, not raster.** Every figure is written as PDF *and* PNG. The PDF belongs
in the paper — text stays selectable and lines stay sharp at any zoom. The PNG
exists because README files and web pages cannot embed a PDF. Writing both, always,
removes the moment where you need one and have the other.

**Okabe-Ito, not tab10.** The default blue/orange pair is hard to separate for the
~4% of readers with deuteranopia. Okabe-Ito is designed for colour-vision
deficiency.

**Colour paired with marker shape.** Colour alone is a single point of failure:
greyscale printing, a projector with the contrast wrong, a reader who cannot
distinguish the hues. `series()` hands out a colour and a distinct marker together
so the figure degrades gracefully instead of becoming unreadable.

**Size in inches, matched to the column.** A figure scaled down by the layout
engine gets illegible axis labels. Author at final width, so 8pt here is 8pt on
the page.

Usage:

    from lab import figstyle

    plt = figstyle.use()
    fig, ax = plt.subplots(figsize=(figstyle.WIDTH_HALF, 2.4))
    colour, marker = figstyle.series(0)
    ax.plot(xs, ys, color=colour, marker=marker)
    figstyle.save(fig, figstyle.FIGURES_DIR, "e00_smoke_rates")
"""

from __future__ import annotations

from pathlib import Path

from lab.core.paths import FIGURES_DIR

__all__ = [
    "FIGURES_DIR",
    "OKABE_ITO",
    "SERIES",
    "WIDTH_FULL",
    "WIDTH_HALF",
    "save",
    "series",
    "use",
]

# Okabe-Ito, colour-vision-deficiency safe. Named by hue for lookup, but reach for
# `series()` rather than naming a colour directly — that is what keeps a figure
# consistent when someone adds a fourth line to it later.
OKABE_ITO = {
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "green": "#009E73",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "purple": "#CC79A7",
    "yellow": "#F0E442",
    "black": "#000000",
}

#: Ordered (colour, marker) pairs. Order is deliberate: the first two are the
#: most distinguishable pair in the palette, because most figures have two series.
SERIES: list[tuple[str, str]] = [
    (OKABE_ITO["blue"], "o"),
    (OKABE_ITO["vermillion"], "s"),
    (OKABE_ITO["green"], "^"),
    (OKABE_ITO["orange"], "D"),
    (OKABE_ITO["purple"], "v"),
    (OKABE_ITO["sky"], "P"),
    (OKABE_ITO["black"], "X"),
]

#: Full text width and a half-width panel, in inches.
WIDTH_FULL = 6.5
WIDTH_HALF = 3.25

RC = {
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.7,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#DDDDDD",
    "grid.linewidth": 0.5,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "lines.linewidth": 1.2,
    "lines.markersize": 4,
    "legend.frameon": False,
    "pdf.fonttype": 42,  # embed TrueType, so text stays selectable and editable
    "ps.fonttype": 42,
}


def series(index: int) -> tuple[str, str]:
    """The (colour, marker) pair for series `index`. Wraps around past the end."""
    return SERIES[index % len(SERIES)]


def use():
    """Apply the house style and return the pyplot module.

    Selects the Agg backend before importing pyplot, so figures render on a CI
    runner with no display. Call once, before creating any figure.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(RC)
    return plt


def save(fig, figdir: Path, stem: str) -> list[Path]:
    """Write `stem` as both PDF (for the paper) and PNG (for the web).

    Returns the paths written, so callers can log exactly what they produced
    rather than asserting it.
    """
    figdir = Path(figdir)
    figdir.mkdir(parents=True, exist_ok=True)
    written = []
    for ext in ("pdf", "png"):
        path = figdir / f"{stem}.{ext}"
        fig.savefig(path)
        written.append(path)
    return written
