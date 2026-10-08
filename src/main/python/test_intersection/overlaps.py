from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from event_parsing import JfrEvent

log = logging.getLogger(__name__)
# --------------------------------------------------------------------------- #
# Поиск пересечений (sweep line, O(n log n))
# --------------------------------------------------------------------------- #
def find_overlaps(events: list[JfrEvent]) -> list[tuple[JfrEvent, JfrEvent]]:
    """
    Возвращает все пары событий, чьи интервалы пересекаются.

    Касание (end одного == start другого) пересечением НЕ считается.
    """
    points: list[tuple[datetime, int, int]] = []
    for i, e in enumerate(events):
        points.append((e.start_time, +1, i))  # начало
        points.append((e.end_time, -1, i))    # конец

    # При равном времени конец обрабатывается раньше начала -> касание не пересечение
    points.sort(key=lambda p: (p[0], p[1]))

    active: set[int] = set()
    overlaps: list[tuple[JfrEvent, JfrEvent]] = []

    for _, delta, i in points:
        if delta == 1:
            for j in active:
                overlaps.append((events[j], events[i]))
            active.add(i)
        else:
            active.discard(i)

    return overlaps


def calc_intersection_ms(left: JfrEvent, right: JfrEvent) -> float:
    """Длительность пересечения в миллисекундах (0.0, если пересечения нет)."""
    start = max(left.start_time, right.start_time)
    end = min(left.end_time, right.end_time)
    ms = (end - start).total_seconds() * 1000.0
    return ms if ms > 0 else 0.0


# --------------------------------------------------------------------------- #
# Построение словаря пересечений
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Overlap:
    other: JfrEvent
    intersection_ms: float


def build_overlap_dict(events: list[JfrEvent]) -> dict[JfrEvent, list[Overlap]]:
    """Для каждого JfrEvent — список пересечений, отсортированный по убыванию ms."""
    overlaps = find_overlaps(events)
    result: dict[JfrEvent, list[Overlap]] = defaultdict(list)

    for left, right in overlaps:
        ms = calc_intersection_ms(left, right)
        if ms <= 0:
            continue
        result[left].append(Overlap(other=right, intersection_ms=ms))
        result[right].append(Overlap(other=left, intersection_ms=ms))

    for name in result:
        result[name].sort(key=lambda o: o.intersection_ms, reverse=True)

    return dict(result)


