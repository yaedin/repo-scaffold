"""Determinism helpers.

An unseeded run is not an experiment, it is an anecdote you cannot repeat. Call
`seed_all(n)` once at the top of every `run.py`, and record the value in the
manifest so the number in your report is traceable to the draw that produced it.

`seed_all` seeds whatever is installed. It never imports torch just to seed it.
"""

from __future__ import annotations

import os
import random

DEFAULT_SEED = 0


def seed_all(seed: int = DEFAULT_SEED, *, deterministic_torch: bool = True) -> int:
    """Seed every RNG that is actually present. Returns the seed, for the manifest.

    `deterministic_torch=True` also disables cuDNN autotuning, which trades some
    throughput for run-to-run reproducibility on GPU. Turn it off only if you have
    measured that it matters and you have said so in your report.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch
    except ImportError:
        return seed

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic_torch:
        # Documented tradeoff: slower, but the same input gives the same output.
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    return seed


def spawn(seed: int, *, index: int) -> int:
    """Derive an independent child seed for arm/replicate `index`.

    Use this instead of `seed + index`: sequential seeds produce correlated first
    draws in some generators, which silently couples arms that must be independent.
    """
    import numpy as np

    return int(np.random.SeedSequence([seed, index]).generate_state(1)[0])
