# Требования:
# В строке поиска вводится название теста, для которого нужно найти пересекающиеся тесты
# Найденные тесты должны отобразится в виде таймлайна
# У каждого найденного теста должно отобразиться название, поток, результат
# Цвет упавших тестов красный, цвет успешных зеленый. Основной тест выделен в рамку
# Для группы тестов должна быть возможность построить таймлайн для них. Тесты для таймлана можно выбрать
# из раскрывающегося списка, должен быть доступен поиск
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

  /* Стили для выбора группы тестов */
  .group-selector {
    margin: 1.5rem 0;
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 6px;
    border: 1px solid #e0e0e0;
  }
  .group-selector h3 {
    margin: 0 0 .8rem 0;
    font-size: 1rem;
    color: #333;
  }
  .multi-select {
    position: relative;
    width: 100%;
  }
  .multi-select-input {
    width: 100%;
    padding: .5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: .9rem;
    cursor: pointer;
    background: white;
  }
  .multi-select-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    max-height: 300px;
    overflow-y: auto;
    background: white;
    border: 1px solid #ccc;
    border-top: none;
    border-radius: 0 0 4px 4px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    display: none;
    z-index: 100;
  }
  .multi-select-dropdown.open {
    display: block;
  }
  .multi-select-search {
    padding: .5rem;
    border-bottom: 1px solid #eee;
    position: sticky;
    top: 0;
    background: white;
  }
  .multi-select-search input {
    width: 100%;
    padding: .4rem;
    border: 1px solid #ddd;
    border-radius: 3px;
    font-size: .85rem;
  }
  .multi-select-option {
    padding: .5rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: .5rem;
    font-size: .85rem;
  }
  .multi-select-option:hover {
    background: #f0f0f0;
  }
  .multi-select-option input[type="checkbox"] {
    width: auto;
    margin: 0;
  }
  .selected-tags {
    display: flex;
    flex-wrap: wrap;
    gap: .3rem;
    margin-top: .5rem;
  }
  .selected-tag {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    padding: .2rem .5rem;
    background: #e3f2fd;
    border: 1px solid #90caf9;
    border-radius: 3px;
    font-size: .8rem;
  }
  .selected-tag button {
    background: none;
    border: none;
    cursor: pointer;
    color: #666;
    font-size: 1rem;
    line-height: 1;
    padding: 0;
  }
  .selected-tag button:hover {
    color: #c62828;
  }
  .build-timeline-btn {
    margin-top: .8rem;
    padding: .5rem 1rem;
    background: #2196f3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: .9rem;
  }
  .build-timeline-btn:hover {
    background: #1976d2;
  }
  .build-timeline-btn:disabled {
    background: #ccc;
    cursor: not-allowed;
  }
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

<div class="group-selector">
  <h3>Таймлайн для группы тестов</h3>
  <div class="multi-select">
    <input type="text" class="multi-select-input" id="groupInput" 
           placeholder="Выберите тесты для построения таймлайна..." readonly>
    <div class="multi-select-dropdown" id="groupDropdown">
      <div class="multi-select-search">
        <input type="text" id="groupSearch" placeholder="Поиск...">
      </div>
      <div id="groupOptions"></div>
    </div>
  </div>
  <div class="selected-tags" id="selectedTags"></div>
  <button class="build-timeline-btn" id="buildBtn" disabled>
    Построить таймлайн
  </button>
  <div id="groupTimeline"></div>
</div>

<script>
const q = document.getElementById('q');
const results = document.getElementById('results');
const groupInput = document.getElementById('groupInput');
const groupDropdown = document.getElementById('groupDropdown');
const groupSearch = document.getElementById('groupSearch');
const groupOptions = document.getElementById('groupOptions');
const selectedTags = document.getElementById('selectedTags');
const buildBtn = document.getElementById('buildBtn');
const groupTimeline = document.getElementById('groupTimeline');
let timer = null;
let allTests = [];
let selectedTests = new Set();

q.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(search, 150);
});

// Загружаем список всех тестов при старте
async function loadAllTests() {
  const r = await fetch('/all-tests');
  allTests = await r.json();
  renderGroupOptions();
}

groupInput.addEventListener('click', (e) => {
  e.stopPropagation();
  groupDropdown.classList.toggle('open');
  if (groupDropdown.classList.contains('open')) {
    groupSearch.focus();
  }
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.multi-select')) {
    groupDropdown.classList.remove('open');
  }
});

groupSearch.addEventListener('input', () => {
  renderGroupOptions(groupSearch.value);
});

function renderGroupOptions(filter = '') {
  const lowerFilter = filter.toLowerCase();
  const filtered = allTests.filter(t => 
    t.name.toLowerCase().includes(lowerFilter) ||
    t.thread.toLowerCase().includes(lowerFilter)
  );

  groupOptions.innerHTML = filtered.map(t => `
    <div class="multi-select-option" data-name="${escapeHtml(t.name)}">
      <input type="checkbox" ${selectedTests.has(t.name) ? 'checked' : ''}>
      <span>${escapeHtml(t.name)}</span>
      <span class="threads">[${escapeHtml(t.thread)}]</span>
      <span class="status ${statusClass(t.result)}">${escapeHtml(t.result)}</span>
    </div>
  `).join('');

  groupOptions.querySelectorAll('.multi-select-option').forEach(opt => {
    opt.addEventListener('click', (e) => {
      e.stopPropagation();
      const name = opt.dataset.name;
      if (selectedTests.has(name)) {
        selectedTests.delete(name);
      } else {
        selectedTests.add(name);
      }
      renderGroupOptions(groupSearch.value);
      renderSelectedTags();
      updateBuildBtn();
    });
  });
}

function renderSelectedTags() {
  selectedTags.innerHTML = Array.from(selectedTests).map(name => `
    <span class="selected-tag">
      ${escapeHtml(name)}
      <button onclick="removeTest('${escapeHtml(name).replace(/'/g, "\\'")}')">&times;</button>
    </span>
  `).join('');
}

function removeTest(name) {
  selectedTests.delete(name);
  renderGroupOptions(groupSearch.value);
  renderSelectedTags();
  updateBuildBtn();
}

function updateBuildBtn() {
  buildBtn.disabled = selectedTests.size < 2;
}

buildBtn.addEventListener('click', async () => {
  if (selectedTests.size < 2) return;

  const names = Array.from(selectedTests);
  const r = await fetch('/group-timeline', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({names})
  });
  const data = await r.json();
  renderGroupTimeline(data);
});

function renderGroupTimeline(data) {
  if (!data.rows || !data.rows.length) {
    groupTimeline.innerHTML = '<div class="empty">Нет данных для отображения</div>';
    return;
  }

  groupTimeline.innerHTML = `
    <div class="item" style="margin-top:1rem">
      <div class="name">Таймлайн группы тестов (${data.rows.length} шт.)</div>
      <div class="timeline">
        ${data.rows.map(r => `
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
        <span>${data.axis_start}</span>
        <span>${data.axis_end}</span>
      </div>
    </div>
  `;
}

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

// Загружаем список тестов при старте
loadAllTests();
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


def _build_group_timeline(test_names: list[str]) -> dict:
    """Строит таймлайн для группы выбранных тестов."""
    if not test_names or GLOBAL_MIN is None or GLOBAL_MAX is None:
        return {"rows": [], "axis_start": "", "axis_end": ""}

    axis_start = _ts_to_ms(GLOBAL_MIN)
    axis_end = _ts_to_ms(GLOBAL_MAX)
    span = max(axis_end - axis_start, 1.0)

    # Собираем все тесты по именам
    tests_to_show: list[TestCase] = []
    seen = set()

    for test in OVERLAP_DICT.keys():
        if test.display_name in test_names and test.display_name not in seen:
            tests_to_show.append(test)
            seen.add(test.display_name)

    # Сортируем по времени начала
    tests_to_show.sort(key=lambda t: t.start_time)

    def pct(ms_abs: float) -> float:
        return (ms_abs - axis_start) / span * 100.0

    rows = []
    for tc in tests_to_show:
        left = pct(_ts_to_ms(tc.start_time))
        right = pct(_ts_to_ms(tc.end_time))
        rows.append({
            "name": tc.display_name,
            "thread": tc.thread_name,
            "result": tc.result,
            "cls": _result_class(tc.result),
            "left": round(left, 3),
            "width": round(max(right - left, 0.4), 3),
            "title": f"{tc.display_name} [{tc.thread_name}] "
                     f"result={tc.result} "
                     f"{tc.duration.total_seconds() * 1000:.1f} ms",
        })

    return {
        "rows": rows,
        "axis_start": _fmt_dt(GLOBAL_MIN),
        "axis_end": _fmt_dt(GLOBAL_MAX),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
        elif parsed.path == "/search":
            q = parse_qs(parsed.query).get("q", [""])[0].strip().lower()
            self._send_json(self._search(q))
        elif parsed.path == "/all-tests":
            self._send_json(self._all_tests())
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/group-timeline":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            names = data.get('names', [])
            self._send_json(_build_group_timeline(names))
        else:
            self.send_error(404)

    def _all_tests(self):
        """Возвращает список всех тестов для выбора в группу."""
        result = []
        seen = set()
        for test in OVERLAP_DICT.keys():
            if test.display_name not in seen:
                seen.add(test.display_name)
                result.append({
                    "name": test.display_name,
                    "thread": test.thread_name,
                    "result": test.result,
                })
        result.sort(key=lambda x: x["name"])
        return result

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

    print(f"Open http://{host}:{port}\n")
    HTTPServer((host, port), Handler).serve_forever()