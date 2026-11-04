# handler.py
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from context import AppContext
from test_intersection.test_handler import (
    _threads_timeline,
    _mixed_timeline,
    _all_tests,
    _search_tests,
    _all_events,
    _search_events,
    _event_types,
)
from test_intersection.test_timeline import build_group_timeline_by_keys as build_tests_group
from test_intersection.events_timeline import build_group_timeline_by_keys as build_events_group
from test_intersection.stats.test_stats import build_test_stats

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


def make_handler(ctx: AppContext) -> type[BaseHTTPRequestHandler]:

    class Handler(BaseHTTPRequestHandler):
        _ctx = ctx                                  # ← вместо g

        # ---------- GET ----------
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            ctx = self._ctx

            if path in ("/", "/index.html"):
                self._send_static("home.html", "text/html; charset=utf-8")
            elif path == "/style.css":
                self._send_static("style.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                self._send_static("app.js", "application/javascript; charset=utf-8")
            elif path == "/threads.js":
                self._send_static("threads.js", "application/javascript; charset=utf-8")

            # --- tests: ленивая загрузка только здесь ---
            elif path == "/all-tests":
                self._send_json(_all_tests(ctx))
            elif path == "/search":
                q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
                self._send_json(_search_tests(ctx, q))

            # --- events ---
            elif path == "/all-events":
                self._send_json(_all_events(ctx))
            elif path == "/search-events":
                q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
                self._send_json(_search_events(ctx, q))
            elif path == "/event-types":
                self._send_json(_event_types(ctx))

            # --- stats ---
            elif path == "/stats":
                self._send_static("stats.html", "text/html; charset=utf-8")
            elif path == "/stats.js":
                self._send_static("stats.js", "application/javascript; charset=utf-8")
            elif path == "/test-stats":
                # build_test_stats теперь принимает test_events явно
                self._send_json(build_test_stats(ctx.test_events))

            # --- timeline ---
            elif path == "/timeline":
                self._send_static("timeline.html", "text/html; charset=utf-8")
            elif path == "/threads-timeline":
                self._send_json(_threads_timeline(ctx))

            # --- flow ---
            elif path == "/flow":
                self._send_static("flow.html", "text/html; charset=utf-8")
            elif path == "/flow.js":
                self._send_static("flow.js", "application/javascript; charset=utf-8")
            elif path == "/flow-list":
                self._send_json(self._flow_list())
            elif path.startswith("/flow/"):
                self._send_flow_file(path[len("/flow/"):])

            else:
                self.send_error(404)

        # ---------- POST ----------
        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            ctx = self._ctx

            if path not in ("/group-timeline", "/events-timeline", "/mixed-timeline"):
                self.send_error(404); return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                self.send_error(400, "invalid JSON"); return

            if path == "/group-timeline":
                keys = data.get("keys", [])
                self._send_json(build_tests_group(
                    keys, ctx.test_events, ctx.global_min, ctx.global_max
                ))
            elif path == "/events-timeline":
                keys = data.get("keys", [])
                self._send_json(build_events_group(
                    keys, ctx.all_events, ctx.global_min, ctx.global_max
                ))
            else:
                test_keys = data.get("test_keys", [])
                event_types = data.get("event_types", [])
                self._send_json(_mixed_timeline(ctx, test_keys, event_types))

        # ---------- flow ----------
        def _flow_list(self):
            d = self._ctx.flow_html_dir
            if d is None or not d.is_dir():
                return []
            return [{"name": p.stem, "url": f"/flow/{p.name}"}
                    for p in sorted(d.glob("*.html"))]

        def _send_flow_file(self, name: str):
            d = self._ctx.flow_html_dir
            if d is None:
                self.send_error(404, "flow not generated"); return
            if "/" in name or "\\" in name or ".." in name:
                self.send_error(400); return
            fp = (d / name).resolve()
            if not fp.is_file() or d.resolve() not in fp.parents:
                self.send_error(404); return
            body = fp.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        # ---------- utils ----------
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

    return Handler