# test_handler.py
from __future__ import annotations

from collections import defaultdict

from test_intersection.timeline_common import fmt_dt, make_ticks, ts_to_ms, result_class
from test_intersection.event_parsing import JfrEvent
from test_intersection.test_events import TestCase

from test_intersection.test_timeline import (
    build_timeline as build_tests_timeline,
    test_key,
)
from test_intersection.events_timeline import (
    build_timeline as build_events_timeline,
    event_key,
    make_row as make_event_row,
)

# ---------- constants ----------

TEST_EVENT_TYPE = "org.junit.TestExecution"


# ---------- helpers ----------

def _lower(s) -> str:
    return (s or "").lower()


def _is_test(e: JfrEvent) -> bool:
    """Надёжнее, чем isinstance: не зависит от того, откуда импортирован TestCase."""
    return getattr(e, "event_type", None) == TEST_EVENT_TYPE


def _tests(ctx) -> list[TestCase]:
    """Все тесты из all_events. Вычисляется на месте — без отдельного кэша в ctx."""
    return [e for e in ctx.all_events if _is_test(e)]


def _test_brief(tc: TestCase) -> dict:
    return {
        "key": test_key(tc),
        "name": tc.name,
        "display_name": tc.display_name,
        "class_name": tc.class_name,
        "method_name": tc.method_name,
        "thread": tc.thread_name,
        "result": tc.result,
    }


def _test_matches(tc: TestCase, query: str) -> bool:
    q = query
    cls = _lower(tc.class_name)
    mth = _lower(tc.method_name)
    dsp = _lower(tc.display_name)
    nm = _lower(tc.name)
    return (q in cls or q in mth or q in dsp or q in nm or q in f"{cls}.{mth}")


def _event_brief(tc: JfrEvent) -> dict:
    return {
        "key": event_key(tc),
        "name": tc.display_name,
        "display_name": tc.display_name,
        "thread": tc.thread_name,
        "event_type": tc.event_type,
    }


def _event_matches(tc: JfrEvent, query: str) -> bool:
    q = query
    return (q in _lower(tc.display_name)
            or q in _lower(tc.event_type)
            or q in _lower(tc.thread_name))


def event_class(tc: JfrEvent) -> str:
    t = (tc.event_type or "").lower()
    if "springframework" in t:
        return "context"
    if t.startswith("org.junit"):
        result = getattr(tc, "result", "") or ""
        return result_class(result) if result else "test-event"
    if t.startswith("jdk."):
        return "jfr-system"
    return "event"


# ---------- endpoints ----------

def _all_tests(ctx) -> list[dict]:
    result = [_test_brief(tc) for tc in _tests(ctx)]
    result.sort(key=lambda x: (x["class_name"], x["method_name"], x["name"]))
    return result


def _search_tests(ctx, query: str) -> list[dict]:
    tests = _tests(ctx)
    if (not query
            or ctx.global_min is None
            or ctx.global_max is None
            or not tests):
        return []

    axis_start = ts_to_ms(ctx.global_min)
    axis_end = ts_to_ms(ctx.global_max)
    ticks = make_ticks(axis_start, axis_end, n=10)

    overlap = getattr(ctx, "overlap_dict", None) or {}

    result: list[dict] = []
    matched: set[str] = set()

    for test, partners in overlap.items():
        if not _is_test(test):
            continue
        if not _test_matches(test, query):
            continue
        matched.add(test_key(test))
        test_partners = [ov for ov in partners if _is_test(ov.other)]
        partners_json = [
            {**_test_brief(ov.other), "ms": ov.intersection_ms}
            for ov in test_partners
        ]
        rows = build_tests_timeline(test, test_partners, axis_start, axis_end)
        result.append({
            **_test_brief(test),
            "partners": partners_json,
            "rows": rows,
            "axis_start": fmt_dt(ctx.global_min),
            "axis_end": fmt_dt(ctx.global_max),
            "ticks": ticks,
        })

    for tc in tests:
        k = test_key(tc)
        if k in matched:
            continue
        if not _test_matches(tc, query):
            continue
        matched.add(k)
        rows = build_tests_timeline(tc, [], axis_start, axis_end)
        result.append({
            **_test_brief(tc),
            "partners": [],
            "rows": rows,
            "axis_start": fmt_dt(ctx.global_min),
            "axis_end": fmt_dt(ctx.global_max),
            "ticks": ticks,
        })

    result.sort(key=lambda x: (
        -sum(p["ms"] for p in x["partners"]),
        x["class_name"], x["method_name"], x["name"],
    ))
    return result[:50]


def _all_events(ctx) -> list[dict]:
    result = [_event_brief(e) for e in ctx.all_events]
    result.sort(key=lambda x: (x["event_type"], x["name"], x["thread"]))
    return result


def _search_events(ctx, query: str) -> list[dict]:
    if (not query
            or ctx.global_min is None
            or ctx.global_max is None
            or not ctx.all_events):
        return []

    axis_start = ts_to_ms(ctx.global_min)
    axis_end = ts_to_ms(ctx.global_max)
    ticks = make_ticks(axis_start, axis_end, n=10)

    overlap = getattr(ctx, "overlap_dict", None) or {}

    result: list[dict] = []
    matched: set[str] = set()

    for ev, partners in overlap.items():
        if _is_test(ev):          # тесты ищутся через _search_tests
            continue
        if not _event_matches(ev, query):
            continue
        matched.add(event_key(ev))
        partners_json = [
            {**_event_brief(ov.other), "ms": ov.intersection_ms}
            for ov in partners
        ]
        rows = build_events_timeline(ev, partners, axis_start, axis_end)
        result.append({
            **_event_brief(ev),
            "partners": partners_json,
            "rows": rows,
            "axis_start": fmt_dt(ctx.global_min),
            "axis_end": fmt_dt(ctx.global_max),
            "ticks": ticks,
        })

    for ev in ctx.all_events:
        if _is_test(ev):
            continue
        k = event_key(ev)
        if k in matched:
            continue
        if not _event_matches(ev, query):
            continue
        matched.add(k)
        rows = build_events_timeline(ev, [], axis_start, axis_end)
        result.append({
            **_event_brief(ev),
            "partners": [],
            "rows": rows,
            "axis_start": fmt_dt(ctx.global_min),
            "axis_end": fmt_dt(ctx.global_max),
            "ticks": ticks,
        })

    result.sort(key=lambda x: (
        -sum(p["ms"] for p in x["partners"]),
        x["event_type"], x["name"],
    ))
    return result[:50]


def _event_types(ctx) -> list[dict]:
    counts: dict[str, int] = {}
    for e in ctx.all_events:
        t = e.event_type or ""
        counts[t] = counts.get(t, 0) + 1
    return [{"event_type": t, "count": c} for t, c in sorted(counts.items())]


def _threads_timeline(ctx) -> dict:
    if (not ctx.all_events
            or ctx.global_min is None
            or ctx.global_max is None):
        return {
            "threads": [], "ticks": [],
            "axis_start": "", "axis_end": "",
            "axis_start_ms": 0, "axis_end_ms": 0,
        }

    axis_start = ts_to_ms(ctx.global_min)
    axis_end = ts_to_ms(ctx.global_max)
    span = max(axis_end - axis_start, 1.0)

    by_thread: dict[str, list] = defaultdict(list)
    for ev in _tests(ctx):                    # ← было ctx.test_events
        by_thread[ev.thread_name or "<unknown>"].append(ev)

    threads_data = []
    for thread_name, events in by_thread.items():
        events.sort(key=lambda e: e.start_time)
        rows = []
        for ev in events:
            left = (ts_to_ms(ev.start_time) - axis_start) / span * 100.0
            right = (ts_to_ms(ev.end_time) - axis_start) / span * 100.0
            width = max(right - left, 0.02)
            rows.append({
                "key": event_key(ev),
                "name": ev.name,
                "display_name": ev.display_name,
                "event_type": ev.event_type,
                "left": round(left, 4),
                "width": round(width, 4),
                "cls": event_class(ev),
            })
        threads_data.append({
            "name": thread_name,
            "count": len(rows),
            "events": rows,
        })

    threads_data.sort(key=lambda t: -t["count"])

    return {
        "axis_start_ms": axis_start,
        "axis_end_ms": axis_end,
        "axis_start": fmt_dt(ctx.global_min),
        "axis_end": fmt_dt(ctx.global_max),
        "threads": threads_data,
    }


def _mixed_timeline(ctx, test_keys: list[str], event_types: list[str]) -> dict:
    if ctx.global_min is None or ctx.global_max is None:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    wanted_types = set(event_types)
    wanted_keys = set(test_keys)
    if not wanted_types and not wanted_keys:
        return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

    axis_start = ts_to_ms(ctx.global_min)
    axis_end = ts_to_ms(ctx.global_max)
    ticks = make_ticks(axis_start, axis_end, n=10)

    rows = []
    for ev in ctx.all_events:
        # события выбранных типов
        if ev.event_type and ev.event_type in wanted_types:
            rows.append(make_event_row(ev, axis_start, axis_end))
            continue
        # выбранные тесты (по ключу)
        if _is_test(ev) and test_key(ev) in wanted_keys:
            rows.append(make_event_row(ev, axis_start, axis_end))

    rows.sort(key=lambda r: r["left"])

    return {
        "rows": rows,
        "axis_start": fmt_dt(ctx.global_min),
        "axis_end": fmt_dt(ctx.global_max),
        "ticks": ticks,
    }