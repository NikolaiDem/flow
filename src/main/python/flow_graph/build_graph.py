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
HIERARCHICAL     = False

# Как показывать потоки:
#   "border"   — цвет рамки узла по доминирующему потоку (по умолчанию)
#   "cluster"  — узлы группируются в рамки-кластеры по потокам
#   "none"     — не подсвечивать
THREAD_MODE      = "border"

Node = tuple[str, str]  # (className, methodName)


# ---------- 1. Построение графа + сбор статистики по потокам ----------

def build_call_graph(events_by_thread: dict[str, list[dict]]):
    """
    Возвращает:
      graph     : caller -> set(callee)
      node_threads : node -> Counter(thread_id -> сколько раз встретился)
      thread_calls : thread_id -> set(node), какие методы вызывались в потоке
    """
    graph: dict[Node, set[Node]] = defaultdict(set)
    node_threads: dict[Node, Counter] = defaultdict(Counter)
    thread_calls: dict[str, set[Node]] = defaultdict(set)
    all_nodes: set[Node] = set()
    warnings: list[str] = []

    for thread_id, events in events_by_thread.items():
        stack: list[Node] = []

        for i, ev in enumerate(events):
            node: Node = (ev["className"], ev["methodName"])
            ntype = ev["type"].upper()
            all_nodes.add(node)

            if ntype == "ENTER":
                node_threads[node][thread_id] += 1
                thread_calls[thread_id].add(node)
                if stack:
                    graph[stack[-1]].add(node)
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

    for w in warnings:
        print("WARN:", w, file=sys.stderr)

    return dict(graph), dict(node_threads), dict(thread_calls)


# ---------- 2. Палитра для потоков ----------

THREAD_PALETTE = [
    "#e6194b",  # red
    "#3cb44b",  # green
    "#4363d8",  # blue
    "#f58231",  # orange
    "#911eb4",  # purple
    "#42d4f4",  # cyan
    "#f032e6",  # magenta
    "#bfef45",  # lime
    "#fabed4",  # pink
    "#469990",  # teal
    "#dcbeff",  # lavender
    "#9a6324",  # brown
    "#fffac8",  # beige
    "#800000",  # maroon
    "#aaffc3",  # mint
    "#808000",  # olive
    "#ffd8b1",  # apricot
    "#000075",  # navy
]


def thread_color_map(thread_ids: list[str]) -> dict[str, str]:
    return {tid: THREAD_PALETTE[i % len(THREAD_PALETTE)]
            for i, tid in enumerate(sorted(thread_ids))}


# ---------- 3. Визуализация через pyvis ----------

def visualize_pyvis(
    graph: dict[Node, set[Node]],
    node_threads: dict[Node, Counter],
    thread_calls: dict[str, set[Node]],
    out_path: Path,
    show_full_class: bool = False,
    open_browser: bool = True,
    hierarchical: bool = False,
    thread_mode: str = "border",
) -> None:
    from pyvis.network import Network

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def node_id(n: Node) -> str:
        return f"{n[0]}#{n[1]}"

    def node_label(n: Node) -> str:
        return f"{short_class(n[0])}\n{n[1]}"

    # Тултип: полное имя + список потоков, где встречается метод
    def node_title(n: Node) -> str:
        lines = [f"{n[0]}.{n[1]}"]
        counter = node_threads.get(n, Counter())
        if counter:
            total = sum(counter.values())
            lines.append(f"Вызовов: {total}")
            lines.append("Потоки:")
            # сортируем по количеству вхождений
            for tid, cnt in counter.most_common():
                lines.append(f"  • {tid}: {cnt}")
        return "\n".join(lines)

    # Цвет узла — по степени связности (хабы/листья)
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

    # Цвет рамки — по доминирующему потоку
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

    # --- создаём сеть ---
    net = Network(
        height="900px",
        width="100%",
        directed=True,
        notebook=False,
        bgcolor="#ffffff",
        font_color="#222222",
    )

    all_nodes = set(graph.keys())
    for callees in graph.values():
        all_nodes |= callees

    # кластеры по потокам (если выбран режим cluster)
    # один узел может попасть в несколько кластеров — pyvis поддерживает
    # это только для «однопринадлежащих» узлов, поэтому в cluster-режиме
    # размещаем метод в поток, где он встречается чаще всего
    node_to_cluster: dict[Node, str] = {}
    if thread_mode == "cluster":
        # Для каждого потока создаём кластер из методов, для которых он доминирует
        for n in all_nodes:
            tid = dominant_thread(n)
            if tid is not None:
                node_to_cluster[n] = tid

        # Готовим контейнеры кластеров — pyvis требует добавлять в кластер
        # после создания узлов, но проще: сначала создать все узлы,
        # а затем перегруппировать. pyvis API: net.add_node(..., group=tid)
        # group натягивает «внутреннюю» группировку vis.js, но не рисует
        # рамку с подписью. Поэтому используем net.add_node(..., group=tid)
        # + легенду, объясняющую цвета.

    for n in all_nodes:
        kwargs = dict(
            label=node_label(n),
            title=node_title(n),
            shape="box",
            color={
                "background": node_fill(n),
                "border": node_border(n),
            },
            borderWidth=node_border_width(n),
            font={"size": 14, "face": "Consolas, monospace"},
        )
        if thread_mode == "cluster" and n in node_to_cluster:
            kwargs["group"] = node_to_cluster[n]
        net.add_node(node_id(n), **kwargs)

    # Рёбра
    for caller, callees in graph.items():
        for callee in callees:
            is_self = caller == callee
            net.add_edge(
                node_id(caller),
                node_id(callee),
                arrows="to",
                color="#888888",
                title=f"{caller[0]}.{caller[1]} -> {callee[0]}.{callee[1]}",
                selfReferenceSize=20 if is_self else 0,
                dashes=is_self,
            )

    # --- опции vis.js ---
    options = {
        "physics": {
            "enabled": not hierarchical,
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
            "smooth": {"type": "cubicBezier", "forceDirection": "horizontal"},
            "arrowStrikethrough": False,
            "width": 1.2,
        },
        "nodes": {
            "margin": 10,
            "widthConstraint": {"maximum": 220},
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 120,
            "navigationButtons": True,
            "keyboard": {"enabled": True},
            "multiselect": True,
        },
        "layout": {
            "hierarchical": {
                "enabled": hierarchical,
                "direction": "LR",
                "sortMethod": "directed",
                "levelSeparation": 220,
                "nodeSpacing": 140,
            }
        },
        # визуальные группы, если используется cluster-режим
        "groups": {
            tid: {"color": {"border": colors[tid], "background": "#ffffff"}}
            for tid in colors
        } if thread_mode == "cluster" else {},
    }
    net.set_options(json.dumps(options))

    net.write_html(str(out_path), notebook=False, open_browser=False)

    # --- легенда потоков ---
    # pyvis не умеет добавлять произвольный HTML, поэтому «допишем» легенду
    # прямо в готовый файл после генерации
    if thread_mode in ("border", "cluster"):
        _inject_thread_legend(out_path, colors, thread_mode)

    print(f"Saved: {out_path}")
    print(f"Threads shown: {len(colors)} "
          f"(режим: {thread_mode})")

    if open_browser:
        try:
            webbrowser.open(out_path.resolve().as_uri())
        except Exception as e:
            print(f"(не удалось автоматически открыть браузер: {e})")


def _inject_thread_legend(
    html_path: Path,
    colors: dict[str, str],
    thread_mode: str,
) -> None:
    """
    Вставляет плавающую панель-легенду с потоками в готовый HTML pyvis.
    Панель позиционируется в правом верхнем углу.
    """
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

    legend_html = f"""
<style>
#thread-legend {{
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 9999;
  background: rgba(255,255,255,0.96);
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
  font-family: Consolas, monospace;
  font-size: 12px;
  max-height: 80vh;
  overflow-y: auto;
  min-width: 200px;
}}
#thread-legend h3 {{
  margin: 0 0 6px 0;
  font-size: 13px;
  font-weight: 600;
}}
#thread-legend .hint {{
  color: #666;
  font-size: 11px;
  margin-bottom: 8px;
}}
#thread-legend .thread-item {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 3px 0;
}}
#thread-legend .swatch {{
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid #999;
  flex-shrink: 0;
}}
#thread-legend .name {{
  word-break: break-all;
}}
</style>
<div id="thread-legend">
  <h3>Потоки ({len(colors)})</h3>
  <div class="hint">{_escape(mode_hint)}</div>
  {items}
</div>
"""

    text = html_path.read_text(encoding="utf-8")
    # вставляем перед </body>, чтобы оказалось поверх canvas
    if "</body>" in text:
        text = text.replace("</body>", legend_html + "\n</body>", 1)
    else:
        text += legend_html
    html_path.write_text(text, encoding="utf-8")


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


# ---------- 4. Демо-данные (те же, но с несколькими потоками) ----------

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


def generate_demo_events(seed: int = 42) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    events_by_thread: dict[str, list[dict]] = {}

    # Основной поток
    events_by_thread["thread-main"] = _emit_walk(
        ("com.app.Main", "main"), 0, rng, max_depth=6
    )

    # 3 воркера-обработчика — каждый прогоняет свой Handler.handle
    # (с разной глубиной, чтобы потоки «пересекались» на общих методах)
    for i in range(1, 4):
        events = _emit_walk(
            ("com.app.Handler", "handle"), 0, rng, max_depth=4 + i
        )
        if i == 3 and events:
            events = events[:-1]   # оборванный поток -> WARN
        events_by_thread[f"thread-worker-{i}"] = events

    # Поток, который ходит только в кэш/логгер — «специализированный»
    events_by_thread["thread-cache-warmer"] = [
        {"className": "com.app.Cache", "methodName": "get",   "type": "ENTER"},
        {"className": "com.app.Cache", "methodName": "get",   "type": "EXIT"},
        {"className": "com.app.Cache", "methodName": "get",   "type": "ENTER"},
        {"className": "com.app.Cache", "methodName": "get",   "type": "EXIT"},
        {"className": "com.app.Logger","methodName": "info",  "type": "ENTER"},
        {"className": "com.app.Logger","methodName": "info",  "type": "EXIT"},
    ]

    # Битый поток — только EXIT-ы
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
            print(f"ERROR: не удалось прочитать {INPUT_PATH}: {e}",
                  file=sys.stderr)
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
    graph, node_threads, thread_calls = build_call_graph(events_by_thread)

    total_nodes = len(graph)
    total_edges = sum(len(v) for v in graph.values())
    print(f"\nThreads: {len(events_by_thread)}, "
          f"Nodes: {total_nodes}, Edges: {total_edges}")

    # Кто в скольких потоках встречается (топ-5 «общих» методов)
    shared = sorted(
        node_threads.items(),
        key=lambda kv: (-len(kv[1]), -sum(kv[1].values())),
    )[:5]
    print("Методы, встречающиеся в наибольшем числе потоков:")
    for (cls, meth), counter in shared:
        if len(counter) > 1:
            print(f"  {cls.rsplit('.', 1)[-1]}.{meth} "
                  f"-> {len(counter)} потоков: "
                  f"{', '.join(counter.keys())}")

    visualize_pyvis(
        graph,
        node_threads,
        thread_calls,
        out_path=OUTPUT_HTML,
        show_full_class=SHOW_FULL_CLASS,
        open_browser=OPEN_BROWSER,
        hierarchical=HIERARCHICAL,
        thread_mode=THREAD_MODE,
    )


if __name__ == "__main__":
    main()