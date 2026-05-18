"""Render trace and timing helpers for production hardening."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, List


@dataclass
class TraceEvent:
    phase: str
    elapsed_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "metadata": self.metadata,
        }


@dataclass
class RenderTrace:
    events: List[TraceEvent] = field(default_factory=list)

    @contextmanager
    def phase(self, name: str, **metadata):
        start = perf_counter()
        try:
            yield
        finally:
            elapsed = (perf_counter() - start) * 1000
            self.events.append(TraceEvent(name, elapsed, metadata))

    def to_dict(self) -> Dict[str, Any]:
        total = sum(event.elapsed_ms for event in self.events)
        slowest = sorted(self.events, key=lambda event: event.elapsed_ms, reverse=True)[:5]
        return {
            "total_elapsed_ms": round(total, 3),
            "events": [event.to_dict() for event in self.events],
            "slowest_phases": [event.to_dict() for event in slowest],
        }
