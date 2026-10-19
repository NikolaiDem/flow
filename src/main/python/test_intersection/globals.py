from __future__ import annotations

from datetime import datetime

from event_parsing import JfrEvent

OVERLAP_DICT: dict = {}
ALL_EVENTS: list = [JfrEvent]
TEST_EVENTS: list = []
GLOBAL_MIN: datetime | None = None
GLOBAL_MAX: datetime | None = None