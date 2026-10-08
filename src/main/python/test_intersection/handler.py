from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import globals as g

from timeline_common import fmt_dt, make_ticks, ts_to_ms

from event_parsing import JfrEvent
from test_events import TestCase

from test_timeline import (
    build_group_timeline_by_keys as build_tests_group,
    build_timeline as build_tests_timeline,
    test_key,
)
from events_timeline import (
    build_group_timeline_by_keys as build_events_group,
    build_timeline as build_events_timeline,
    event_key,
    make_row as make_event_row,
)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


# ---------- helpers ----------

def _lower(s) -> str:
    return (s or "").lower()


# ---------- brief: tests ----------

def _test_brief(tc: TestCase) -> dict:
    return {
        "key": test_key(tc),              # == tc.name
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
    return (
        q in cls
        or q in mth
        or q in dsp
        or q in nm
        or q in f"{cls}.{mth}"
    )


# ---------- brief: events ----------

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
    return (
        q in _lower(tc.display_name)
        or q in _lower(tc.event_type)
        or q in _lower(tc.thread_name)
    )


class Handler(BaseHTTPRequestHandler):
    # ---------- GET ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # статика
        if path in ("/", "/index.html"):
            self._send_static("index.html", "text/html; charset=utf-8")
        elif path == "/style.css":
            self._send_static("style.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_static("app.js", "application/javascript; charset=utf-8")

        # тесты
        elif path == "/all-tests":
            self._send_json(self._all_tests())
        elif path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            self._send_json(self._search_tests(q))

        # события
        elif path == "/all-events":
            self._send_json(self._all_events())
        elif path == "/search-events":
            q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            self._send_json(self._search_events(q))
        elif path == "/event-types":
            self._send_json(self._event_types())

        else:
            self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path not in ("/group-timeline", "/events-timeline", "/mixed-timeline"):
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON")
            return

        if path == "/group-timeline":
            keys = data.get("keys", [])
            self._send_json(build_tests_group(
                keys, g.TEST_EVENTS, g.GLOBAL_MIN, g.GLOBAL_MAX
            ))
        elif path == "/events-timeline":
            keys = data.get("keys", [])
            self._send_json(build_events_group(
                keys, g.ALL_EVENTS, g.GLOBAL_MIN, g.GLOBAL_MAX
            ))
        else:  # /mixed-timeline
            test_keys = data.get("test_keys", [])
            event_types = data.get("event_types", [])
            self._send_json(self._mixed_timeline(test_keys, event_types))

    # ---------- tests ----------

    def _all_tests(self):
        result = [_test_brief(tc) for tc in g.TEST_EVENTS]
        result.sort(key=lambda x: (x["class_name"], x["method_name"], x["name"]))
        return result

    def _search_tests(self, query: str):
        if (not query
                or g.GLOBAL_MIN is None
                or g.GLOBAL_MAX is None
                or not g.TEST_EVENTS):
            return []

        axis_start = ts_to_ms(g.GLOBAL_MIN)
        axis_end = ts_to_ms(g.GLOBAL_MAX)
        ticks = make_ticks(axis_start, axis_end, n=10)

        result: list[dict] = []
        matched: set[str] = set()

        # 1) тесты с пересечениями
        for test, partners in g.OVERLAP_DICT.items():
            if not isinstance(test, TestCase):
                continue
            if not _test_matches(test, query):
                continue
            matched.add(test_key(test))

            test_partners = [ov for ov in partners if isinstance(ov.other, TestCase)]

            partners_json = [
                {
                    **_test_brief(ov.other),
                    "ms": ov.intersection_ms,
                }
                for ov in test_partners
            ]
            rows = build_tests_timeline(test, test_partners, axis_start, axis_end)
            result.append({
                **_test_brief(test),
                "partners": partners_json,
                "rows": rows,
                "axis_start": fmt_dt(g.GLOBAL_MIN),
                "axis_end": fmt_dt(g.GLOBAL_MAX),
                "ticks": ticks,
            })

        # 2) тесты без пересечений
        for tc in g.TEST_EVENTS:
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
                "axis_start": fmt_dt(g.GLOBAL_MIN),
                "axis_end": fmt_dt(g.GLOBAL_MAX),
                "ticks": ticks,
            })

        def sort_key(x):
            total = sum(p["ms"] for p in x["partners"])
            return (-total, x["class_name"], x["method_name"], x["name"])

        result.sort(key=sort_key)
        return result[:50]

    # ---------- events ----------

    def _all_events(self):
        result = [_event_brief(e) for e in g.ALL_EVENTS]
        result.sort(key=lambda x: (x["event_type"], x["name"], x["thread"]))
        return result

    def _search_events(self, query: str):
        if (not query
                or g.GLOBAL_MIN is None
                or g.GLOBAL_MAX is None
                or not g.ALL_EVENTS):
            return []

        axis_start = ts_to_ms(g.GLOBAL_MIN)
        axis_end = ts_to_ms(g.GLOBAL_MAX)
        ticks = make_ticks(axis_start, axis_end, n=10)

        result: list[dict] = []
        matched: set[str] = set()

        for ev, partners in g.OVERLAP_DICT.items():
            if not _event_matches(ev, query):
                continue
            matched.add(event_key(ev))

            partners_json = [
                {
                    **_event_brief(ov.other),
                    "ms": ov.intersection_ms,
                }
                for ov in partners
            ]
            rows = build_events_timeline(ev, partners, axis_start, axis_end)
            result.append({
                **_event_brief(ev),
                "partners": partners_json,
                "rows": rows,
                "axis_start": fmt_dt(g.GLOBAL_MIN),
                "axis_end": fmt_dt(g.GLOBAL_MAX),
                "ticks": ticks,
            })

        for ev in g.ALL_EVENTS:
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
                "axis_start": fmt_dt(g.GLOBAL_MIN),
                "axis_end": fmt_dt(g.GLOBAL_MAX),
                "ticks": ticks,
            })

        def sort_key(x):
            total = sum(p["ms"] for p in x["partners"])
            return (-total, x["event_type"], x["name"])

        result.sort(key=sort_key)
        return result[:50]

    def _event_types(self):
        """Уникальные event_type с количеством вхождений."""
        counts: dict[str, int] = {}
        for e in g.ALL_EVENTS:
            t = e.event_type or ""
            counts[t] = counts.get(t, 0) + 1

        return [
            {"event_type": t, "count": c}
            for t, c in sorted(counts.items())
        ]

    # ---------- mixed ----------

    def _mixed_timeline(self, test_keys: list[str], event_types: list[str]) -> dict:
        """Смешанный таймлайн: тесты и события в едином формате JfrEvent.

        - test_keys:  список tc.name (пустой — тестов нет);
        - event_types: список event_type (пустой — событий нет);
        - оба пусты — пустой таймлайн.
        """
        if g.GLOBAL_MIN is None or g.GLOBAL_MAX is None:
            return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

        wanted_tests = set(test_keys)
        wanted_types = set(event_types)

        if not wanted_tests and not wanted_types:
            return {"rows": [], "axis_start": "", "axis_end": "", "ticks": []}

        axis_start = ts_to_ms(g.GLOBAL_MIN)
        axis_end = ts_to_ms(g.GLOBAL_MAX)
        ticks = make_ticks(axis_start, axis_end, n=10)

        rows: list[dict] = []

        # тесты — рендерим как обычные JfrEvent
        if wanted_tests:
            for tc in g.TEST_EVENTS:
                if tc.name not in wanted_tests:
                    continue
                rows.append(make_event_row(tc, axis_start, axis_end))

        # события выбранных типов
        if wanted_types:
            for ev in g.ALL_EVENTS:
                if not ev.event_type or ev.event_type not in wanted_types:
                    continue
                # тест, уже добавленный через test_keys, не дублируем
                if isinstance(ev, TestCase) and ev.name in wanted_tests:
                    continue
                rows.append(make_event_row(ev, axis_start, axis_end))

        rows.sort(key=lambda r: r["left"])

        return {
            "rows": rows,
            "axis_start": fmt_dt(g.GLOBAL_MIN),
            "axis_end": fmt_dt(g.GLOBAL_MAX),
            "ticks": ticks,
        }

    # ---------- IO ----------

    def _send_static(self, filename: str, content_type: str):
        file_path = BASE_DIR / "static" / filename
        if not file_path.is_file():
            log.error("static not found: %s (BASE_DIR=%s)", file_path, BASE_DIR)
            self.send_error(404, f"{filename} not found in {BASE_DIR}")
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass