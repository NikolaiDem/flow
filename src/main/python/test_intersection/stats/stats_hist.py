from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class HistogramBin:
    lo: float
    hi: float
    count: int


def build_linear_histogram(durations: list[float], bins: int = 30) -> list[HistogramBin]:
    if not durations:
        return []
    lo, hi = min(durations), max(durations)
    if hi == lo:
        return [HistogramBin(lo, hi, len(durations))]
    step = (hi - lo) / bins
    edges = [lo + step * i for i in range(bins + 1)]
    counts = [0] * bins
    for d in durations:
        idx = int((d - lo) / step)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1
    return [HistogramBin(edges[i], edges[i + 1], counts[i]) for i in range(bins)]


def build_log_histogram(durations: list[float], bins_per_decade: int = 4) -> list[HistogramBin]:
    positive = [d for d in durations if d > 0]
    if not positive:
        return []
    lo_exp = math.floor(math.log10(min(positive)))
    hi_exp = math.ceil(math.log10(max(positive)))
    n_bins = (hi_exp - lo_exp) * bins_per_decade
    if n_bins <= 0:
        return []
    edges = [10 ** (lo_exp + i / bins_per_decade) for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for d in positive:
        idx = int((math.log10(d) - lo_exp) * bins_per_decade)
        if idx < 0:
            idx = 0
        elif idx >= n_bins:
            idx = n_bins - 1
        counts[idx] += 1
    return [HistogramBin(edges[i], edges[i + 1], counts[i]) for i in range(n_bins)]