# run.py
"""
Запуск сервера. Если реальных JFR-файлов нет — используются демо-данные.
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from jfr_test_intersection import (
    TestCase, build_overlap_dict, jfr_to_json, collect_all,
)
from main import serve
from timeline import test_key


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def make_demo_events() -> list[TestCase]:
    """Синтетические тесты для демонстрации таймлайна.

    У каждого теста есть:
      - class_name / method_name — из них собирается ключ class_name:method_name:display_name;
      - display_name — человекочитаемое название для UI ("Login — happy path");
      - event_type / value_type — как у реальных JFR-событий.
    """
    base = datetime(2026, 10, 5, 12, 0, 0)

    def tc(class_name, method_name, display_name, thread, start_s, dur_s,
           result="PASSED",
           event_type="Test",
           value_type="jdk.jfr.Test"):
        s = base + timedelta(seconds=start_s)
        d = timedelta(seconds=dur_s)
        return TestCase(
            class_name=class_name,
            method_name=method_name,
            display_name=display_name,
            thread_name=thread,
            start_time=s,
            end_time=s + d,
            duration=d,
            result=result,
            event_type=event_type,
            value_type=value_type,
        )

    return [
        tc("LoginTest", "test_login",
           "Login — happy path",
           "worker-1", 0.0, 3.5, "PASSED"),

        tc("PaymentTest", "test_payment",
           "Payment — card declined",
           "worker-2", 1.2, 2.0, "FAILED"),        # пересекается с login

        tc("ProfileTest", "test_profile",
           "Profile — update display name",
           "worker-1", 2.5, 1.5, "PASSED"),        # пересекается с login и payment

        tc("LogoutTest", "test_logout",
           "Logout — clears session",
           "worker-3", 5.0, 1.0, "PASSED"),

        tc("SearchTest", "test_search",
           "Search — full-text query",
           "worker-2", 6.0, 4.0, "FAILED"),

        tc("CheckoutTest", "test_checkout",
           "Checkout — guest user",
           "worker-3", 7.5, 2.0, "PASSED"),        # пересекается с search

        tc("ReportTest", "test_report_generation",
           "Reports — monthly export",
           "worker-1", 9.0, 3.0, "FAILED"),        # пересекается с search и checkout

        tc("CleanupTest", "test_cleanup",
           "Cleanup — temp files",
           "worker-3", 12.5, 1.0, "PASSED"),

        tc("HealthTest", "test_healthcheck",
           "Healthcheck — /status ping",
           "worker-2", 12.8, 0.5, "PASSED"),       # микро-пересечение с cleanup
    ]


def main() -> int:
    jfr_dir = Path("D:/work/jfr")
    json_dir = Path("D:/work/jfr/json")

    # Если реальные JFR есть — парсим их. Иначе — демо.
    if jfr_dir.is_dir() and any(jfr_dir.glob("*.jfr")):
        print("Найдены JFR-файлы, парсим...")
        jfr_to_json(jfr_dir, json_dir)
        events = collect_all(json_dir)
        if not events:
            print("JFR-файлы не дали событий, использую демо-данные.")
            events = make_demo_events()
    else:
        print("JFR-файлы не найдены — использую демо-данные.")
        events = make_demo_events()

    print(f"Событий: {len(events)}")

    overlap_dict = build_overlap_dict(events)
    print(f"Пересекающихся пар: {len(overlap_dict)}")

    # Уникальные ключи — через тот же test_key, что и в handler.py / timeline.py.
    unique_keys = {test_key(e) for e in events}
    print(f"Уникальных тестов (по ключу): {len(unique_keys)}")

    serve(overlap_dict, events)
    return 0


if __name__ == "__main__":
    sys.exit(main())