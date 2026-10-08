# {
#     "type": "org.springframework.core.metrics.jfr.FlightRecorderStartupEvent",
#     "values": {
#         "startTime": "2026-10-07T11:26:39.022204191+03:00",
#         "duration": "PT0.044989933S",
#         "eventThread": {
#             "osName": "main",
#             "osThreadId": 24440,
#             "javaName": "main",
#             "javaThreadId": 1,
#             "group": {
#                 "parent": {
#                     "parent": null,
#                     "name": "system"
#                 },
#                 "name": "main"
#             },
#             "virtual": false
#         },
#         "stackTrace": {
#             "truncated": true
#         },
#         "eventId": 1,
#         "parentId": 1,
#         "name": "spring.boot.application.starting",
#         "tags": "mainApplicationClass=ru.alfabank.pc.acq.emoney.actualizer.ActualizerIT,"
#     }
#
from __future__ import annotations

import logging
from dataclasses import dataclass

import isodate
from dateutil import parser as dtparser

from event_parsing import JfrEvent

log = logging.getLogger(__name__)

SPRING_STAGE_LABELS = {
    "spring.boot.application.starting": "Spring — application starting",
    "spring.boot.application.environment-prepared": "Spring — environment prepared",
    "spring.boot.application.context-prepared": "Spring — context prepared",
    "spring.boot.application.context-loaded": "Spring — context loaded",
    "spring.boot.application.started": "Spring — started",
}


@dataclass(frozen=True, slots=True)
class SpringEvent(JfrEvent):
    event_id: int | None
    parent_id: int | None
    tags: str


def parse_event(raw: dict) -> SpringEvent | None:
    values = raw.get("values")
    if not values:
        return None
    if raw.get("type") != "org.springframework.core.metrics.jfr.FlightRecorderStartupEvent":
        return None

    name = values.get("name") or "<default-spring-jfr>"
    try:
        start_time = dtparser.isoparse(values["startTime"])
        duration = isodate.parse_duration(values["duration"])
    except (KeyError, ValueError, TypeError) as e:
        log.debug("Некорректное событие: %s (%s)", name, e)
        return None

    thread_name = (values.get("eventThread") or {}).get("javaName") or "<unknown>"

    return SpringEvent(
        thread_name=thread_name,
        start_time=start_time,
        end_time=start_time + duration,
        duration=duration,
        event_type=raw.get("type") or "<unknown>",
        name=name,
        display_name=SPRING_STAGE_LABELS.get(name, name),
        parent_id=values.get("parentId"),  # int | None
        event_id=values.get("eventId"),  # int | None
        tags=values.get("tags") or "",
    )
