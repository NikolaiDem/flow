import json
import sys
import random
from collections import defaultdict
from pathlib import Path

# ---------- 1. Построение графа ----------

Node = tuple[str, str]  # (className, methodName)

def build_call_graph(events_by_thread: dict[str, list[dict]]) -> dict[Node, set[Node]]:
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


# ---------- 2. Визуализация graphviz ----------

def visualize_graphviz(graph: dict[Node, set[Node]], out_path: str = "call_graph"):
    from graphviz import Digraph

    dot = Digraph("calls", format="png")
    dot.attr(rankdir="LR", nodesep="0.35", ranksep="0.6", fontname="Helvetica")
    dot.attr("node", shape="box", style="rounded,filled",
             fillcolor="#e8f0fe", fontname="Helvetica", fontsize="10")
    dot.attr("edge", fontname="Helvetica", fontsize="9", color="#555555")

    def nid(n: Node) -> str:
        return f"{n[0]}#{n[1]}"

    def label(n: Node) -> str:
        return f"{n[0].rsplit('.', 1)[-1]}\n{n[1]}"

    seen: set[Node] = set()
    for caller, callees in graph.items():
        if caller not in seen:
            dot.node(nid(caller), label(caller))
            seen.add(caller)
        for callee in callees:
            if callee not in seen:
                dot.node(nid(callee), label(callee))
                seen.add(callee)
            dot.edge(nid(caller), nid(callee))

    dot.render(out_path, cleanup=True)
    print(f"Saved: {out_path}.png")


# ---------- 3. Визуализация networkx ----------

def visualize_networkx(graph: dict[Node, set[Node]],
                       out_path: str = "call_graph_nx.png"):
    import networkx as nx
    import matplotlib.pyplot as plt

    G = nx.DiGraph()
    for caller, callees in graph.items():
        G.add_node(f"{caller[0].rsplit('.',1)[-1]}.{caller[1]}")
        for callee in callees:
            G.add_edge(
                f"{caller[0].rsplit('.',1)[-1]}.{caller[1]}",
                f"{callee[0].rsplit('.',1)[-1]}.{callee[1]}",
            )

    n = max(len(G.nodes), 1)
    size = max(10, min(30, 0.8 * n))
    plt.figure(figsize=(size, size * 0.75))

    try:
        pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    except Exception:
        pos = nx.spring_layout(G, k=1.0, seed=42)

    nx.draw_networkx_nodes(G, pos, node_color="#aac8ff",
                           node_size=2200, node_shape="s")
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=15,
                           alpha=0.75, edge_color="#444444")
    nx.draw_networkx_labels(G, pos, font_size=8)

    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")


# ---------- 4. Генератор тестовых данных ----------

# Небольшое "приложение": какие методы что вызывают (реалистичный граф)
DEMO_CALLS: dict[Node, list[Node]] = {
    ("com.app.Main",             "main"):      [("com.app.Bootstrap", "start")],
    ("com.app.Bootstrap",        "start"):     [("com.app.Config",    "load"),
                                                ("com.app.Server",    "run")],
    ("com.app.Config",           "load"):      [("com.app.Files",     "read"),
                                                ("com.app.Json",      "parse")],
    ("com.app.Server",           "run"):       [("com.app.Pool",      "submit"),
                                                ("com.app.Router",    "accept")],
    ("com.app.Router",           "accept"):    [("com.app.Handler",   "handle"),
                                                ("com.app.Router",    "accept")],  # рекурсия!
    ("com.app.Handler",          "handle"):    [("com.app.Service",   "process"),
                                                ("com.app.Logger",    "info")],
    ("com.app.Service",          "process"):   [("com.app.Repo",      "find"),
                                                ("com.app.Cache",     "get"),
                                                ("com.app.Validator", "check")],
    ("com.app.Repo",             "find"):      [("com.app.Db",        "query"),
                                                ("com.app.Cache",     "get")],
    ("com.app.Db",               "query"):     [("com.app.Pool",      "borrow"),
                                                ("com.app.Files",     "read")],
    ("com.app.Cache",            "get"):       [],
    ("com.app.Validator",        "check"):     [],
    ("com.app.Logger",           "info"):      [],
    ("com.app.Pool",             "submit"):    [],
    ("com.app.Pool",             "borrow"):    [],
    ("com.app.Files",            "read"):      [],
    ("com.app.Json",             "parse"):     [],
}


def _emit_walk(node: Node, depth: int, rng: random.Random,
               max_depth: int) -> list[dict]:
    """Сгенерировать ENTER/EXIT с вложенными вызовами начиная с node."""
    events = [
        {"className": node[0], "methodName": node[1], "type": "ENTER"}
    ]
    if depth < max_depth:
        for callee in DEMO_CALLS.get(node, []):
            # немного случайности: иногда пропускаем вызов, иногда углубляемся
            if rng.random() < 0.15:
                continue
            events.extend(_emit_walk(callee, depth + 1, rng, max_depth))
    events.append(
        {"className": node[0], "methodName": node[1], "type": "EXIT"}
    )
    return events


def generate_demo_events(seed: int = 42) -> dict[str, list[dict]]:
    """Сгенерировать eventsByThread для демо-режима."""
    rng = random.Random(seed)
    events_by_thread: dict[str, list[dict]] = {}

    # Основной поток — полный прогон от Main.main
    events_by_thread["thread-main"] = _emit_walk(
        ("com.app.Main", "main"), 0, rng, max_depth=6
    )

    # Обработчики — по одной обработке на поток
    for i in range(1, 4):
        thread_id = f"thread-worker-{i}"
        # обрезаем "хвост", чтобы поток иногда не завершался (для WARN)
        events = _emit_walk(
            ("com.app.Handler", "handle"), 0, rng, max_depth=5
        )
        if i == 3 and events:
            events = events[:-1]  # убираем последний EXIT -> WARN
        events_by_thread[thread_id] = events

    # Немного "битых" данных: EXIT без ENTER
    events_by_thread["thread-broken"] = [
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
        {"className": "com.app.Mystery", "methodName": "ghost", "type": "EXIT"},
    ]

    return events_by_thread


# ---------- 5. CLI ----------

def main():
    import argparse

    p = argparse.ArgumentParser(description="Build call graph from Java flow events")
    p.add_argument("input", nargs="?",
                   help="Путь к JSON с eventsByThread. "
                        "Если не указан — используется демо-режим.")
    p.add_argument("-o", "--output", default="call_graph",
                   help="Базовое имя выходного файла (без расширения)")
    p.add_argument("--engine", choices=["graphviz", "networkx", "both"],
                   default="both")
    p.add_argument("--seed", type=int, default=42,
                   help="Seed для демо-генератора")
    p.add_argument("--save-demo-json",
                   help="Сохранить сгенерированный демо-JSON по этому пути")
    args = p.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            events_by_thread = json.load(f)
        print(f"Loaded: {args.input}")
    else:
        print(">>> Демо-режим: генерирую синтетические события")
        events_by_thread = generate_demo_events(seed=args.seed)
        if args.save_demo_json:
            with open(args.save_demo_json, "w", encoding="utf-8") as f:
                json.dump(events_by_thread, f, ensure_ascii=False, indent=2)
            print(f"Demo JSON saved: {args.save_demo_json}")

    graph = build_call_graph(events_by_thread)

    total_nodes = len(graph)
    total_edges = sum(len(v) for v in graph.values())
    print(f"Threads: {len(events_by_thread)}, "
          f"Nodes: {total_nodes}, Edges: {total_edges}")

    # немного статистики
    top_callers = sorted(graph.items(), key=lambda kv: -len(kv[1]))[:5]
    print("\nTop callers:")
    for (cls, meth), callees in top_callers:
        if callees:
            print(f"  {cls.rsplit('.',1)[-1]}.{meth} -> {len(callees)}")

   # if args.engine in ("graphviz", "both"):
   #     visualize_graphviz(graph, f"{args.output}_gv")
   # if args.engine in ("networkx", "both"):
    visualize_networkx(graph, f"{args.output}_nx.png")


if __name__ == "__main__":
    main()