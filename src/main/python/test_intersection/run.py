# run.py
"""
Запуск сервера. Если реальных JFR-файлов нет — используются демо-данные.
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from jfr_test_intersection import (
    TestCase, find_overlaps, build_overlap_dict, jfr_to_json, collect_all,
)
from jfr_server_test_intersection import serve


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def make_demo_events() -> list[TestCase]:
    """Синтетические тесты для демонстрации таймлайна."""
    base = datetime(2026, 10, 5, 12, 0, 0)

    def tc(name, thread, start_s, dur_s):
        s = base + timedelta(seconds=start_s)
        d = timedelta(seconds=dur_s)
        return TestCase(name, thread, s, s + d, d)

    return [
        tc("test_login",            "worker-1", 0.0,  3.5),
        tc("test_payment",          "worker-2", 1.2,  2.0),   # пересекается с login
        tc("test_profile",          "worker-1", 2.5,  1.5),   # пересекается с login и payment
        tc("test_logout",           "worker-3", 5.0,  1.0),
        tc("test_search",           "worker-2", 6.0,  4.0),
        tc("test_checkout",         "worker-3", 7.5,  2.0),   # пересекается с search
        tc("test_report_generation","worker-1", 9.0,  3.0),   # пересекается с search и checkout
        tc("test_cleanup",          "worker-3", 12.5, 1.0),
        tc("test_healthcheck",      "worker-2", 12.8, 0.5),   # микро-пересечение с cleanup
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
    overlaps = find_overlaps(events)
    print(f"Пересекающихся пар: {len(overlaps)}")

    overlap_dict = build_overlap_dict(overlaps)
    serve(overlap_dict, events)
    return 0


if __name__ == "__main__":
    sys.exit(main())