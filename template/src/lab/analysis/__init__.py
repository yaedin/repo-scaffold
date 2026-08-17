"""Statistics and integrity checks for measured data."""

from lab.analysis.integrity import IntegrityReport, Issue, check_records
from lab.analysis.stats import (
    Interval,
    TestResult,
    bootstrap_ci,
    paired_bootstrap_ci,
    rate,
    two_proportion_ztest,
    wilson_ci,
)

__all__ = [
    "IntegrityReport",
    "Issue",
    "Interval",
    "TestResult",
    "bootstrap_ci",
    "check_records",
    "paired_bootstrap_ci",
    "rate",
    "two_proportion_ztest",
    "wilson_ci",
]
