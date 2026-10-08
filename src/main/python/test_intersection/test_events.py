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

import logging
import re
from dataclasses import dataclass

import isodate
from dateutil import parser as dtparser

from event_parsing import JfrEvent

log = logging.getLogger(__name__)


_CLASS_RE = re.compile(r'\[class:([^\]]+)\]')
_METHOD_RE = re.compile(r'\[method:([^\]]+)\]')


@dataclass(frozen=True, slots=True)
class TestCase(JfrEvent):
    class_name: str
    method_name: str
    result: str
    value_type: str


def _parse_unique_id(unique_id: str) -> tuple[str, str]:
    if not unique_id:
        return "", ""
    cm = _CLASS_RE.search(unique_id)
    mm = _METHOD_RE.search(unique_id)
    return (
        cm.group(1) if cm else "",
        mm.group(1) if mm else "",
    )


def parse_event(raw: dict) -> TestCase | None:
    """Преобразует одно событие JFR в TestCase. None, если данных не хватает."""
    values = raw.get("values")
    if not values:
        return None
    if raw.get("type") != "org.junit.TestExecution":
        return None
    values = raw.get("values") or {}
    if values.get("type") != "TEST":
        return None
    try:
        start_time = dtparser.isoparse(values["startTime"])
        duration = isodate.parse_duration(values["duration"])
    except (KeyError, ValueError, TypeError) as e:
        log.debug("Некорректное событие: %s (%s)",
                  values.get("displayName"), e)
        return None

    thread_name = (values.get("eventThread") or {}).get("javaName") or "<unknown>"
    class_name, method_name = _parse_unique_id(values.get("uniqueId") or "")

    return TestCase(
        class_name=class_name,
        method_name=method_name,
        display_name=values.get("displayName") or "<unnamed>",
        thread_name=thread_name,
        start_time=start_time,
        end_time=start_time + duration,
        duration=duration,
        result=values.get("result") or "<unknown>",
        event_type=raw.get("type") or "<unknown>",
        value_type=values.get("type") or "<unknown>",
    )
