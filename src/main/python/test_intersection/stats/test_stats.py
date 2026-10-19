from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from test_intersection.test_events import TestCase
from stats.stats_hist import build_cdf
import globals as g

@dataclass
class ThreadStats:
    total: int = 0
    failed: int = 0
    total_time: timedelta = timedelta()
    min_duration: timedelta | None = None
    max_duration: timedelta | None = None
    durations: list[float] = field(default_factory=list)
    first_start: datetime | None = None
    last_end: datetime | None = None

    def add(self, tc: TestCase) -> None:
        self.total += 1
        if _is_failed(tc.result):
            self.failed += 1
        self.total_time += tc.duration
        if self.min_duration is None or tc.duration < self.min_duration:
            self.min_duration = tc.duration
        if self.max_duration is None or tc.duration > self.max_duration:
            self.max_duration = tc.duration
        self.durations.append(tc.duration.total_seconds())
        if self.first_start is None or tc.start_time < self.first_start:
            self.first_start = tc.start_time
        if self.last_end is None or tc.end_time > self.last_end:
            self.last_end = tc.end_time

    @property
    def wall_clock(self) -> timedelta:
        if not self.first_start or not self.last_end:
            return timedelta()
        return self.last_end - self.first_start

    def mean_seconds(self) -> float:
        return self.total_time.total_seconds() / self.total if self.total else 0.0

    def median_seconds(self) -> float:
        return statistics.median(self.durations) if self.durations else 0.0


def _is_failed(result: str | None) -> bool:
    """FAILED / FAILURE / ERROR → True."""
    if not result:
        return False
    r = result.upper()
    return r in ("FAILED", "FAILURE", "ERROR")


@dataclass
class TestStats:
    total: int = 0
    by_result: Counter = field(default_factory=Counter)
    durations: list[float] = field(default_factory=list)
    thread_stat_by_thread_name: dict[str, ThreadStats] = field(
        default_factory=lambda: defaultdict(ThreadStats)
    )

    # ---- глобальный wall-clock по всем тестам ----
    first_start: datetime | None = None
    last_end: datetime | None = None

    def add(self, tc: TestCase) -> None:
        self.total += 1
        self.by_result[tc.result or ""] += 1
        self.durations.append(tc.duration.total_seconds())

        th = tc.thread_name or "<unknown>"
        self.thread_stat_by_thread_name[th].add(tc)

        if self.first_start is None or tc.start_time < self.first_start:
            self.first_start = tc.start_time
        if self.last_end is None or tc.end_time > self.last_end:
            self.last_end = tc.end_time

    # ---- агрегаты верхнего уровня ----

    def success_rate(self) -> float:
        if not self.total:
            return 0.0
        ok = sum(
            v for k, v in self.by_result.items()
            if k and k.upper() in ("SUCCESSFUL", "PASSED", "SUCCESS")
        )
        return ok / self.total

    def total_time(self) -> timedelta:
        """Сумма duration по всем тестам — «если бы они шли в одном потоке»."""
        return sum(
            (ts.total_time for ts in self.thread_stat_by_thread_name.values()),
            timedelta(),
        )

    def wall_clock(self) -> timedelta:
        """Wall-clock всего прогона: от первого старта до последнего конца."""
        if not self.first_start or not self.last_end:
            return timedelta()
        return self.last_end - self.first_start

    # ---- сводка по длительностям ----

    def durations_summary(self) -> dict:
        if not self.durations:
            return {}
        ds = sorted(self.durations)
        n = len(ds)

        def pct(p: float) -> float:
            if n == 1:
                return ds[0]
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            return ds[f] + (ds[c] - ds[f]) * (k - f)

        return {
            "count": n,
            "sum_s": sum(ds),
            "origin_sum_s": self.wall_clock().seconds,
            "mean_s": statistics.fmean(ds),
            "median_s": statistics.median(ds),
            "p90_s": pct(0.90),
            "p95_s": pct(0.95),
            "p99_s": pct(0.99),
            "min_s": ds[0],
            "max_s": ds[-1],
        }

def build_test_stats() -> dict:
    stats = TestStats()
    for tc in g.TEST_EVENTS:
        stats.add(tc)

    ds = stats.durations_summary()

    cdf = build_cdf(stats.durations, max_points=500)

    by_thread = []
    for name, ts in sorted(
            stats.thread_stat_by_thread_name.items(),
            key=lambda kv: kv[1].total_time,
            reverse=True,
    ):
        by_thread.append({
            "name": name,
            "total": ts.total,
            "failed": ts.failed,
            "total_time_s": ts.total_time.total_seconds(),
            "wall_s": ts.wall_clock.total_seconds(),
            "mean_s": ts.mean_seconds(),
            "median_s": ts.median_seconds(),
            "min_s": ts.min_duration.total_seconds() if ts.min_duration else 0.0,
            "max_s": ts.max_duration.total_seconds() if ts.max_duration else 0.0,
        })

    return {
        "total": stats.total,
        "success_rate": stats.success_rate(),
        "by_result": list(stats.by_result.most_common()),
        "durations_summary": ds,
        "cdf": cdf,
        "by_thread": by_thread,
    }