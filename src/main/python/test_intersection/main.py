from __future__ import annotations

from http.server import HTTPServer

import globals as g
from handler import Handler
from event_parsing import JfrEvent
from overlaps import build_overlap_dict
from test_events import TestCase


def serve(all_events: list[JfrEvent],
          host: str = "127.0.0.1", port: int = 8000) -> None:
    g.OVERLAP_DICT = build_overlap_dict(all_events)
    g.ALL_EVENTS = all_events
    g.TEST_EVENTS = [e for e in all_events if isinstance(e, TestCase)]

    if all_events:
        g.GLOBAL_MIN = min(e.start_time for e in all_events)
        g.GLOBAL_MAX = max(e.end_time for e in all_events)
    else:
        g.GLOBAL_MIN = g.GLOBAL_MAX = None

    print(f"  ALL_EVENTS:   {len(g.ALL_EVENTS)}")
    print(f"  TEST_EVENTS:  {len(g.TEST_EVENTS)}")
    print(f"  OVERLAP_DICT: {len(g.OVERLAP_DICT)}")

    print(f"\n  → Откройте http://{host}:{port}\n")
    HTTPServer((host, port), Handler).serve_forever()