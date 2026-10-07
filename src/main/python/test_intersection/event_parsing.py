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
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re
import isodate
from dateutil import parser as dtparser

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Модель данных
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class TestCase:
    class_name: str
    method_name: str
    display_name: str
    thread_name: str
    start_time: datetime
    end_time: datetime
    duration: timedelta
    result: str
    event_type: str
    value_type: str

    def __post_init__(self) -> None:
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) < start_time ({self.start_time}) "
                f"for {self.display_name!r}"
            )

    def __str__(self) -> str:
        return (
            f"[{self.thread_name}] {self.display_name} "
            f"({self.duration.total_seconds():.3f}s) result={self.result}"
        )


def _parse_unique_id(unique_id: str) -> tuple[str, str]:
    class_match = re.search(r'\[class:([^\]]+)\]', unique_id)
    method_match = re.search(r'\[method:([^\]]+)\]', unique_id)

    class_name = class_match.group(1) if class_match else ""
    method_name = method_match.group(1) if method_match else ""

    return class_name, method_name


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
    class_name, method_name = _parse_unique_id(values.get("uniqueId", ""))
    return TestCase(
        class_name=class_name,
        method_name=method_name,
        display_name=values.get("displayName", "<unnamed>"),
        thread_name=thread_name,
        start_time=start_time,
        end_time=start_time + duration,
        duration=duration,
        result=values.get("result", "<unknown>"),
        event_type=raw.get("type", "<unknown>"),
        value_type=values.get("type", "<unknown>"),
    )

def _matches(value: str | None, allowed: list[str] | None) -> bool:
    """Фильтр не задан → пропускаем. Иначе проверяем вхождение."""
    return allowed is None or value in allowed


def parse_file(path: Path,
               event_types: list[str] | None = None,
               value_types: list[str] | None = None, ) -> list[TestCase]:
    """Читает один JSON и возвращает список TestCase (только TEST-события)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("recording", {}).get("events", [])
    result: list[TestCase] = []

    for e in events:
        if not _matches(e.get("type"), event_types):
            continue
        values = e.get("values") or {}
        if not _matches(values.get("type"), value_types):
            continue

        tc = parse_event(e)
        if tc is not None:
            result.append(tc)

    return result
