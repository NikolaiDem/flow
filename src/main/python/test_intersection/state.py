# test_intersection/state.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppState:
    all_events: list
    test_events: list
    overlap_dict: dict
    global_min: object | None      # datetime | None
    global_max: object | None      # datetime | None
    flow_html_dir: Path | None = None