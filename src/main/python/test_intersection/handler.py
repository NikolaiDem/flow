from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import globals as g
from timeline import (
    all_unique_tests,
    build_group_timeline_by_keys,
    build_timeline,
    fmt_dt,
    make_ticks,
    test_key,
    ts_to_ms,
)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


def _matches(tc, query: str) -> bool:
    """Ищет подстроку в class_name, method_name, display_name и их комбинациях."""
    q = query.lower()
    cls = (getattr(tc, "class_name", "") or "").lower()
    mth = (getattr(tc, "method_name", "") or "").lower()
    dsp = (getattr(tc, "display_name", "") or "").lower()
    return (
        q in cls
        or q in mth
        or q in dsp
        or q in f"{cls}.{mth}"
        or q in f"{cls}:{mth}:{dsp}"
    )


def _brief(tc) -> dict:
    """Компактное представление теста для фронта."""
    return {
        "key": test_key(tc),
        "name": getattr(tc, "display_name", "") or "",
        "class_name": getattr(tc, "class_name", "") or "",
        "method_name": getattr(tc, "method_name", "") or "",
        "thread": tc.thread_name,
        "result": tc.result,
    }


class Handler(BaseHTTPRequestHandler):
    # ---------- GET ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_static("index.html", "text/html; charset=utf-8")
        elif path == "/style.css":
            self._send_static("style.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_static("app.js", "application/javascript; charset=utf-8")
        elif path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            self._send_json(self._search(q))
        elif path == "/all-tests":
            self._send_json(self._all_tests())
        else:
            self.send_error(404)

    # ---------- POST ----------
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/group-timeline":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                self.send_error(400, "invalid JSON")
                return
            keys = data.get("keys", [])
            self._send_json(build_group_timeline_by_keys(
                keys, g.ALL_EVENTS, g.GLOBAL_MIN, g.GLOBAL_MAX
            ))
        else:
            self.send_error(404)

    # ---------- helpers ----------
    def _all_tests(self):
        """Список ВСЕХ уникальных тестов (включая без пересечений)."""
        result = [_brief(tc) for tc in all_unique_tests(g.ALL_EVENTS)]
        result.sort(key=lambda x: (x["class_name"], x["method_name"], x["name"]))
        return result

    def _search(self, query: str):
        if not query or g.GLOBAL_MIN is None or g.GLOBAL_MAX is None:
            return []

        axis_start = ts_to_ms(g.GLOBAL_MIN)
        axis_end = ts_to_ms(g.GLOBAL_MAX)
        ticks = make_ticks(axis_start, axis_end, n=10)

        result = []
        matched_keys: set[str] = set()

        # 1) Тесты с пересечениями
        for test, partners in g.OVERLAP_DICT.items():
            if not _matches(test, query):
                continue
            matched_keys.add(test_key(test))

            partners_json = [
                {
                    **_brief(ov.other),
                    "other": ov.other.display_name,
                    "ms": ov.intersection_ms,
                }
                for ov in partners
            ]
            rows = build_timeline(test, partners, axis_start, axis_end)
            result.append({
                **_brief(test),
                "partners": partners_json,
                "rows": rows,
                "axis_start": fmt_dt(g.GLOBAL_MIN),
                "axis_end": fmt_dt(g.GLOBAL_MAX),
                "ticks": ticks,
            })

        # 2) Тесты без пересечений
        for tc in all_unique_tests(g.ALL_EVENTS):
            k = test_key(tc)
            if k in matched_keys:
                continue
            if not _matches(tc, query):
                continue
            matched_keys.add(k)

            rows = build_timeline(tc, [], axis_start, axis_end)
            result.append({
                **_brief(tc),
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