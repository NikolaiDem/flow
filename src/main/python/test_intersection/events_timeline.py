from __future__ import annotations

from datetime import datetime

from event_parsing import JfrEvent
from overlaps import Overlap

from timeline_common import (
    fmt_dt,
    make_ticks,
    ts_to_ms,
)


# ---------- ключ ----------

def event_key(tc: JfrEvent) -> str:
    """Канонический ключ события.

    event_type:thread:start_time:display_name — уникален для любого JFR-события,
    включая тесты и повторные загрузки Spring-контекста.
    """
    return (
        f"{tc.event_type or ''}:"
        f"{tc.thread_name or ''}:"
        f"{tc.start_time.isoformat()}:"
        f"{tc.display_name or ''}"
    )


def event_class(tc: JfrEvent) -> str:
    """CSS-класс бара по типу JFR-события.

    Здесь нет разделения на passed/failed — этот таймлайн нейтральный
    и показывает всё, что есть в ALL_EVENTS.
    """
    t = (tc.event_type or "").lower()
    if "springframework" in t:
        return "context"
    if "testexecution" in t or t.startswith("org.junit"):
        return "test-event"
    return "event"


# ---------- строка таймлайна ----------

def _row_title(tc: JfrEvent, extra_title: str = "") -> str:
    parts = [f"({tc.display_name})"]
    if tc.thread_name:
        parts.append(f"[{tc.thread_name}]")
    if tc.event_type:
        parts.append(f"type={tc.event_type}")
    parts.append(f"{tc.duration.total_seconds() * 1000:.1f} ms")

    title = " ".join(parts)
    if extra_title:
        title += f" — {extra_title}"
    return title


def make_row(
        tc: JfrEvent,
        axis_start_ms: float,
        axis_end_ms: float,
        extra_cls: str = "",
        extra_title: str = "",
) -> dict:
    """Одна строка таймлайна события."""
    span = max(axis_end_ms - axis_start_ms, 1.0)
    left = (ts_to_ms(tc.start_time) - axis_start_ms) / span * 100.0
    right = (ts_to_ms(tc.end_time) - axis_start_ms) / span * 100.0
    cls = f"{event_class(tc)} {extra_cls}".strip()

    return {
        "key": event_key(tc),
        "name": tc.display_name,
        "display_name": tc.display_name,
        "thread": tc.thread_name,
        "event_type": tc.event_type,
        "cls": cls,
        "left": round(left, 3),
        "width": round(max(right - left, 0.4), 3),
        "title": _row_title(tc, extra_title),
    }


# ---------- таймлайн одиночного поиска ----------

def build_timeline(
        main: JfrEvent,
        partners: list[Overlap],
        axis_start_ms: float,
        axis_end_ms: float,
) -> list[dict]:
    """Таймлайн для одиночного события: главное + его пересечения.

    Все партнёры — JfrEvent (гарантируется вызывающей стороной).
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
        events: list[JfrEvent],
        global_min: datetime | None,
        global_max: datetime | None,
) -> dict:
    """Таймлайн для группы событий, идентифицированных event_key."""
    if not keys or global_min is None or global_max is None:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    axis_start = ts_to_ms(global_min)
    axis_end = ts_to_ms(global_max)

    wanted = set(keys)
    events_to_show = [e for e in events if event_key(e) in wanted]
    events_to_show.sort(key=lambda t: t.start_time)

    rows = [make_row(tc, axis_start, axis_end) for tc in events_to_show]

    return {
        "rows": rows,
        "axis_start": fmt_dt(global_min),
        "axis_end": fmt_dt(global_max),
        "ticks": make_ticks(axis_start, axis_end, n=10),
    }