import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from jfr_test_intersection import (
    format_to_json,
    collect_all,
    find_overlaps,
    build_overlap_dict,
)


OVERLAP_DICT: dict = {}


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Overlap search</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 900px; }
  input { width: 100%; padding: .6rem; font-size: 1rem; box-sizing: border-box; }
  .item  { margin: 1rem 0; border-bottom: 1px solid #eee; padding-bottom: .8rem; }
  .name  { font-weight: 600; margin-bottom: .3rem; }
  .pair  { display: flex; justify-content: space-between; align-items: baseline;
           padding: .15rem 0; gap: 1rem; }
  .other { flex: 1; }
  .threads { color: #888; font-size: .85em; margin-left: .5rem; }
  .ms    { color: #666; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .empty { color: #999; margin-top: 1rem; }
</style>
</head>
<body>
<h1>Поиск пересечений тестов</h1>
<input id="q" placeholder="Начните вводить название теста..." autofocus>
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

function render(items) {
  if (!items.length) {
    results.innerHTML = '<div class="empty">Ничего не найдено</div>';
    return;
  }
  results.innerHTML = items.map(item => `
    <div class="item">
      <div class="name">${escapeHtml(item.name)}</div>
      ${item.partners.map(p => `
        <div class="pair">
          <span class="other">
            ${escapeHtml(p.other)}
            <span class="threads">[${escapeHtml(p.thread)}]</span>
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
        if not query:
            return []
        result = []
        for name, pairs in OVERLAP_DICT.items():
            if query not in name.lower():
                continue
            partners = []
            for other_event, ms in pairs:
                partners.append({
                    "other": other_event["displayName"],
                    "thread": other_event["threadName"],
                    "ms": ms,
                })
            result.append({"name": name, "partners": partners})

        # сначала те, у кого суммарное время больше
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


def serve(overlap_dict: dict, host="127.0.0.1", port=8000):
    global OVERLAP_DICT
    OVERLAP_DICT = overlap_dict
    print(f"Open http://{host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    jfr_path = Path("D:/work/jfr")
    json_path = Path("D:/work/jfr/json")

    format_to_json(jfr_path, json_path)
    all_events = collect_all(json_path)
    overlaps = find_overlaps(all_events)
    overlap_dict = build_overlap_dict(overlaps)

    serve(overlap_dict)