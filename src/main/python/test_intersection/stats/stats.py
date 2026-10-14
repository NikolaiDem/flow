from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable

from ..event_parsing import iter_parsed_events
from ..test_events import TestCase, parse_event as parse_test_event
from test_stats import TestStats


log = logging.getLogger("stats")


def collect(events: Iterable[TestCase],
            only_value_type: str | None = "TEST") -> TestStats:
    """Прогоняет TestCase через аккумулятор.

    only_value_type — фильтр по value_type (обычно "TEST");
    None — без фильтра.
    """
    stats = TestStats()
    for tc in events:
        if only_value_type is not None and tc.value_type != only_value_type:
            continue
        stats.add(tc)
    return stats


def collect_from_dir(json_dir: Path,
                     only_value_type: str | None = "TEST") -> TestStats:
    stats = TestStats()
    files = sorted(json_dir.glob("*.json"))
    if not files:
        log.warning("В %s нет *.json", json_dir)
        return stats

    for path in files:
        log.info("Читаю %s", path.name)
        try:
            for tc in iter_parsed_events(path, parse_test_event):
                if only_value_type is not None and tc.value_type != only_value_type:
                    continue
                stats.add(tc)
        except Exception as e:
            log.error("Ошибка в %s: %s", path.name, e)
    return stats


# ----------------------------- вывод ------------------------------

def _fmt_hms(td) -> str:
    """Секунды → 'HH:MM:SS.mmm'."""
    total = td.total_seconds()
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def print_threads_report(stats: TestStats) -> None:
    print("=" * 90)
    print("СТАТИСТИКА ПО ПОТОКАМ")
    print("=" * 90)

    rows = sorted(
        stats.by_thread.items(),
        key=lambda kv: kv[1].total_time,
        reverse=True,
    )

    if not rows:
        print("Нет данных.")
        return

    print(f"\nВсего потоков: {len(rows)}")
    print(f"Всего тестов:  {stats.total_tests()}")
    print(f"Суммарное время тестов: {_fmt_hms(stats.total_time())}")

    header = (
        f"\n{'поток':<40} "
        f"{'тестов':>7} "
        f"{'упало':>6} "
        f"{'сумма':>12} "
        f"{'wall':>12} "
        f"{'сред':>8} "
        f"{'медиана':>9} "
        f"{'min':>8} "
        f"{'max':>8}"
    )
    print(header)
    print("-" * len(header))

    for name, ts in rows:
        print(
            f"{name[:40]:<40} "
            f"{ts.total:>7} "
            f"{ts.failed:>6} "
            f"{_fmt_hms(ts.total_time):>12} "
            f"{_fmt_hms(ts.wall_clock):>12} "
            f"{ts.mean_seconds():>8.3f} "
            f"{ts.median_seconds():>9.3f} "
            f"{(ts.min_duration.total_seconds() if ts.min_duration else 0):>8.3f} "
            f"{(ts.max_duration.total_seconds() if ts.max_duration else 0):>8.3f}"
        )

    # Отдельно — сводка по загрузке потоков
    print("\nЗагрузка потоков (суммарное время тестов / wall-clock):")
    for name, ts in rows:
        wall = ts.wall_clock.total_seconds()
        s = ts.total_time.total_seconds()
        if wall > 0:
            util = s / wall
        else:
            util = 0.0
        print(f"  {util:>6.1%}  {name}  "
              f"(сумма {_fmt_hms(ts.total_time)}, "
              f"wall {_fmt_hms(ts.wall_clock)})")


# ----------------------------- CLI ------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    p = argparse.ArgumentParser(description="Потоки и время тестов в них")
    p.add_argument("json_dir", type=Path)
    p.add_argument("--type", default="TEST",
                   help="value_type теста (по умолчанию TEST); 'all' — все")
    args = p.parse_args()

    only = None if args.type == "all" else args.type
    stats = collect_from_dir(args.json_dir, only_value_type=only)
    print_threads_report(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())