# server.py
from __future__ import annotations

import webbrowser
from http.server import HTTPServer, ThreadingHTTPServer
from pathlib import Path

from context import AppContext
from handler import make_handler


def _load_events():
    """Ленивая загрузка JFR/тестов. Вызывается при первом запросе к данным."""
    # from event_parsing import parse_jfr
    # return parse_jfr(Path("..."))
    return []


def _generate_flow() -> Path | None:
    """
    Генерация flow-HTML. Вызывается лениво — при первом /flow-list или /flow/<name>.html.
    Возвращает директорию или None.
    """
    from flow_graph.build_graph import (generate_flow_htmls)
    return generate_flow_htmls()


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    open_browser: bool = True,
    threaded: bool = False,
    flow_html_dir: Path | None = None,
) -> None:
    ctx = AppContext(
        _load_events,
        flow_generator=_generate_flow,      # ← генератор, не вызов
        flow_html_dir=flow_html_dir,        # ← если CI уже сгенерировал — путь
    )
    handler_cls = make_handler(ctx)

    url = f"http://{host}:{port}/"
    print(f"  → Откройте {url}")
    print("  (данные и flow загружаются лениво — при первом запросе)")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"  (не удалось открыть браузер: {e})")

    server_cls = ThreadingHTTPServer if threaded else HTTPServer
    server_cls((host, port), handler_cls).serve_forever()