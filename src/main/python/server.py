# server.py
from __future__ import annotations

import webbrowser
from http.server import HTTPServer, ThreadingHTTPServer

from context import AppContext
from handler import make_handler
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from test_events import TestCase

log = logging.getLogger(__name__)

def make_demo_events() -> list:
    """Демо-данные: несколько тестов + типичные Spring-фазы.

    Spring-фазы идут ДО тестов, чтобы на таймлайне они были видны слева
    и не пересекались с тестами.
    """
    base = datetime(2026, 10, 5, 12, 0, 0)

    test_base = base + timedelta(seconds=1.5)   # старт тестов через 1.5 сек после base

    def tc(class_name, method_name, display_name, thread, start_s, dur_s,
           result="PASSED",
           event_type="org.junit.TestExecution"):
        s = test_base + timedelta(seconds=start_s)
        d = timedelta(seconds=dur_s)
        return TestCase(
            name=method_name,
            class_name=class_name,
            method_name=method_name,
            display_name=display_name,
            thread_name=thread,
            start_time=s,
            end_time=s + d,
            duration=d,
            result=result,
            event_type=event_type,
            value_type="TEST",
        )

    tests = [
        tc("LoginTest", "test_login", "Login — happy path",
           "worker-1", 0.0, 3.5, "PASSED"),
        tc("PaymentTest", "test_payment", "Payment — card declined",
           "worker-2", 1.2, 2.0, "FAILED"),
        tc("ProfileTest", "test_profile", "Profile — update display name",
           "worker-1", 4.5, 1.5, "PASSED"),
        tc("LogoutTest", "test_logout", "Logout — clears session",
           "worker-3", 5.0, 1.0, "PASSED"),
        tc("SearchTest", "test_search", "Search — full-text query",
           "worker-2", 6.0, 4.0, "FAILED"),
        tc("CheckoutTest", "test_checkout", "Checkout — guest user",
           "worker-3", 7.5, 2.0, "PASSED"),
        tc("ReportTest", "test_report_generation", "Reports — monthly export",
           "worker-1", 9.0, 3.0, "FAILED"),
        tc("CleanupTest", "test_cleanup", "Cleanup — temp files",
           "worker-3", 12.5, 1.0, "PASSED"),
        tc("HealthTest", "test_healthcheck", "Healthcheck — /status ping",
           "worker-2", 12.8, 0.5, "PASSED"),
    ]

    return tests

def _load_events():
    """Ленивая загрузка JFR/тестов. Вызывается при первом запросе к данным."""
    from jfr_test_intersection import collect_all
    from jfr_to_json import jfr_to_json
    from config import
    path = resolve_config_path()
    cfg = load_config(path)

    jfr_dir = Path(os.getenv("JFR_DIR", "jfr"))
    json_dir = Path(os.getenv("JFR_JSON_DIR", "jfr/json"))

    if not (jfr_dir.is_dir() and any(jfr_dir.glob("*.jfr"))):
        log.info("JFR-файлы не найдены — использую демо-данные")
        return make_demo_events()

    log.info("Найдены JFR-файлы в %s, парсим...", jfr_dir)
    try:
        json_dir.mkdir(parents=True, exist_ok=True)
        jfr_to_json(
            jfr_dir, json_dir,
            events=["org.junit.TestExecution"],
        )
        events = collect_all(json_dir, _resolve_parsers())
    except Exception as e:
        log.exception("Ошибка парсинга JFR: %s. Использую демо-данные", e)
        return make_demo_events()

    if not events:
        log.warning("JFR-файлы не дали событий — использую демо-данные")
        return make_demo_events()

    log.info("Загружено событий: %d", len(events))
    return events

def _resolve_parsers():
    """Ленивый импорт парсеров — чтобы не тянуть модули при старте."""
    import test_events
    return {
        "org.junit.TestExecution": test_events.parse_event
    }

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