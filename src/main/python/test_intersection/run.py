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

import test_events
import spring_events


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

PARSERS = {
    "org.junit.TestExecution": test_events.parse_event,
    "org.springframework.core.metrics.jfr.FlightRecorderStartupEvent":
        spring_events.parse_event,
}


def make_demo_events() -> list[TestCase]:
    base = datetime(2026, 10, 5, 12, 0, 0)

    def tc(class_name, method_name, display_name, thread, start_s, dur_s,
           result="PASSED",
           event_type="org.junit.TestExecution"):
        s = base + timedelta(seconds=start_s)
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

    return [
        tc("LoginTest",    "test_login",    "Login — happy path",       "worker-1", 0.0,  3.5, "PASSED"),
        tc("PaymentTest",  "test_payment",  "Payment — card declined",  "worker-2", 1.2,  2.0, "FAILED"),
        tc("ProfileTest",  "test_profile",  "Profile — update display name", "worker-1", 2.5, 1.5, "PASSED"),
        tc("LogoutTest",   "test_logout",   "Logout — clears session",  "worker-3", 5.0,  1.0, "PASSED"),
        tc("SearchTest",   "test_search",   "Search — full-text query", "worker-2", 6.0,  4.0, "FAILED"),
        tc("CheckoutTest", "test_checkout", "Checkout — guest user",    "worker-3", 7.5,  2.0, "PASSED"),
        tc("ReportTest",   "test_report_generation", "Reports — monthly export", "worker-1", 9.0, 3.0, "FAILED"),
        tc("CleanupTest",  "test_cleanup",  "Cleanup — temp files",     "worker-3", 12.5, 1.0, "PASSED"),
        tc("HealthTest",   "test_healthcheck", "Healthcheck — /status ping", "worker-2", 12.8, 0.5, "PASSED"),
    ]


def main() -> int:
    jfr_dir = Path("D:/work/jfr")
    json_dir = Path("D:/work/jfr/json")

    if jfr_dir.is_dir() and any(jfr_dir.glob("*.jfr")):
        print("Найдены JFR-файлы, парсим...")
        jfr_to_json(jfr_dir, json_dir)
        events = collect_all(json_dir, PARSERS)
        if not events:
            print("JFR-файлы не дали событий, использую демо-данные.")
            events = make_demo_events()
    else:
        print("JFR-файлы не найдены — использую демо-данные.")
        events = make_demo_events()

    print(f"Событий: {len(events)}")
    serve(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())