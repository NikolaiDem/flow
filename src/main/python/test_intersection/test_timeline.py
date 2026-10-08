from __future__ import annotations

from datetime import datetime

from overlaps import Overlap
from test_events import TestCase

from timeline_common import (
    fmt_dt,
    make_ticks,
    ts_to_ms,
)


# ---------- ключ ----------

def test_key(tc: TestCase) -> str:
    """Канонический ключ теста. Поле name гарантированно уникально."""
    return tc.name


def result_class(result: str) -> str:
    """PASSED/SUCCESS -> passed, FAILED/ERROR -> failed, иначе other."""
    r = (result or "").upper()
    if r in ("PASSED", "SUCCESS", "SUCCESSFUL"):
        return "passed"
    if r in ("FAILED", "FAILURE", "ERROR"):
        return "failed"
    return "other"


# ---------- строка таймлайна ----------

def _row_title(tc: TestCase, extra_title: str = "") -> str:
    parts = []
    if tc.class_name and tc.method_name:
        parts.append(f"{tc.class_name}.{tc.method_name}")
    parts.append(f"({tc.display_name})")
    parts.append(f"[{tc.thread_name}]")
    if tc.result:
        parts.append(f"result={tc.result}")
    parts.append(f"{tc.duration.total_seconds() * 1000:.1f} ms")

    title = " ".join(parts)
    if extra_title:
        title += f" — {extra_title}"
    return title


def make_row(
        tc: TestCase,
        axis_start_ms: float,
        axis_end_ms: float,
        extra_cls: str = "",
        extra_title: str = "",
) -> dict:
    """Одна строка таймлайна: позиция, ширина, цвет, tooltip."""
    span = max(axis_end_ms - axis_start_ms, 1.0)
    left = (ts_to_ms(tc.start_time) - axis_start_ms) / span * 100.0
    right = (ts_to_ms(tc.end_time) - axis_start_ms) / span * 100.0
    cls = f"{result_class(tc.result)} {extra_cls}".strip()

    return {
        "key": tc.name,
        "name": tc.name,
        "display_name": tc.display_name,
        "class_name": tc.class_name,
        "method_name": tc.method_name,
        "thread": tc.thread_name,
        "result": tc.result,
        "cls": cls,
        "left": round(left, 3),
        "width": round(max(right - left, 0.4), 3),
        "title": _row_title(tc, extra_title),
    }


# ---------- таймлайн одиночного поиска ----------

def build_timeline(
        main: TestCase,
        partners: list[Overlap],
        axis_start_ms: float,
        axis_end_ms: float,
) -> list[dict]:
    """Таймлайн для одиночного поиска: искомый тест + его пересечения.

    Все партнёры — TestCase (гарантируется вызывающей стороной).
    """
    rows: list[dict] = [
        make_row(main, axis_start_ms, axis_end_ms, extra_cls="highlight")
    ]
    for ov in partners:
        rows.append(make_row(
            ov.other,
            axis_start_ms,
            axis_end_ms,
            extra_title=f"пересечение {ov.intersection_ms:.1f} ms",
        ))
    return rows


# ---------- групповой таймлайн ----------

def build_group_timeline_by_keys(
        keys: list[str],
        tests: list[TestCase],
        global_min: datetime | None,
        global_max: datetime | None,
) -> dict:
    """Таймлайн для группы тестов, идентифицированных именами (test_key)."""
    if not keys or global_min is None or global_max is None:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    axis_start = ts_to_ms(global_min)
    axis_end = ts_to_ms(global_max)

    wanted = set(keys)
    tests_to_show = [tc for tc in tests if tc.name in wanted]
    tests_to_show.sort(key=lambda t: t.start_time)

    rows = [make_row(tc, axis_start, axis_end) for tc in tests_to_show]

    return {
        "rows": rows,
        "axis_start": fmt_dt(global_min),
        "axis_end": fmt_dt(global_max),
        "ticks": make_ticks(axis_start, axis_end, n=10),
    }