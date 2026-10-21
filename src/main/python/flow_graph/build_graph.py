import json
import sys
import random
import webbrowser
from pathlib import Path
from collections import defaultdict, Counter

# ---------- Настройки ----------

INPUT_PATH       = Path("D:/work/stacks/current.json")
OUTPUT_HTML      = Path("call_graph.html")
DEMO_SEED        = 42
SAVE_DEMO_JSON   = None
SHOW_FULL_CLASS  = False
OPEN_BROWSER     = True
HIERARCHICAL     = True    # топологическая раскладка сверху вниз

# "border" | "cluster" | "none"
THREAD_MODE      = "border"

# Показывать ли «последовательные» рёбра (эвристика: ENTER при пустом стеке)
SHOW_SEQUENTIAL  = True

Node = tuple[str, str]


# ---------- 1. Построение графа ----------

def build_call_graph(events_by_thread: dict[str, list[dict]]):
    """
    Возвращает:
      graph            : caller -> set(callee)            (реальная вложенность)
      sequential_graph : caller -> set(callee)            (последовательные вызовы)
      node_threads     : node -> Counter(thread_id -> count)
      thread_calls     : thread_id -> set(node)
    """
    graph: dict[Node, set[Node]] = defaultdict(set)
    sequential_graph: dict[Node, set[Node]] = defaultdict(set)
    node_threads: dict[Node, Counter] = defaultdict(Counter)
    thread_calls: dict[str, set[Node]] = defaultdict(set)
    all_nodes: set[Node] = set()
    warnings: list[str] = []

    for thread_id, events in events_by_thread.items():
        stack: list[Node] = []
        last_root: Node | None = None

        for i, ev in enumerate(events):
            node: Node = (ev["className"], ev["methodName"])
            ntype = ev["type"].upper()
            all_nodes.add(node)

            if ntype == "ENTER":
                node_threads[node][thread_id] += 1
                thread_calls[thread_id].add(node)

                if stack:
                    graph[stack[-1]].add(node)
                else:
                    if last_root is not None and last_root != node:
                        sequential_graph[last_root].add(node)
                    last_root = node

                stack.append(node)

            elif ntype == "EXIT":
                if stack and stack[-1] == node:
                    stack.pop()
                elif node in stack:
                    warnings.append(
                        f"[{thread_id}#{i}] EXIT {node} не на вершине стека "
                        f"(вершина={stack[-1]}), откат"
                    )
                    while stack and stack[-1] != node:
                        stack.pop()
                    if stack:
                        stack.pop()
                else:
                    warnings.append(
                        f"[{thread_id}#{i}] EXIT {node} без соответствующего ENTER"
                    )

            else:
                warnings.append(f"[{thread_id}#{i}] неизвестный type={ntype!r}")

        if stack:
            warnings.append(
                f"[{thread_id}] поток завершился с незакрытыми вызовами: "
                + " -> ".join(f"{c}.{m}" for c, m in stack)
            )

    for n in all_nodes:
        graph.setdefault(n, set())
        sequential_graph.setdefault(n, set())

    for w in warnings:
        print("WARN:", w, file=sys.stderr)

    return dict(graph), dict(sequential_graph), dict(node_threads), dict(thread_calls)


# ---------- 2. Палитра потоков ----------

THREAD_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324",
    "#fffac8", "#800000", "#aaffc3", "#808000", "#ffd8b1", "#000075",
]


def thread_color_map(thread_ids: list[str]) -> dict[str, str]:
    return {tid: THREAD_PALETTE[i % len(THREAD_PALETTE)]
            for i, tid in enumerate(sorted(thread_ids))}


# ---------- 3. Визуализация ----------

def visualize_pyvis(
    graph: dict[Node, set[Node]],
    sequential_graph: dict[Node, set[Node]],
    node_threads: dict[Node, Counter],
    thread_calls: dict[str, set[Node]],
    out_path: Path,
    show_full_class: bool = False,
    open_browser: bool = True,
    hierarchical: bool = False,
    thread_mode: str = "border",
    show_sequential: bool = True,
) -> None:
    from pyvis.network import Network

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def node_id(n: Node) -> str:
        return f"{n[0]}#{n[1]}"

    def node_label(n: Node) -> str:
        return f"{short_class(n[0])}\n{n[1]}"

    def node_title(n: Node) -> str:
        lines = [f"{n[0]}.{n[1]}"]
        counter = node_threads.get(n, Counter())
        if counter:
            total = sum(counter.values())
            lines.append(f"Вызовов: {total}")
            lines.append("Потоки:")
            for tid, cnt in counter.most_common():
                lines.append(f"  • {tid}: {cnt}")
        return "\n".join(lines)

    indeg: dict[Node, int] = defaultdict(int)
    outdeg: dict[Node, int] = defaultdict(int)
    for caller, callees in graph.items():
        outdeg[caller] += len(callees)
        for c in callees:
            indeg[c] += 1

    def node_fill(n: Node) -> str:
        weight = indeg[n] + outdeg[n]
        if weight >= 6:
            return "#5b8def"
        if weight >= 3:
            return "#8fb3f5"
        if indeg[n] and not outdeg[n]:
            return "#a8d5a8"
        return "#e8f0fe"

    colors = thread_color_map(list(thread_calls.keys()))

    def dominant_thread(n: Node) -> str | None:
        counter = node_threads.get(n, Counter())
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    def node_border(n: Node) -> str:
        if thread_mode != "border":
            return "#888888"
        tid = dominant_thread(n)
        return colors.get(tid, "#888888") if tid else "#888888"

    def node_border_width(n: Node) -> float:
        return 3 if thread_mode == "border" else 1

    height = "1400px" if hierarchical else "900px"

    net = Network(
        height=height,
        width="100%",
        directed=True,
        notebook=False,
        bgcolor="#ffffff",
        font_color="#222222",
    )

    all_nodes = set(graph.keys())
    for callees in graph.values():
        all_nodes |= callees
    for callees in sequential_graph.values():
        all_nodes |= callees

    node_to_cluster: dict[Node, str] = {}
    if thread_mode == "cluster":
        for n in all_nodes:
            tid = dominant_thread(n)
            if tid is not None:
                node_to_cluster[n] = tid

    for n in all_nodes:
        kwargs = dict(
            label=node_label(n),
            title=node_title(n),
            shape="box",
            color={"background": node_fill(n), "border": node_border(n)},
            borderWidth=node_border_width(n),
            font={"size": 14, "face": "Consolas, monospace"},
        )
        if thread_mode == "cluster" and n in node_to_cluster:
            kwargs["group"] = node_to_cluster[n]
        net.add_node(node_id(n), **kwargs)

    # --- реальные (вложенные) рёбра: сплошные ---
    for caller, callees in graph.items():
        for callee in callees:
            is_self = caller == callee
            net.add_edge(
                node_id(caller),
                node_id(callee),
                arrows="to",
                color={"color": "#555555", "highlight": "#000000"},
                width=1.5,
                title=f"[вложенный вызов]\n"
                      f"{caller[0]}.{caller[1]} -> {callee[0]}.{callee[1]}",
                selfReferenceSize=20 if is_self else 0,
                dashes=False,
            )

    # --- «последовательные» рёбра: пунктир ---
    if show_sequential:
        for caller, callees in sequential_graph.items():
            for callee in callees:
                if callee in graph.get(caller, set()):
                    continue
                is_self = caller == callee
                net.add_edge(
                    node_id(caller),
                    node_id(callee),
                    arrows="to",
                    color={"color": "#e6194b", "highlight": "#a00030"},
                    width=1.2,
                    title=f"[последовательный вызов, эвристика]\n"
                          f"{caller[0]}.{caller[1]} -> {callee[0]}.{callee[1]}",
                    selfReferenceSize=20 if is_self else 0,
                    dashes=[6, 4],
                )

    # --- ОДИН раз выбираем опции в зависимости от режима ---
    groups_opt = {
        tid: {"color": {"border": colors[tid], "background": "#ffffff"}}
        for tid in colors
    } if thread_mode == "cluster" else {}

    common_interaction = {
        "hover": True,
        "tooltipDelay": 120,
        "navigationButtons": True,
        "keyboard": {"enabled": True},
        "multiselect": True,
    }

    if hierarchical:
        options = {
            "physics": {"enabled": False},
            "edges": {
                "smooth": {
                    "type": "cubicBezier",
                    "forceDirection": "vertical",
                    "roundness": 0.4,
                },
                "arrowStrikethrough": False,
                "width": 1.2,
            },
            "nodes": {
                "margin": 10,
                "widthConstraint": {"maximum": 220},
                "font": {"size": 13, "face": "Consolas, monospace"},
            },
            "interaction": common_interaction,
            "layout": {
                "hierarchical": {
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "levelSeparation": 150,
                    "nodeSpacing": 120,
                    "treeSpacing": 200,
                    "blockShifting": True,
                    "edgeMinimization": True,
                    "parentCentralization": True,
                    "shakeTowards": "roots",
                }
            },
            "groups": groups_opt,
        }
    else:
        options = {
            "physics": {
                "enabled": True,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                    "gravitationalConstant": -80,
                    "centralGravity": 0.01,
                    "springLength": 180,
                    "springConstant": 0.08,
                    "damping": 0.4,
                },
                "stabilization": {"enabled": True, "iterations": 500},
            },
            "edges": {
                "smooth": {"type": "cubicBezier",
                           "forceDirection": "horizontal"},
                "arrowStrikethrough": False,
                "width": 1.2,
            },
            "nodes": {"margin": 10, "widthConstraint": {"maximum": 220}},
            "interaction": common_interaction,
            "layout": {"hierarchical": {"enabled": False}},
            "groups": groups_opt,
        }

    # --- применяем опции ровно ОДИН раз, с fallback для pyvis ---
    try:
        net.set_options(json.dumps(options))
    except AttributeError:
        net.set_options(options)

    net.write_html(str(out_path), notebook=False, open_browser=False)

    if thread_mode in ("border", "cluster"):
        _inject_thread_legend(out_path, colors, thread_mode, show_sequential)

    print(f"Saved: {out_path}")
    print(f"Layout: {'hierarchical (UD)' if hierarchical else 'physics'}, "
          f"Threads: {len(colors)} (режим: {thread_mode}), "
          f"sequential edges: {'on' if show_sequential else 'off'}")

    if open_browser:
        try:
            webbrowser.open(out_path.resolve().as_uri())
        except Exception as e:
            print(f"(не удалось автоматически открыть браузер: {e})")


def _inject_thread_legend(html_path: Path, colors: dict[str, str],
                          thread_mode: str, show_sequential: bool) -> None:
    if not colors:
        return

    mode_hint = {
        "border": "Цвет рамки узла = доминирующий поток",
        "cluster": "Цвет узла/рамки = поток (группировка)",
    }.get(thread_mode, "")

    items = "\n".join(
        f'<div class="thread-item">'
        f'<span class="swatch" style="background:{color}"></span>'
        f'<span class="name">{_escape(tid)}</span>'
        f'</div>'
        for tid, color in sorted(colors.items())
    )

    seq_html = ""
    if show_sequential:
        seq_html = """
<div class="edge-legend">
  <div class="edge-item">
    <svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5"
      stroke="#555" stroke-width="2"/></svg>
    <span>вложенный вызов (реальный)</span>
  </div>
  <div class="edge-item">
    <svg width="40" height="10"><line x1="0" y1="5" x2="40" y2="5"
      stroke="#e6194b" stroke-width="2" stroke-dasharray="6,4"/></svg>
    <span>последовательный (эвристика)</span>
  </div>
</div>
"""

    legend_html = f"""
<style>
#thread-legend {{
  position: fixed; top: 12px; right: 12px; z-index: 9999;
  background: rgba(255,255,255,0.96); border: 1px solid #ccc;
  border-radius: 8px; padding: 10px 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
  font-family: Consolas, monospace; font-size: 12px;
  max-height: 85vh; overflow-y: auto; min-width: 220px;
}}
#thread-legend h3 {{ margin: 0 0 6px 0; font-size: 13px; }}
#thread-legend .hint {{ color: #666; font-size: 11px; margin-bottom: 8px; }}
#thread-legend .thread-item {{
  display: flex; align-items: center; gap: 8px; margin: 3px 0;
}}
#thread-legend .swatch {{
  display: inline-block; width: 14px; height: 14px;
  border-radius: 3px; border: 1px solid #999; flex-shrink: 0;
}}
#thread-legend .name {{ word-break: break-all; }}
#thread-legend .edge-legend {{
  margin-top: 10px; padding-top: 8px; border-top: 1px solid #ddd;
}}
#thread-legend .edge-item {{
  display: flex; align-items: center; gap: 8px; margin: 4px 0;
}}
</style>
<div id="thread-legend">
  <h3>Потоки ({len(colors)})</h3>
  <div class="hint">{_escape(mode_hint)}</div>
  {items}
  {seq_html}
</div>
"""

    text = html_path.read_text(encoding="utf-8")
    if "</body>" in text:
        text = text.replace("</body>", legend_html + "\n</body>", 1)
    else:
        text += legend_html
    html_path.write_text(text, encoding="utf-8")


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# ---------- 4. Демо-данные ----------

DEMO_CALLS: dict[Node, list[Node]] = {
    ("com.app.Main",       "main"):    [("com.app.Bootstrap", "start")],
    ("com.app.Bootstrap",  "start"):   [("com.app.Config",    "load"),
                                        ("com.app.Server",    "run")],
    ("com.app.Config",     "load"):    [("com.app.Files",     "read"),
                                        ("com.app.Json",      "parse")],
    ("com.app.Server",     "run"):     [("com.app.Pool",      "submit"),
                                        ("com.app.Router",    "accept")],
    ("com.app.Router",     "accept"):  [("com.app.Handler",   "handle"),
                                        ("com.app.Router",    "accept")],
    ("com.app.Handler",    "handle"):  [("com.app.Service",   "process"),
                                        ("com.app.Logger",    "info")],
    ("com.app.Service",    "process"): [("com.app.Repo",      "find"),
                                        ("com.app.Cache",     "get"),
                                        ("com.app.Validator", "check")],
    ("com.app.Repo",       "find"):    [("com.app.Db",        "query"),
                                        ("com.app.Cache",     "get")],
    ("com.app.Db",         "query"):   [("com.app.Pool",      "borrow"),
                                        ("com.app.Files",     "read")],
    ("com.app.Cache",      "get"):     [],
    ("com.app.Validator",  "check"):   [],
    ("com.app.Logger",     "info"):    [],
    ("com.app.Pool",       "submit"):  [],
    ("com.app.Pool",       "borrow"):  [],
    ("com.app.Files",      "read"):    [],
    ("com.app.Json",       "parse"):   [],
}


def _emit_walk(node: Node, depth: int, rng: random.Random, max_depth: int) -> list[dict]:
    events = [{"className": node[0], "methodName": node[1], "type": "ENTER"}]
    if depth < max_depth:
        for callee in DEMO_CALLS.get(node, []):
            if rng.random() < 0.15:
                continue
            events.extend(_emit_walk(callee, depth + 1, rng, max_depth))
    events.append({"className": node[0], "methodName": node[1], "type": "EXIT"})
    return events


def _seq(*nodes: Node) -> list[dict]:
    """Последовательность независимых ENTER/EXIT — без вложенности."""
    out: list[dict] = []
    for c, m in nodes:
        out.append({"className": c, "methodName": m, "type": "ENTER"})
        out.append({"className": c, "methodName": m, "type": "EXIT"})
    return out


def generate_demo_events(seed: int = 42) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    events_by_thread: dict[str, list[dict]] = {}

    events_by_thread["thread-main"] = _emit_walk(
        ("com.app.Main", "main"), 0, rng, max_depth=6
    )

    for i in range(1, 4):
        events = _emit_walk(
            ("com.app.Handler", "handle"), 0, rng, max_depth=4 + i
        )
        if i == 3 and events:
            events = events[:-1]
        events_by_thread[f"thread-worker-{i}"] = events

    events_by_thread["thread-seq"] = (
        _seq(("com.app.Service", "process"),
             ("com.app.Cache",   "get"),
             ("com.app.Logger",  "info"),
             ("com.app.Service", "process"),
             ("com.app.Validator", "check"))
    )

    events_by_thread["thread-broken"] = [
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
    ]

    return events_by_thread


# ---------- 5. Точка входа ----------

def load_or_generate() -> dict[str, list[dict]]:
    if INPUT_PATH.exists():
        try:
            with INPUT_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            print(f"Loaded: {INPUT_PATH}")
            return data
        except Exception as e:
            print(f"ERROR: не удалось прочитать {INPUT_PATH}: {e}", file=sys.stderr)
            print(">>> Переключаюсь на демо-режим", file=sys.stderr)
    else:
        print(f"Файл не найден: {INPUT_PATH}")
        print(">>> Демо-режим: генерирую синтетические события")

    demo = generate_demo_events(seed=DEMO_SEED)
    if SAVE_DEMO_JSON is not None:
        with SAVE_DEMO_JSON.open("w", encoding="utf-8") as f:
            json.dump(demo, f, ensure_ascii=False, indent=2)
        print(f"Demo JSON saved: {SAVE_DEMO_JSON}")
    return demo


def main() -> None:
    events_by_thread = load_or_generate()
    graph, seq_graph, node_threads, thread_calls = build_call_graph(events_by_thread)

    total_nodes = len(graph)
    total_edges = sum(len(v) for v in graph.values())
    total_seq   = sum(len(v) for v in seq_graph.values())
    print(f"\nThreads: {len(events_by_thread)}, "
          f"Nodes: {total_nodes}, "
          f"Nested edges: {total_edges}, "
          f"Sequential edges: {total_seq}")

    visualize_pyvis(
        graph, seq_graph, node_threads, thread_calls,
        out_path=OUTPUT_HTML,
        show_full_class=SHOW_FULL_CLASS,
        open_browser=OPEN_BROWSER,
        hierarchical=HIERARCHICAL,
        thread_mode=THREAD_MODE,
        show_sequential=SHOW_SEQUENTIAL,
    )


if __name__ == "__main__":
    main()