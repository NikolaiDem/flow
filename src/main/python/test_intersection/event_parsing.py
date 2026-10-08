from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JfrEvent:
    name: str
    display_name: str
    thread_name: str
    start_time: datetime
    end_time: datetime
    duration: timedelta
    event_type: str

    def __post_init__(self) -> None:
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) < start_time ({self.start_time}) "
                f"for {self.display_name!r}"
            )

    def __str__(self) -> str:
        return (
            f"[{self.thread_name}] {self.display_name} "
            f"({self.duration.total_seconds():.3f}s) "
            f"type={self.event_type}"
        )


def iter_raw_events(path: Path) -> Iterable[dict]:
    """Читает один JSON и отдаёт сырые события по одному.

    Никакой фильтрации — только распаковка структуры recording.events.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    yield from data.get("recording", {}).get("events", [])


def parse_file(
        path: Path,
        parse_event_func: Callable[[dict], JfrEvent | None],
) -> list[JfrEvent]:
    """Прогоняет все сырые события через parse_event_func.

    Событие, для которого parse_event_func вернул None, пропускается.
    Исключения внутри parse_event_func логируются и не роняют обход.
    """
    result: list[JfrEvent] = []
    for raw in iter_raw_events(path):
        try:
            event = parse_event_func(raw)
        except Exception as e:
            log.debug("Ошибка парсинга события type=%r: %s",
                      raw.get("type"), e)
            continue
        if event is not None:
            result.append(event)
    return result