# Требования:
# В строке поиска вводится название теста, для которого нужно найти пересекающиеся тесты
# Найденные тесты должны отобразится в виде таймлайна
# У каждого найденного теста должно отобразиться название, поток, результат
# Цвет упавших тестов красный, цвет успешных зеленый. Основной тест выделен в рамку
# server.py
from __future__ import annotations

import json
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from jfr_test_intersection import Overlap, TestCase


log = logging.getLogger(__name__)

OVERLAP_DICT: dict = {}
ALL_EVENTS: list = []
GLOBAL_MIN: datetime | None = None
GLOBAL_MAX: datetime | None = None


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Overlap search</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem;
         max-width: 1200px; color: #222; }
  input { width: 100%; padding: .6rem; font-size: 1rem; box-sizing: border-box; }
  .item { margin: 1.5rem 0; border-bottom: 1px solid #eee; padding-bottom: 1rem; }
  .name { font-weight: 600; margin-bottom: .5rem; font-size: 1.05rem;
          display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap; }

  .status {
    font-size: .75rem;
    font-weight: 600;
    padding: .1rem .5rem;
    border-radius: 10px;
    text-transform: uppercase;
    letter-spacing: .03em;
  }
  .status.passed { background: #e3f5e0; color: #2e7d32; }
  .status.failed { background: #fde7e5; color: #c62828; }
  .status.other  { background: #eee; color: #666; }

  .timeline {
    margin: .3rem 0 .3rem 0;
    border-left: 1px solid #ddd;
    border-right: 1px solid #ddd;
    background: #fafbfc;
  }
  .row {
    display: flex;
    align-items: center;
    height: 24px;
    border-bottom: 1px solid #eef1f4;
  }
  .row:last-child { border-bottom: none; }
  .row-label {
    width: 260px;
    flex: 0 0 260px;
    font-size: .8rem;
    color: #555;
    padding: 0 .5rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
  }
  .row-label .threads { color: #999; margin-left: .3rem; }
  .row-track {
    position: relative;
    flex: 1;
    height: 100%;
    background: #ffffff;
  }
  .bar {
    position: absolute;
    top: 4px; bottom: 4px;
    border-radius: 3px;
    opacity: .9;
    cursor: help;
  }
  /* Цвет по результату теста */
  .bar.passed { background: #7bb86f; }
  .bar.failed { background: #e25c4a; }
  .bar.other  { background: #9aa4ad; }

  /* Искомый тест выделен рамкой (цвет — по статусу) */
  .bar.highlight {
    opacity: 1;
    outline: 2px solid #222;
    outline-offset: 0;
    box-shadow: 0 0 0 1px #fff inset;
    z-index: 1;
  }

  .pair { display: flex; justify-content: space-between; align-items: baseline;
          padding: .15rem 0; gap: 1rem; }
  .other { flex: 1; }
  .threads { color: #888; font-size: .85em; margin-left: .5rem; }
  .ms { color: #666; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .empty { color: #999; margin-top: 1rem; }
  .axis { display: flex; justify-content: space-between;
          font-size: .75rem; color: #999;
          margin-left: 260px; }
  .legend { font-size: .8rem; color: #666; margin: .3rem 0 1rem 0; }
  .legend span { display: inline-block; width: 12px; height: 12px;
                 border-radius: 2px; margin-right: .3rem;
                 vertical-align: middle; }
</style>
</head>
<body>
<h1>Поиск пересечений тестов</h1>
<input id="q" placeholder="Начните вводить название теста..." autofocus>

<div class="legend">
  <span style="background:#7bb86f"></span>успешный
  <span style="background:#e25c4a; margin-left:1rem"></span>упавший
  <span style="background:#9aa4ad; margin-left:1rem"></span>прочее
  <span style="border:2px solid #222; width:8px; height:8px; background:transparent; margin-left:1rem"></span>искомый тест
</div>

<div id="results"></div>

<script>
const q = document.getElementById('q');
const results = document.getElementById('results');
let timer = null;

q.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(search, 150);
});

async function search() {
  const query = q.value.trim();
  if (!query) { results.innerHTML = ''; return; }
  const r = await fetch('/search?q=' + encodeURIComponent(query));
  const data = await r.json();
  render(data);
}

function statusClass(result) {
  const r = String(result || '').toUpperCase();
  if (r === 'PASSED' || r === 'SUCCESS' || r === 'SUCCESSFUL') return 'passed';
  if (r === 'FAILED' || r === 'FAILURE' || r === 'ERROR') return 'failed';
  return 'other';
}

function render(items) {
  if (!items.length) {
    results.innerHTML = '<div class="empty">Ничего не найдено</div>';
    return;
  }
  results.innerHTML = items.map(item => `
    <div class="item">
      <div class="name">
        <span>${escapeHtml(item.name)}</span>
        <span class="threads">[${escapeHtml(item.thread)}]</span>
        <span class="status ${statusClass(item.result)}">${escapeHtml(item.result)}</span>
      </div>

      <div class="timeline">
        ${item.rows.map(r => `
          <div class="row">
            <div class="row-label" title="${escapeHtml(r.name)} [${escapeHtml(r.thread)}] — ${escapeHtml(r.result)}">
              ${escapeHtml(r.name)}
              <span class="threads">[${escapeHtml(r.thread)}]</span>
            </div>
            <div class="row-track">
              <div class="bar ${r.cls}"
                   style="left:${r.left}%; width:${r.width}%"
                   title="${escapeHtml(r.title)}"></div>
            </div>
          </div>
        `).join('')}
      </div>
      <div class="axis">
        <span>${item.axis_start}</span>
        <span>${item.axis_end}</span>
      </div>

      ${item.partners.map(p => `
        <div class="pair">
          <span class="other">
            ${escapeHtml(p.other)}
            <span class="threads">[${escapeHtml(p.thread)}]</span>
            <span class="status ${statusClass(p.result)}">${escapeHtml(p.result)}</span>
          </span>
          <span class="ms">${p.ms.toFixed(1)} ms</span>
        </div>
      `).join('')}
    </div>
  `).join('');
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}
</script>
</body>
</html>
"""


def _ts_to_ms(dt: datetime) -> float:
    return dt.timestamp() * 1000.0


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S.%f")[:-3]


def _result_class(result: str) -> str:
    """PASSED/SUCCESS -> passed, FAILED/ERROR -> failed, иначе other."""
    r = (result or "").upper()
    if r in ("PASSED", "SUCCESS", "SUCCESSFUL"):
        return "passed"
    if r in ("FAILED", "FAILURE", "ERROR"):
        return "failed"
    return "other"


def _build_timeline(
    main: TestCase,
    partners: list[Overlap],
    axis_start_ms: float,
    axis_end_ms: float,
) -> list[dict]:
    """
    Возвращает список строк таймлайна — по одной на тест:
      [ {name, thread, result, cls, left, width, title}, ... ]
    Первая строка — искомый тест, дальше — партнёры.
    Все координаты — проценты от общего окна [0..100].
    """
    span = max(axis_end_ms - axis_start_ms, 1.0)

    def pct(ms_abs: float) -> float:
        return (ms_abs - axis_start_ms) / span * 100.0

    def make_row(tc: TestCase, extra_cls: str, title: str) -> dict:
        left = pct(_ts_to_ms(tc.start_time))
        right = pct(_ts_to_ms(tc.end_time))
        cls = f"{_result_class(tc.result)} {extra_cls}".strip()
        return {
            "name": tc.display_name,
            "thread": tc.thread_name,
            "result": tc.result,
            "cls": cls,
            "left": round(left, 3),
            "width": round(max(right - left, 0.4), 3),  # минимум для видимости
            "title": title,
        }

    rows: list[dict] = []

    # 1) Искомый тест — сверху, с рамкой
    rows.append(make_row(
        main,
        extra_cls="highlight",
        title=f"{main.display_name} [{main.thread_name}] "
              f"result={main.result} "
              f"{main.duration.total_seconds() * 1000:.1f} ms",
    ))

    # 2) Каждый партнёр — на своей строке
    for ov in partners:
        other = ov.other
        rows.append(make_row(
            other,
            extra_cls="",
            title=f"{other.display_name} [{other.thread_name}] "
                  f"result={other.result} "
                  f"пересечение {ov.intersection_ms:.1f} ms",
        ))

    return rows


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
        elif parsed.path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            self._send_json(self._search(q))
        else:
            self.send_error(404)

    def _search(self, query: str):
        if not query or GLOBAL_MIN is None or GLOBAL_MAX is None:
            return []

        axis_start = _ts_to_ms(GLOBAL_MIN)
        axis_end = _ts_to_ms(GLOBAL_MAX)

        result = []
        for test, partners in OVERLAP_DICT.items():
            if query not in test.display_name.lower():
                continue

            partners_json = [
                {
                    "other": ov.other.display_name,
                    "thread": ov.other.thread_name,
                    "result": ov.other.result,
                    "ms": ov.intersection_ms,
                }
                for ov in partners
            ]
            rows = _build_timeline(test, partners, axis_start, axis_end)
            result.append({
                "name": test.display_name,
                "thread": test.thread_name,
                "result": test.result,
                "partners": partners_json,
                "rows": rows,
                "axis_start": _fmt_dt(GLOBAL_MIN),
                "axis_end": _fmt_dt(GLOBAL_MAX),
            })

        result.sort(key=lambda x: -sum(p["ms"] for p in x["partners"]))
        return result[:50]

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def serve(overlap_dict: dict, all_events: list,
          host: str = "127.0.0.1", port: int = 8000) -> None:
    global OVERLAP_DICT, ALL_EVENTS, GLOBAL_MIN, GLOBAL_MAX
    OVERLAP_DICT = overlap_dict
    ALL_EVENTS = all_events
    if all_events:
        GLOBAL_MIN = min(e.start_time for e in all_events)
        GLOBAL_MAX = max(e.end_time for e in all_events)

    print(f"\n  → Откройте http://{host}:{port}\n")
    HTTPServer((host, port), Handler).serve_forever()