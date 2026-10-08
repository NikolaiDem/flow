from __future__ import annotations

from datetime import datetime

from event_parsing import JfrEvent
from overlaps import Overlap


# ---------- базовые утилиты ----------

def ts_to_ms(dt: datetime) -> float:
    return dt.timestamp() * 1000.0


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S.%f")[:-3]


def result_class(result: str) -> str:
    """PASSED/SUCCESS -> passed, FAILED/ERROR -> failed, иначе other."""
    r = (result or "").upper()
    if r in ("PASSED", "SUCCESS", "SUCCESSFUL"):
        return "passed"
    if r in ("FAILED", "FAILURE", "ERROR"):
        return "failed"
    return "other"


def _kind(tc) -> str:
    return getattr(tc, "kind", "event") or "event"


def test_key(tc) -> str:
    """Канонический ключ события.

    Для тестов — class_name:method_name:display_name.
    Для прочих событий — kind:thread:start_time:display_name,
    чтобы повторные загрузки одного и того же контекста не схлопывались.
    """
    kind = _kind(tc)
    if kind == "test":
        return (
            f"{getattr(tc, 'class_name', '') or ''}:"
            f"{getattr(tc, 'method_name', '') or ''}:"
            f"{getattr(tc, 'display_name', '') or ''}"
        )

    st = getattr(tc, "start_time", None)
    return (
        f"{kind}:"
        f"{getattr(tc, 'thread_name', '') or ''}:"
        f"{st.isoformat() if st else ''}:"
        f"{getattr(tc, 'display_name', '') or ''}"
    )


def make_ticks(
        axis_start_ms: float,
        axis_end_ms: float,
        n: int = 10,
        fmt: str = "%H:%M:%S",
) -> list[dict]:
    """n+1 равномерных вертикальных засечек на оси.

    Каждая: {"left": <процент 0..100>, "label": "ЧЧ:ММ:СС"}.
    """
    span = max(axis_end_ms - axis_start_ms, 1.0)
    ticks: list[dict] = []
    for i in range(n + 1):
        frac = i / n
        left = frac * 100.0
        t_ms = axis_start_ms + frac * span
        dt = datetime.fromtimestamp(t_ms / 1000.0)
        ticks.append({
            "left": round(left, 3),
            "label": dt.strftime(fmt),
        })
    return ticks


# ---------- построение строк таймлайна ----------

def _row_cls(tc) -> str:
    """CSS-класс бара по kind и result."""
    kind = _kind(tc)
    if kind == "test":
        return result_class(getattr(tc, "result", "") or "")
    if kind == "context":
        return "context"
    if kind == "setup":
        return "setup"
    if kind == "teardown":
        return "teardown"
    return "other"


def _row_title(tc, extra_title: str = "") -> str:
    cls_name = getattr(tc, "class_name", "") or ""
    mth_name = getattr(tc, "method_name", "") or ""
    result = getattr(tc, "result", "") or ""

    parts = []
    if cls_name and mth_name:
        parts.append(f"{cls_name}.{mth_name}")
    parts.append(f"({tc.display_name})")
    parts.append(f"[{tc.thread_name}]")
    parts.append(f"kind={_kind(tc)}")
    if result:
        parts.append(f"result={result}")
    parts.append(f"{tc.duration.total_seconds() * 1000:.1f} ms")

    title = " ".join(parts)
    if extra_title:
        title += f" — {extra_title}"
    return title


def make_row(
        tc,
        axis_start_ms: float,
        axis_end_ms: float,
        extra_cls: str = "",
        extra_title: str = "",
) -> dict:
    span = max(axis_end_ms - axis_start_ms, 1.0)
    left = (ts_to_ms(tc.start_time) - axis_start_ms) / span * 100.0
    right = (ts_to_ms(tc.end_time) - axis_start_ms) / span * 100.0
    cls = f"{_row_cls(tc)} {extra_cls}".strip()

    return {
        "key": test_key(tc),
        "kind": _kind(tc),
        "name": tc.display_name,
        "class_name": getattr(tc, "class_name", "") or "",
        "method_name": getattr(tc, "method_name", "") or "",
        "thread": tc.thread_name,
        "result": getattr(tc, "result", "") or "",
        "cls": cls,
        "left": round(left, 3),
        "width": round(max(right - left, 0.4), 3),
        "title": _row_title(tc, extra_title),
    }


def build_timeline(
        main: JfrEvent,
        partners: list[Overlap],
        axis_start_ms: float,
        axis_end_ms: float,
) -> list[dict]:
    """Таймлайн для одиночного поиска: главное событие + его пересечения."""
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


# ---------- уникальность и группы ----------

def all_unique_events(all_events: list) -> list:
    """Возвращает список уникальных событий (по test_key)."""
    seen: set[str] = set()
    result: list = []
    for tc in all_events:
        k = test_key(tc)
        if k not in seen:
            seen.add(k)
            result.append(tc)
    return result


def build_group_timeline_by_keys(
        keys: list[str],
        all_events: list,
        global_min: datetime | None,
        global_max: datetime | None,
) -> dict:
    """Строит таймлайн для группы событий, идентифицированных ключами test_key."""
    if not keys or global_min is None or global_max is None:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    axis_start = ts_to_ms(global_min)
    axis_end = ts_to_ms(global_max)

    wanted = set(keys)
    by_key = {test_key(tc): tc for tc in all_unique_events(all_events)}
    events_to_show = [by_key[k] for k in wanted if k in by_key]
    events_to_show.sort(key=lambda t: t.start_time)

    rows = [make_row(tc, axis_start, axis_end) for tc in events_to_show]

    return {
        "rows": rows,
        "axis_start": fmt_dt(global_min),
        "axis_end": fmt_dt(global_max),
        "ticks": make_ticks(axis_start, axis_end, n=10),
    }