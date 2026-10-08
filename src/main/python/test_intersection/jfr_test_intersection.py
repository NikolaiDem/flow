from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from event_parsing import JfrEvent

log = logging.getLogger(__name__)

# Парсер: raw dict -> JfrEvent | None
Parser = Callable[[dict], JfrEvent | None]


def _iter_raw_events(json_file: Path):
    """Читает один JSON и отдаёт сырые события по одному."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    yield from data.get("recording", {}).get("events", [])


def collect_all(
        json_dir: Path,
        parsers: dict[str, Parser],
) -> list[JfrEvent]:
    """Обходит все *.json в директории и парсит события по словарю parsers.

    parsers: {jfr_event_type: parse_func}
        - jfr_event_type — значение raw["type"] (например, "org.junit.TestExecution");
        - parse_func(raw) -> JfrEvent | None.

    События с типом, которого нет в parsers, пропускаются.
    Исключения внутри parse_func логируются, но не роняют обход.
    """
    all_events: list[JfrEvent] = []
    files = sorted(json_dir.glob("*.json"))

    if not files:
        log.warning("В %s не найдено ни одного .json файла", json_dir)
        return all_events

    skipped_types: dict[str, int] = {}
    errors = 0

    for json_file in files:
        file_events = 0
        try:
            raw_events = list(_iter_raw_events(json_file))
        except Exception as e:  # noqa: BLE001
            log.error("Не удалось прочитать %s: %s", json_file.name, e)
            continue

        for raw in raw_events:
            raw_type = raw.get("type")
            parser = parsers.get(raw_type)
            if parser is None:
                skipped_types[raw_type] = skipped_types.get(raw_type, 0) + 1
                continue

            try:
                event = parser(raw)
            except Exception as e:  # noqa: BLE001
                errors += 1
                log.debug("Ошибка в %s (%s): %s", json_file.name, raw_type, e)
                continue

            if event is not None:
                all_events.append(event)
                file_events += 1

        log.debug("%s: %d событий", json_file.name, file_events)

    log.info("Всего распарсено событий: %d", len(all_events))

    by_kind: dict[str, int] = {}
    for e in all_events:
        k = getattr(e, "kind", "event")
        by_kind[k] = by_kind.get(k, 0) + 1
    for kind, n in sorted(by_kind.items()):
        log.info("  kind=%-8s %d", kind, n)

    if skipped_types:
        log.debug("Пропущено типов событий: %d", len(skipped_types))
        for t, n in sorted(skipped_types.items(), key=lambda kv: -kv[1])[:10]:
            log.debug("  %-60s %d", t, n)

    if errors:
        log.warning("Ошибок парсинга: %d (см. debug-лог)", errors)

    return all_events