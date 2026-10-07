"""
Анализ пересечений JUnit-тестов из JFR-записей.

Использование:
    python analyze_jfr.py <jfr_dir> <json_dir> [--top N] [--keep-json]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from jfr_to_json import jfr_to_json
from event_parsing import TestCase
from event_parsing import parse_file
from overlaps import build_overlap_dict


TEST_EVENT_TYPE = "org.junit.TestExecution"
log = logging.getLogger("analyze_jfr")


def collect_all(json_dir: Path) -> list[TestCase]:
    """Парсит все *.json в директории. Ошибки логирует, но не падает."""
    all_events: list[TestCase] = []
    files = sorted(json_dir.glob("*.json"))

    if not files:
        log.warning("В %s не найдено ни одного .json файла", json_dir)

    for json_file in files:
        try:
            events = parse_file(json_file, event_types=list(TEST_EVENT_TYPE), value_types=list("Test"))
            all_events.extend(events)
            log.debug("%s: %d событий", json_file.name, len(events))
        except Exception as e:  # noqa: BLE001 — хотим продолжать на любых ошибках
            log.error("Ошибка в %s: %s", json_file.name, e)

    log.info("Всего распарсено событий: %d", len(all_events))
    return all_events


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
    jfr_to_json(jfr_path, json_path)
    all_events = collect_all(Path(json_path))
    overlap_dicts = build_overlap_dict(all_events)
    print(len(all_events))