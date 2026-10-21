# render_html.py
import json
from collections import Counter, defaultdict
from pathlib import Path


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Flow call graphs by thread</title>
<script type="text/javascript"
  src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Segoe UI', Consolas, monospace;
    background: #f5f7fa;
    color: #222;
  }
  #tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding: 8px 12px;
    background: #fff;
    border-bottom: 1px solid #ddd;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .tab {
    padding: 6px 14px;
    border: 1px solid #ccc;
    border-radius: 6px 6px 0 0;
    background: #fafafa;
    cursor: pointer;
    font-size: 13px;
    font-family: Consolas, monospace;
    white-space: nowrap;
  }
  .tab:hover { background: #eef3ff; }
  .tab.active {
    background: #4363d8;
    color: #fff;
    border-color: #4363d8;
  }
  .tab .badge {
    display: inline-block;
    margin-left: 6px;
    padding: 0 6px;
    border-radius: 8px;
    background: rgba(0,0,0,0.12);
    font-size: 11px;
  }
  .tab.active .badge { background: rgba(255,255,255,0.25); }

  #controls {
    padding: 8px 12px;
    background: #fff;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    display: flex;
    gap: 16px;
    align-items: center;
  }
  #controls label { display: flex; align-items: center; gap: 4px; }

  .graph-container {
    position: relative;
    width: 100%;
    height: calc(100vh - 120px);
  }
  .graph-canvas {
    width: 100%;
    height: 100%;
    display: none;
  }
  .graph-canvas.active { display: block; }

  #legend {
    position: fixed;
    top: 110px;
    right: 16px;
    z-index: 20;
    background: rgba(255,255,255,0.97);
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 10px 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.12);
    font-family: Consolas, monospace;
    font-size: 12px;
    max-height: 60vh;
    overflow-y: auto;
    min-width: 200px;
  }
  #legend h3 { margin: 0 0 6px 0; font-size: 13px; }
  #legend .edge-item {
    display: flex; align-items: center; gap: 8px; margin: 4px 0;
  }
</style>
</head>
<body>

<div id="tabs"></div>

<div id="controls">
  <label>
    <input type="checkbox" id="cb-seq" checked>
    показывать последовательные рёбра (эвристика)
  </label>
</div>

<div class="graph-container" id="graphs"></div>

<div id="legend">
  <h3>Легенда</h3>
  <div class="edge-item">
    <svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5"
      stroke="#555" stroke-width="2"/></svg>
    <span>вложенный вызов</span>
  </div>
  <div class="edge-item">
    <svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5"
      stroke="#e6194b" stroke-width="2" stroke-dasharray="6,4"/></svg>
    <span>последовательный (эвристика)</span>
  </div>
</div>

<script>
// Данные инжектируются из Python: массив по потокам
const THREAD_GRAPHS = __THREAD_GRAPHS_JSON__;
const SEQ_ENABLED_DEFAULT = true;

// Глобальный реестр: thread_id -> {nodes, edges, network, ...}
const registry = {};

function makeNetwork(containerId, threadData) {
  const nodes = new vis.DataSet(threadData.nodes);
  const edges = new vis.DataSet(
    threadData.edges.filter(e => e.kind === 'nested' || SEQ_ENABLED_DEFAULT)
  );

  const allEdgesByKind = threadData.edges;

  const container = document.getElementById(containerId);
  const network = new vis.Network(container, {nodes, edges}, {
    physics: { enabled: false },
    edges: {
      smooth: {
        type: 'cubicBezier',
        forceDirection: 'vertical',
        roundness: 0.4,
      },
      arrowStrikethrough: false,
      width: 1.2,
    },
    nodes: {
      margin: 10,
      widthConstraint: { maximum: 240 },
      font: { size: 13, face: 'Consolas, monospace' },
    },
    interaction: {
      hover: true,
      tooltipDelay: 120,
      navigationButtons: true,
      keyboard: { enabled: true },
      multiselect: true,
    },
    layout: {
      hierarchical: {
        enabled: true,
        direction: 'UD',
        sortMethod: 'directed',
        levelSeparation: 180,
        nodeSpacing: 260,      // <-- главный параметр против наложений
        treeSpacing: 320,
        blockShifting: false,  // чтобы nodeSpacing не «съедался»
        edgeMinimization: true,
        parentCentralization: true,
        shakeTowards: 'roots',
      },
    },
  });

  registry[threadData.thread_id] = {
    network, nodes, edges, allEdgesByKind,
  };
  return network;
}

function rebuildEdges(threadId, showSeq) {
  const rec = registry[threadId];
  if (!rec) return;
  const filtered = rec.allEdgesByKind.filter(
    e => e.kind === 'nested' || showSeq
  );
  rec.edges.clear();
  rec.edges.add(filtered);
}

// --- построение вкладок и canvas ---
const tabsEl = document.getElementById('tabs');
const graphsEl = document.getElementById('graphs');

THREAD_GRAPHS.forEach((threadData, idx) => {
  // кнопка вкладки
  const tab = document.createElement('div');
  tab.className = 'tab' + (idx === 0 ? ' active' : '');
  tab.dataset.threadId = threadData.thread_id;
  tab.innerHTML = `${threadData.thread_id}` +
    `<span class="badge">${threadData.nodes.length}</span>`;
  tab.onclick = () => activateThread(threadData.thread_id);
  tabsEl.appendChild(tab);

  // canvas
  const div = document.createElement('div');
  div.className = 'graph-canvas' + (idx === 0 ? ' active' : '');
  div.id = 'graph-' + idx;
  div.style.height = '100%';
  div.style.width = '100%';
  div.style.border = '1px solid #ddd';
  div.style.borderRadius = '6px';
  div.style.background = '#fff';
  div.style.margin = '8px';
  graphsEl.appendChild(div);

  // создаём network
  makeNetwork(div.id, threadData);
});

let activeThread = THREAD_GRAPHS.length ? THREAD_GRAPHS[0].thread_id : null;

function activateThread(threadId) {
  activeThread = threadId;
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.threadId === threadId);
  });
  THREAD_GRAPHS.forEach((t, idx) => {
    const el = document.getElementById('graph-' + idx);
    el.classList.toggle('active', t.thread_id === threadId);
  });
  // пересчитать размер — vis.Network не всегда видит смену display
  const rec = registry[threadId];
  if (rec) {
    setTimeout(() => {
      rec.network.redraw();
      rec.network.fit();
    }, 30);
  }
}

// переключатель последовательных рёбер
document.getElementById('cb-seq').addEventListener('change', (e) => {
  const show = e.target.checked;
  Object.keys(registry).forEach(tid => rebuildEdges(tid, show));
});

// при ресайзе окна — пересчитать активный canvas
window.addEventListener('resize', () => {
  const rec = registry[activeThread];
  if (rec) rec.network.redraw();
});
</script>
</body>
</html>
"""


def render_by_thread_html(
    per_thread: list[dict],
    out_path: Path,
    *,
    show_sequential: bool = True,
    level_separation: int = 180,
    node_spacing: int = 260,
    tree_spacing: int = 320,
) -> None:
    """
    per_thread — список словарей вида:
      {
        "thread_id": "thread-main",
        "nodes": [ {id, label, title, shape, color, borderWidth, font}, ... ],
        "edges": [ {from, to, arrows, color, width, title, dashes, kind}, ... ],
      }
    где kind ∈ {"nested", "sequential"}.
    """
    payload = json.dumps(per_thread, ensure_ascii=False)
    html = (
        HTML_TEMPLATE
        .replace("__THREAD_GRAPHS_JSON__", payload)
        .replace("__SEQ_ENABLED__", "true" if show_sequential else "false")
        .replace("levelSeparation: 180", f"levelSeparation: {level_separation}")
        .replace("nodeSpacing: 260", f"nodeSpacing: {node_spacing}")
        .replace("treeSpacing: 320", f"treeSpacing: {tree_spacing}")
    )
    out_path.write_text(html, encoding="utf-8")