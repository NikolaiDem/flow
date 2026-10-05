# Начиная с версии junit-platform-launcher-6.0.3.jar
# Преобразовать recording.jfr в json
# jfr print --json --events "ru.dev.flow.advice.LogRecordingEvent" recording.jfr > output.json
# Структура event:
# "type": "org.junit.TestExecution",
#       "values": {
#         "startTime": "2026-10-01T17:50:51.628035091+03:00",
#         "duration": "PT4.809288896S",
#         "eventThread": {
#           "osName": "ForkJoinPool-1-worker-4",
#           "osThreadId": 14896,
#           "javaName": "ForkJoinPool-1-worker-4",
#           "javaThreadId": 56,
#           "group": {
#             "parent": {
#               "parent": null,
#               "name": "system"
#             },
#             "name": "main"
#           },
#           "virtual": false
#         },
#         "stackTrace": null,
#         "result": "SUCCESSFUL",
#         "exceptionClass": null,
#         "exceptionMessage": null,
#         "uniqueId": "[engine:junit-jupiter]\/[class:ru.alfabank.pc.api.diva.repo.CardOwnersTest]\/[method:cardOwnersByReqAmtWithIssAcctNumStartedWithPOOL()]",
#         "displayName": "\u0412 \u0432\u044b\u0431\u043e\u0440\u043a\u0443 \u043f\u043e\u043f\u0430\u0434\u0430\u044e\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438, \u0443 \u043a\u043e\u0442\u043e\u0440\u044b\u0445 iss_acct_num \u043d\u0435 \u043d\u0430\u0447\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0441 POOL (\u0437\u0430\u043f\u0440\u043e\u0441 \u0431\u0435\u0437 \u0424\u0418\u041e). ~48\u0441\u0435\u043a",
#         "tags": null,
#         "type": "TEST"
#       }
#     }

#!/usr/bin/env python3
"""
Анализ пересечений JUnit-тестов из JFR-записей.

Использование:
    python analyze_jfr.py <jfr_dir> <json_dir> [--top N] [--keep-json]
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import isodate
from dateutil import parser as dtparser


TEST_EVENT_TYPE = "org.junit.TestExecution"
log = logging.getLogger("analyze_jfr")


# --------------------------------------------------------------------------- #
# Модель данных
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class TestCase:
    display_name: str
    thread_name: str
    start_time: datetime
    end_time: datetime
    duration: timedelta

    def __post_init__(self) -> None:
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) < start_time ({self.start_time}) "
                f"for {self.display_name!r}"
            )

    def __str__(self) -> str:
        return (
            f"[{self.thread_name}] {self.display_name} "
            f"({self.duration.total_seconds():.3f}s)"
        )


# --------------------------------------------------------------------------- #
# Конвертация JFR -> JSON
# --------------------------------------------------------------------------- #
def jfr_to_json(jfr_dir: Path, out_dir: Path, *, force: bool = False) -> None:
    """Конвертирует все *.jfr в out_dir/*.json через `jfr print`."""
    out_dir.mkdir(parents=True, exist_ok=True)

    jfr_files = sorted(jfr_dir.glob("*.jfr"))
    if not jfr_files:
        log.warning("В %s не найдено ни одного .jfr файла", jfr_dir)
        return

    for jfr_file in jfr_files:
        out_file = out_dir / (jfr_file.stem + ".json")

        # Пропускаем, если JSON свежее исходного JFR
        if (
            not force
            and out_file.exists()
            and out_file.stat().st_mtime >= jfr_file.stat().st_mtime
        ):
            log.info("Skip (up to date): %s", out_file.name)
            continue

        cmd = [
            "jfr", "print",
            "--json",
            "--events", TEST_EVENT_TYPE,
            str(jfr_file),
        ]
        log.info("Converting: %s -> %s", jfr_file.name, out_file.name)

        try:
            with open(out_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    check=False,
                )
        except FileNotFoundError:
            log.error("Команда 'jfr' не найдена. Установите JDK (jfr в PATH).")
            sys.exit(1)

        if result.returncode != 0:
            log.error("jfr failed: %s", result.stderr.strip())
            out_file.unlink(missing_ok=True)
        else:
            log.info("  OK")


# --------------------------------------------------------------------------- #
# Парсинг JSON
# --------------------------------------------------------------------------- #
def parse_event(raw: dict) -> TestCase | None:
    """Преобразует одно событие JFR в TestCase. None, если данных не хватает."""
    values = raw.get("values")
    if not values:
        return None

    try:
        start_time = dtparser.isoparse(values["startTime"])
        duration = isodate.parse_duration(values["duration"])
    except (KeyError, ValueError) as e:
        log.debug("Некорректное событие: %s (%s)", values.get("displayName"), e)
        return None

    thread_name = (
        values.get("eventThread", {}).get("javaName", "<unknown>")
    )

    return TestCase(
        display_name=values.get("displayName", "<unnamed>"),
        thread_name=thread_name,
        start_time=start_time,
        end_time=start_time + duration,
        duration=duration,
    )


def parse_file(path: Path) -> list[TestCase]:
    """Читает один JSON и возвращает список TestCase (только TEST-события)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("recording", {}).get("events", [])
    result: list[TestCase] = []

    for e in events:
        if e.get("type") != TEST_EVENT_TYPE:
            continue
        values = e.get("values", {})
        if values.get("type") != "TEST":
            continue

        tc = parse_event(e)
        if tc is not None:
            result.append(tc)

    return result


def collect_all(json_dir: Path) -> list[TestCase]:
    """Парсит все *.json в директории. Ошибки логирует, но не падает."""
    all_events: list[TestCase] = []
    files = sorted(json_dir.glob("*.json"))

    if not files:
        log.warning("В %s не найдено ни одного .json файла", json_dir)

    for json_file in files:
        try:
            events = parse_file(json_file)
            all_events.extend(events)
            log.debug("%s: %d событий", json_file.name, len(events))
        except Exception as e:  # noqa: BLE001 — хотим продолжать на любых ошибках
            log.error("Ошибка в %s: %s", json_file.name, e)

    log.info("Всего распарсено событий: %d", len(all_events))
    return all_events


# --------------------------------------------------------------------------- #
# Поиск пересечений (sweep line, O(n log n))
# --------------------------------------------------------------------------- #
def find_overlaps(events: list[TestCase]) -> list[tuple[TestCase, TestCase]]:
    """
    Возвращает все пары событий, чьи интервалы пересекаются.

    Касание (end одного == start другого) пересечением НЕ считается.
    """
    points: list[tuple[datetime, int, int]] = []
    for i, e in enumerate(events):
        points.append((e.start_time, +1, i))  # начало
        points.append((e.end_time, -1, i))    # конец

    # При равном времени конец обрабатывается раньше начала -> касание не пересечение
    points.sort(key=lambda p: (p[0], p[1]))

    active: set[int] = set()
    overlaps: list[tuple[TestCase, TestCase]] = []

    for _, delta, i in points:
        if delta == 1:
            for j in active:
                overlaps.append((events[j], events[i]))
            active.add(i)
        else:
            active.discard(i)

    return overlaps


def calc_intersection_ms(left: TestCase, right: TestCase) -> float:
    """Длительность пересечения в миллисекундах (0.0, если пересечения нет)."""
    start = max(left.start_time, right.start_time)
    end = min(left.end_time, right.end_time)
    ms = (end - start).total_seconds() * 1000.0
    return ms if ms > 0 else 0.0


# --------------------------------------------------------------------------- #
# Построение словаря пересечений
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Overlap:
    other: TestCase
    intersection_ms: float


def build_overlap_dict(
    overlaps: list[tuple[TestCase, TestCase]],
) -> dict[TestCase, list[Overlap]]:
    """Для каждого TestCase — список пересечений, отсортированный по убыванию ms."""
    result: dict[TestCase, list[Overlap]] = defaultdict(list)

    for left, right in overlaps:
        ms = calc_intersection_ms(left, right)
        if ms <= 0:
            continue
        result[left].append(Overlap(other=right, intersection_ms=ms))
        result[right].append(Overlap(other=left, intersection_ms=ms))

    for name in result:
        result[name].sort(key=lambda o: o.intersection_ms, reverse=True)

    return dict(result)


# --------------------------------------------------------------------------- #
# Вывод
# --------------------------------------------------------------------------- #
def print_overlaps_table(
    overlap_dict: dict[TestCase, list[Overlap]],
    top_n: int = 10,
) -> None:
    name_w = 40
    other_w = 40
    header = f"{'TEST':<{name_w}} {'OTHER':<{other_w}} {'MS':>10}"
    print(header)
    print("-" * len(header))

    for name, items in overlap_dict.items():
        for i, ov in enumerate(items[:top_n]):
            left = name.display_name if i == 0 else ""
            other = ov.other.display_name
            print(
                f"{left:<{name_w}} {'-' * 17} "
                f"{other:<{other_w}} {ov.intersection_ms:>10.1f}"
            )
        if items:
            print()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Анализ пересечений JUnit-тестов из JFR-записей.",
    )
    p.add_argument("jfr_dir", type=Path, help="Директория с *.jfr файлами")
    p.add_argument("json_dir", type=Path, help="Директория для *.json")
    p.add_argument(
        "--top", type=int, default=10,
        help="Сколько пересечений показывать на тест (по умолчанию 10)",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Перепарсить JFR, даже если JSON свежее",
    )
    p.add_argument(
        "--keep-json", action="store_true",
        help="Не удалять JSON после анализа",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Подробный вывод (DEBUG)",
    )
    return p


if __name__ == "__main__":
    jfr_path = Path("D:/work/jfr")
    json_path = Path("D:/work/jfr/json")
    format_to_json(jfr_path, json_path)
    all_events = collect_all(Path("D:/work/jfr/json"))
    overlaps = find_overlaps(all_events)
    overlap_dicts = build_overlap_dict(overlaps)
    print_overlaps_table(overlap_dicts)
    print(len(all_events))
