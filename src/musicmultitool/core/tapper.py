"""BPM tap tempo: pure math, time is passed in."""
from __future__ import annotations


class Tapper:
    def __init__(self, window: int = 8, reset_gap: float = 2.0):
        self.window, self.reset_gap = window, reset_gap
        self._taps: list[float] = []

    @property
    def count(self) -> int:
        return len(self._taps)

    def reset(self) -> None:
        self._taps = []

    def tap(self, t: float) -> float | None:
        """Register a tap at time t (seconds); returns BPM from the mean interval of the last `window` taps."""
        if self._taps and t - self._taps[-1] > self.reset_gap:
            self._taps = []
        self._taps = (self._taps + [t])[-self.window:]
        if len(self._taps) < 2:
            return None
        return 60.0 / ((self._taps[-1] - self._taps[0]) / (len(self._taps) - 1))


def relation(tapped: float, detected: float, tol: float = 0.04) -> str:
    def near(a: float, b: float) -> bool:
        return abs(a - b) <= tol * b

    if near(tapped, detected):
        return "match"
    if near(tapped, detected / 2):
        return "half"
    if near(tapped, detected * 2):
        return "double"
    return "off"
