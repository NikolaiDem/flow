# run.py
"""
Запуск сервера. Если реальных JFR-файлов нет — используются демо-данные.
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from jfr_test_intersection import collect_all
from jfr_to_json import jfr_to_json
from main import serve
from test_events import TestCase
from spring_events import SpringEvent

import test_events
import spring_events


logging.basicConfig(
    filename="app.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

SPRING_EVENT_TYPE = (
    "org.springframework.core.metrics.jfr.FlightRecorderStartupEvent"
)

PARSERS = {
    "org.junit.TestExecution": test_events.parse_event,
    SPRING_EVENT_TYPE: spring_events.parse_event,
}


def make_demo_events() -> list:
    """Демо-данные: несколько тестов + типичные Spring-фазы.

    Spring-фазы идут ДО тестов, чтобы на таймлайне они были видны слева
    и не пересекались с тестами.
    """
    base = datetime(2026, 10, 5, 12, 0, 0)

    # ---- Spring-фазы (всё в main, до старта тестов) ----

    def spring(name: str, display: str,
               start_s: float, dur_s: float,
               event_id: int, parent_id: int | None) -> SpringEvent:
        s = base + timedelta(seconds=start_s)
        d = timedelta(seconds=dur_s)
        return SpringEvent(
            name=name,
            display_name=display,
            thread_name="main",
            start_time=s,
            end_time=s + d,
            duration=d,
            event_type=SPRING_EVENT_TYPE,
            event_id=event_id,
            parent_id=parent_id,
            tags="",
        )

    spring_events = [
        spring("spring.boot.application.starting",
               "Spring — application starting",
               0.000, 0.045, event_id=1, parent_id=None),

        spring("spring.boot.application.environment-prepared",
               "Spring — environment prepared",
               0.045, 0.120, event_id=2, parent_id=1),

        spring("spring.boot.application.context-prepared",
               "Spring — context prepared",
               0.165, 0.540, event_id=3, parent_id=2),

        spring("spring.boot.application.context-loaded",
               "Spring — context loaded",
               0.705, 0.300, event_id=4, parent_id=3),

        spring("spring.boot.application.started",
               "Spring — started",
               1.005, 0.010, event_id=5, parent_id=4),
    ]

    # ---- Тесты (начинаются после Spring-фаз) ----

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

    return spring_events + tests


def main() -> int:
    jfr_dir = Path("D:/work/jfr")
    json_dir = Path("D:/work/jfr/json")

    if jfr_dir.is_dir() and any(jfr_dir.glob("*.jfr")):
        print("Найдены JFR-файлы, парсим...")
        jfr_to_json(
            jfr_dir, json_dir,
            events=[
                "org.junit.TestExecution",
                SPRING_EVENT_TYPE,
            ],
        )
        events = collect_all(json_dir, PARSERS)
        if not events:
            print("JFR-файлы не дали событий, использую демо-данные.")
            events = make_demo_events()
    else:
        print("JFR-файлы не найдены — использую демо-данные.")
        events = make_demo_events()

    print(f"Событий: {len(events)}")

    tests = sum(1 for e in events if isinstance(e, TestCase))
    springs = sum(1 for e in events if isinstance(e, SpringEvent))
    print(f"  тестов: {tests}")
    print(f"  spring-событий: {springs}")

    serve(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())