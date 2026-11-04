# context.py
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from event_parsing import JfrEvent
from test_events import TestCase
from overlaps import build_overlap_dict


class _Unset:
    def __repr__(self) -> str:
        return "<unset>"


_UNSET = _Unset()


class AppContext:
    """
    Ленивый контейнер данных. Все тяжёлые вычисления — при первом обращении.
    Потокобезопасен: ThreadingHTTPServer может дёрнуть два запроса одновременно.
    """

    def __init__(
        self,
        events_loader: Callable[[], list[JfrEvent]],
        *,
        flow_generator: Callable[[], Path | None] | None = None,
        flow_html_dir: Path | None = None,
    ) -> None:
        self._events_loader = events_loader

        # flow: либо уже готовый путь, либо генератор (ленивый), либо ничего
        self._flow_generator = flow_generator
        self._flow_html_dir: Path | None | _Unset = (
            _UNSET if flow_html_dir is None and flow_generator is not None
            else flow_html_dir
        )

        self._lock = threading.Lock()
        self._flow_lock = threading.Lock()

        self._all_events: list[JfrEvent] | None = None
        self._test_events: list[TestCase] | None = None
        self._overlap_dict: dict | None = None
        self._global_min = _UNSET
        self._global_max = _UNSET

    # ---------- events ----------

    @property
    def all_events(self) -> list[JfrEvent]:
        if self._all_events is None:
            with self._lock:
                if self._all_events is None:
                    self._all_events = self._events_loader()
        return self._all_events

    @property
    def test_events(self) -> list[TestCase]:
        if self._test_events is None:
            with self._lock:
                if self._test_events is None:
                    self._test_events = [
                        e for e in self.all_events if isinstance(e, TestCase)
                    ]
        return self._test_events

    @property
    def overlap_dict(self) -> dict:
        if self._overlap_dict is None:
            with self._lock:
                if self._overlap_dict is None:
                    self._overlap_dict = build_overlap_dict(self.all_events)
        return self._overlap_dict

    @property
    def global_min(self):
        if self._global_min is _UNSET:
            with self._lock:
                if self._global_min is _UNSET:
                    self._global_min = min(
                        (e.start_time for e in self.all_events), default=None
                    )
        return self._global_min

    @property
    def global_max(self):
        if self._global_max is _UNSET:
            with self._lock:
                if self._global_max is _UNSET:
                    self._global_max = max(
                        (e.end_time for e in self.all_events), default=None
                    )
        return self._global_max

    # ---------- flow (ленивый) ----------

    @property
    def flow_html_dir(self) -> Path | None:
        """
        Директория flow-HTML.
        - Если путь передан в конструктор — возвращается сразу.
        - Если передан generator — вызывается при первом обращении, результат кэшируется.
        - Если ничего — None.
        """
        if self._flow_html_dir is not _UNSET:
            return self._flow_html_dir        # Path | None, уже посчитано

        if self._flow_generator is None:
            return None

        with self._flow_lock:
            if self._flow_html_dir is _UNSET:
                try:
                    self._flow_html_dir = self._flow_generator()
                except Exception as e:
                    # не валим сервер: flow просто будет пустым
                    import logging
                    logging.getLogger(__name__).warning(
                        "flow generation failed: %s", e, exc_info=True
                    )
                    self._flow_html_dir = None
            return self._flow_html_dir

    # ---------- диагностика ----------

    def loaded_sizes(self) -> dict:
        return {
            "all_events": len(self._all_events) if self._all_events is not None else None,
            "test_events": len(self._test_events) if self._test_events is not None else None,
            "overlap_dict": len(self._overlap_dict) if self._overlap_dict is not None else None,
            "flow_html_dir": str(self._flow_html_dir) if self._flow_html_dir is not _UNSET else None,
        }