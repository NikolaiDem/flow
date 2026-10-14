from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

import ijson

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
    """Потоково читает JSON и отдаёт сырые события из recording.events.

    Файл читается через ijson: в память попадает только текущее событие,
    а не весь документ. Это позволяет открывать файлы размером больше 1 ГБ.

    Путь: recording -> events -> [ ... ]
    Для каждого элемента массива events отдаётся готовый dict.
    """
    # Префикс до массива events. ijson вернёт каждый элемент массива как dict.
    prefix = "recording.events.item"

    with path.open("rb") as f:                      # ijson работает с байтами
        for raw in ijson.items(f, prefix):
            yield raw
            # raw — обычный dict, собранный из JSON-объекта очередного события.
            # После yield он уходит в parse_event_func, следующий цикл
            # перезапишет переменную — предыдущий dict может быть собран GC.


def parse_file(
        path: Path,
        parse_event_func: Callable[[dict], JfrEvent | None],
) -> list[JfrEvent]:
    """Прогоняет все сырые события через parse_event_func.

    Событие, для которого parse_event_func вернул None, пропускается.
    Исключения внутри parse_event_func логируются и не роняют обход.

    Внимание: результат всё ещё копится в список. Если в JSON 500 МБ
    отфильтрованных событий и они все нужны — список займёт память
    пропорционально. Если события нужны только «проходом» — используй
    iter_parsed_events (см. ниже).
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


def iter_parsed_events(
        path: Path,
        parse_event_func: Callable[[dict], JfrEvent | None],
) -> Iterable[JfrEvent]:
    """То же, что parse_file, но отдаёт события по одному, не копя список.

    Удобно, когда файл большой, а события обрабатываются «на лету»:
        for ev in iter_parsed_events(path, parse_event):
            process(ev)
    """
    for raw in iter_raw_events(path):
        try:
            event = parse_event_func(raw)
        except Exception as e:
            log.debug("Ошибка парсинга события type=%r: %s",
                      raw.get("type"), e)
            continue
        if event is not None:
            yield event