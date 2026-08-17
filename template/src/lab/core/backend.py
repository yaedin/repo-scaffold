"""Where measurements come from, declared explicitly.

Every experiment runs against a *backend*: the thing that produces measurements.
A stub backend is deterministic, free, offline and instant. A real backend costs
money and time. The scaffold makes three things true about this distinction:

1. **Stub is the default.** Building the synthetic path first is not advice you
   have to remember; it is the path of least resistance. Analysis bugs surface in
   seconds instead of after a GPU bill.
2. **The backend stamps every record it produces.** Provenance is written at the
   point of measurement, so it survives any execution path — including ones that
   bypass `run.py` entirely, such as a remote job launcher.
3. **Nothing downstream has to trust a human.** `check_records` derives what
   produced the data from the data itself and refuses to proceed when the records
   disagree with the manifest.

Point 2 is the important one. Provenance asserted by the writer is a comment.
Provenance derived from the artifact is a fact. A manifest that says `stub` while
the records came from a 7B model is worse than no manifest, because every number
downstream inherits the mistake without anything crashing.

Real backends belong to the project, not the scaffold: subclass `Backend`, put it
in your experiment, and register it. The scaffold deliberately ships no client for
any provider — those disagree about everything and a wrong abstraction here is how
a template rots.
"""

from __future__ import annotations

from typing import Any

# Fields every record carries so its origin can be reconstructed without a manifest.
PROVENANCE_FIELDS = ("backend", "model_id", "dtype")


class Backend:
    """Base class. Subclass it, set the identity fields, implement `generate`."""

    name: str = "abstract"
    model_id: str = "none"
    dtype: str = "none"

    #: False for anything that costs money, time, or leaves the machine. Numbers
    #: from a non-reportable backend are leads, never results.
    reportable: bool = False

    def stamp(self) -> dict[str, Any]:
        """The provenance dict merged into every record this backend produces."""
        return {"backend": self.name, "model_id": self.model_id, "dtype": self.dtype}

    def describe(self) -> dict[str, Any]:
        """Everything worth recording in the manifest about this backend."""
        return {**self.stamp(), "reportable": self.reportable}

    def generate(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, model_id={self.model_id!r})"


class StubBackend(Backend):
    """Deterministic, offline, free. The default, and what CI runs.

    Subclass it per experiment to return whatever shape your real backend returns.
    The point is that the analysis path is fully exercised before anything is
    spent, so a bug in `analyze.py` costs seconds rather than a GPU-hour.
    """

    name = "stub"
    model_id = "stub"
    dtype = "none"
    reportable = False


_REGISTRY: dict[str, type[Backend]] = {"stub": StubBackend}


def register(backend_cls: type[Backend]) -> type[Backend]:
    """Register a project-defined backend. Usable as a decorator."""
    _REGISTRY[backend_cls.name] = backend_cls
    return backend_cls


def resolve(name: str) -> Backend:
    """Instantiate a registered backend by name.

    Experiments take `--backend` and pass it here, so switching between the stub
    and the real thing is a flag rather than an edit.
    """
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown backend {name!r}. Registered: {known}")
    return _REGISTRY[name]()


def available() -> list[str]:
    return sorted(_REGISTRY)
