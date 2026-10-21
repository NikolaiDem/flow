import json
import sys
import random
import webbrowser
from pathlib import Path
from collections import defaultdict

# ---------- Настройки (меняйте здесь, CLI убран) ----------

INPUT_PATH       = Path("D:/work/stacks/current.json")   # входной JSON
OUTPUT_HTML      = Path("call_graph.html")               # куда сохранить
DEMO_SEED        = 42                                    # seed демо-генератора
SAVE_DEMO_JSON   = None                                  # напр. Path("demo_events.json")
SHOW_FULL_CLASS  = False                                 # полное имя класса?
OPEN_BROWSER     = True                                  # открыть после генерации
HIERARCHICAL     = False                                 # иерархическая раскладка?

Node = tuple[str, str]  # (className, methodName)


# ---------- 1. Построение графа ----------

def build_call_graph(events_by_thread: dict[str, list[dict]]) -> dict[Node, set[Node]]:
    """
    Проходим по каждому потоку как по стеку вызовов.
    ENTER -> push (и ребро от вершины стека к новому узлу)
    EXIT  -> pop (с защитой от непарных/битых событий)
    """
    graph: dict[Node, set[Node]] = defaultdict(set)
    all_nodes: set[Node] = set()
    warnings: list[str] = []

    for thread_id, events in events_by_thread.items():
        stack: list[Node] = []

        for i, ev in enumerate(events):
            node: Node = (ev["className"], ev["methodName"])
            ntype = ev["type"].upper()
            all_nodes.add(node)

            if ntype == "ENTER":
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

    return dict(graph)


# ---------- 2. Интерактивная визуализация через pyvis ----------

def visualize_pyvis(
    graph: dict[Node, set[Node]],
    out_path: Path,
    show_full_class: bool = False,
    open_browser: bool = True,
    hierarchical: bool = False,
) -> None:
    from pyvis.network import Network

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def node_id(n: Node) -> str:
        return f"{n[0]}#{n[1]}"

    def node_label(n: Node) -> str:
        return f"{short_class(n[0])}\n{n[1]}"

    def node_title(n: Node) -> str:
        return f"{n[0]}.{n[1]}"

    # Степени для цветовой подсветки
    indeg: dict[Node, int] = defaultdict(int)
    outdeg: dict[Node, int] = defaultdict(int)
    for caller, callees in graph.items():
        outdeg[caller] += len(callees)
        for c in callees:
            indeg[c] += 1

    def node_color(n: Node) -> str:
        weight = indeg[n] + outdeg[n]
        if weight >= 6:
            return "#5b8def"
        if weight >= 3:
            return "#8fb3f5"
        if indeg[n] and not outdeg[n]:
            return "#a8d5a8"
        return "#e8f0fe"

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

    for n in all_nodes:
        net.add_node(
            node_id(n),
            label=node_label(n),
            title=node_title(n),
            shape="box",
            color=node_color(n),
            borderWidth=1,
            font={"size": 14, "face": "Consolas, monospace"},
        )

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
            "stabilization": {
                "enabled": True,
                "iterations": 500,
                "updateInterval": 25,
            },
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
    }
    net.set_options(json.dumps(options))

    net.write_html(str(out_path), notebook=False, open_browser=False)
    print(f"Saved: {out_path}")
    print("Откройте этот файл в браузере — граф интерактивный "
          "(перетаскивание, зум, тултипы).")

    if open_browser:
        try:
            webbrowser.open(out_path.resolve().as_uri())
        except Exception as e:
            print(f"(не удалось автоматически открыть браузер: {e})")


# ---------- 3. Генератор тестовых данных ----------

DEMO_CALLS: dict[Node, list[Node]] = {
    ("com.app.Main",       "main"):    [("com.app.Bootstrap", "start")],
    ("com.app.Bootstrap",  "start"):   [("com.app.Config",    "load"),
                                        ("com.app.Server",    "run")],
    ("com.app.Config",     "load"):    [("com.app.Files",     "read"),
                                        ("com.app.Json",      "parse")],
    ("com.app.Server",     "run"):     [("com.app.Pool",      "submit"),
                                        ("com.app.Router",    "accept")],
    ("com.app.Router",     "accept"):  [("com.app.Handler",   "handle"),
                                        ("com.app.Router",    "accept")],  # рекурсия
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

    events_by_thread["thread-main"] = _emit_walk(
        ("com.app.Main", "main"), 0, rng, max_depth=6
    )

    for i in range(1, 4):
        events = _emit_walk(
            ("com.app.Handler", "handle"), 0, rng, max_depth=5
        )
        if i == 3 and events:
            events = events[:-1]
        events_by_thread[f"thread-worker-{i}"] = events

    events_by_thread["thread-broken"] = [
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
    ]

    return events_by_thread


# ---------- 4. Точка входа ----------

def load_or_generate() -> dict[str, list[dict]]:
    """
    Пытаемся прочитать INPUT_PATH. Если файла нет — демо-режим.
    """
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
    graph = build_call_graph(events_by_thread)

    total_nodes = len(graph)
    total_edges = sum(len(v) for v in graph.values())
    print(f"\nThreads: {len(events_by_thread)}, "
          f"Nodes: {total_nodes}, Edges: {total_edges}")

    top_callers = sorted(graph.items(), key=lambda kv: -len(kv[1]))[:5]
    print("Top callers:")
    for (cls, meth), callees in top_callers:
        if callees:
            print(f"  {cls.rsplit('.', 1)[-1]}.{meth} -> {len(callees)}")

    visualize_pyvis(
        graph,
        out_path=OUTPUT_HTML,
        show_full_class=SHOW_FULL_CLASS,
        open_browser=OPEN_BROWSER,
        hierarchical=HIERARCHICAL,
    )


if __name__ == "__main__":
    main()