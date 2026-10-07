from __future__ import annotations

from datetime import datetime

from event_parsing import TestCase
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


def test_key(tc) -> str:
    """Канонический ключ теста: class_name:method_name:display_name."""
    return (
        f"{getattr(tc, 'class_name', '') or ''}:"
        f"{getattr(tc, 'method_name', '') or ''}:"
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
    cls = f"{result_class(tc.result)} {extra_cls}".strip()

    cls_name = getattr(tc, "class_name", "") or ""
    mth_name = getattr(tc, "method_name", "") or ""

    title = (
        f"{cls_name}.{mth_name} "
        f"({tc.display_name}) "
        f"[{tc.thread_name}] "
        f"result={tc.result} "
        f"{tc.duration.total_seconds() * 1000:.1f} ms"
    )
    if extra_title:
        title += f" — {extra_title}"

    return {
        "key": test_key(tc),
        "name": tc.display_name,
        "class_name": cls_name,
        "method_name": mth_name,
        "thread": tc.thread_name,
        "result": tc.result,
        "cls": cls,
        "left": round(left, 3),
        "width": round(max(right - left, 0.4), 3),
        "title": title,
    }


def build_timeline(
        main: TestCase,
        partners: list[Overlap],
        axis_start_ms: float,
        axis_end_ms: float,
) -> list[dict]:
    """
    Таймлайн для одиночного поиска: искомый тест + его пересечения.
    """
    rows: list[dict] = [make_row(main, axis_start_ms, axis_end_ms, extra_cls="highlight")]

    for ov in partners:
        rows.append(make_row(
            ov.other,
            axis_start_ms,
            axis_end_ms,
            extra_title=f"пересечение {ov.intersection_ms:.1f} ms",
        ))
    return rows


# ---------- уникальность и группы ----------

def all_unique_tests(all_events: list) -> list:
    """Возвращает список уникальных тестов (по class_name:method_name:display_name)."""
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
    """Строит таймлайн для группы тестов, идентифицированных ключами test_key."""
    if not keys or global_min is None or global_max is None:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    axis_start = ts_to_ms(global_min)
    axis_end = ts_to_ms(global_max)

    wanted = set(keys)
    by_key = {test_key(tc): tc for tc in all_unique_tests(all_events)}
    tests_to_show = [by_key[k] for k in wanted if k in by_key]
    tests_to_show.sort(key=lambda t: t.start_time)

    rows = [make_row(tc, axis_start, axis_end) for tc in tests_to_show]

    return {
        "rows": rows,
        "axis_start": fmt_dt(global_min),
        "axis_end": fmt_dt(global_max),
        "ticks": make_ticks(axis_start, axis_end, n=10),
    }