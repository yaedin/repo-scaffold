"""Proportion statistics, implemented directly so the scaffold stays dependency-light.

Everything here is closed-form or numpy-only — no scipy, no statsmodels. That
keeps `uv sync` fast and CI free, and these are the only tests most measurement
work actually needs:

    rate + Wilson CI          for every proportion you report
    two_proportion_ztest      for arm vs control
    bootstrap_ci              for a mean when you cannot assume normality
    paired_bootstrap_ci       for per-unit differences measured on the same unit

Report a rate without an interval and you have reported a number that cannot be
argued with. Overlapping intervals are not an effect; a tight non-overlap is.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

NAN = float("nan")


def _z_critical(alpha: float) -> float:
    """Two-sided normal critical value. 1.959964 at alpha=0.05."""
    # Inverse normal CDF via the Acklam rational approximation; accurate to ~1e-9,
    # far beyond what any experiment's sample size justifies.
    p = 1.0 - alpha / 2.0
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )  # noqa: E501
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )  # noqa: E501
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )  # noqa: E501


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def rate(successes: int, n: int) -> float:
    """Point estimate. NaN rather than ZeroDivisionError on an empty cell."""
    return successes / n if n else NAN


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float
    n: int

    def __str__(self) -> str:
        if self.n == 0:
            return "n/a (n=0)"
        return f"{self.point:.1%} [{self.lo:.1%}, {self.hi:.1%}] (n={self.n})"

    def overlaps(self, other: Interval) -> bool:
        """Crude but honest: overlapping CIs are not evidence of a difference."""
        return not (self.hi < other.lo or other.hi < self.lo)


def wilson_ci(successes: int, n: int, alpha: float = 0.05) -> Interval:
    """Wilson score interval for a proportion.

    Preferred over the normal approximation because it stays inside [0, 1] and
    behaves near 0 and 1 — which is exactly where refusal and fire rates live.
    """
    if n == 0:
        return Interval(NAN, NAN, NAN, 0)
    z = _z_critical(alpha)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return Interval(p, max(0.0, center - half), min(1.0, center + half), n)


@dataclass(frozen=True)
class TestResult:
    delta: float
    z: float
    p_value: float
    n1: int
    n2: int

    def __str__(self) -> str:
        return f"Δ={self.delta:+.1%}, z={self.z:.2f}, p={self.p_value:.2g}"

    def significant(self, alpha: float = 0.05) -> bool:
        return self.p_value < alpha


def two_proportion_ztest(k1: int, n1: int, k2: int, n2: int) -> TestResult:
    """Pooled two-sided z-test for p1 - p2. Arm 1 is the treatment, arm 2 the control.

    For exploratory work where you have run many comparisons, hold yourself to a
    stricter threshold than 0.05 and say in the report how many tests you ran.
    """
    if n1 == 0 or n2 == 0:
        return TestResult(NAN, NAN, NAN, n1, n2)
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        # Both arms are 0/0 or 1/1: no variance, so no test to run.
        return TestResult(p1 - p2, NAN, NAN if p1 == p2 else 0.0, n1, n2)
    z = (p1 - p2) / se
    return TestResult(p1 - p2, z, 2 * (1 - _normal_cdf(abs(z))), n1, n2)


def bootstrap_ci(
    values: Sequence[float], alpha: float = 0.05, n_boot: int = 10_000, seed: int = 0
) -> Interval:
    """Percentile bootstrap CI for the mean. Use when the quantity is not a proportion."""
    import numpy as np

    v = np.asarray([x for x in values if x == x], dtype=float)
    if v.size < 2:
        return Interval(NAN, NAN, NAN, int(v.size))
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n_boot, v.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return Interval(float(v.mean()), float(lo), float(hi), int(v.size))


def paired_bootstrap_ci(
    deltas: Sequence[float], alpha: float = 0.05, n_boot: int = 10_000, seed: int = 0
) -> Interval:
    """CI for the mean of paired per-unit differences.

    Use this whenever the two quantities were measured on the *same* unit — the
    same prompt, the same item, the same subject. Treating paired measurements as
    two independent samples inflates the variance and buries real effects.
    """
    return bootstrap_ci(deltas, alpha=alpha, n_boot=n_boot, seed=seed)
