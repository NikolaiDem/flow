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


def build_cdf(
        durations: list[float],
        max_points: int = 500,
) -> list[dict]:
    """Кумулятивная функция распределения длительностей.

    Возвращает список точек, отсортированных по t (возрастание):
      [{"t": секунды, "count": N, "pct": проценты}, ...]

    Первая точка — t=0, count=0. Последняя — t=max, count=len(durations).

    max_points — прореживание, чтобы не гнать в браузер 100k точек.
    """
    if not durations:
        return []

    ds = sorted(durations)
    n = len(ds)
    max_t = ds[-1]

    # Точки: начало, конец и прореженные промежуточные.
    # Если точек меньше max_points — берём все.
    if n <= max_points:
        step = 1
    else:
        step = max(1, n // max_points)

    points = [{"t": 0.0, "count": 0, "pct": 0.0}]

    # Идём по отсортированным длительностям и берём каждую step-ю.
    # count = индекс + 1 (сколько тестов ≤ текущей длительности).
    for i in range(0, n, step):
        t = ds[i]
        count = i + 1
        points.append({
            "t": t,
            "count": count,
            "pct": round(count / n * 100.0, 4),
        })

    # Гарантируем, что последняя точка = max_t, count = n.
    if points[-1]["t"] != max_t or points[-1]["count"] != n:
        points.append({
            "t": max_t,
            "count": n,
            "pct": 100.0,
        })

    return points