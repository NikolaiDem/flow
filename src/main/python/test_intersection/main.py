from __future__ import annotations

from http.server import HTTPServer

import globals as g
from handler import Handler


def serve(overlap_dict: dict, all_events: list,
          host: str = "127.0.0.1", port: int = 8000) -> None:
    g.OVERLAP_DICT = overlap_dict
    g.ALL_EVENTS = all_events
    if all_events:
        g.GLOBAL_MIN = min(e.start_time for e in all_events)
        g.GLOBAL_MAX = max(e.end_time for e in all_events)

    # Отладка
    names_in_dict = {t.display_name for t in g.OVERLAP_DICT.keys()}
    names_in_events = {e.display_name for e in g.ALL_EVENTS}
    only_in_events = names_in_events - names_in_dict
    print(f"  OVERLAP_DICT: {len(g.OVERLAP_DICT)} тестов с пересечениями")
    print(f"  ALL_EVENTS:   {len(names_in_events)} уникальных тестов")
    print(f"  Без пересечений: {len(only_in_events)}")

    print(f"\n  → Откройте http://{host}:{port}\n")
    HTTPServer((host, port), Handler).serve_forever()