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
PER_THREAD = True

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

def build_per_thread_data(
    events_by_thread: dict[str, list[dict]],
    *,
    show_full_class: bool,
    show_sequential: bool,
) -> list[dict]:
    """
    Возвращает список payload'ов — по одному на поток, в формате,
    который ожидает render_by_thread_html().
    """
    from collections import Counter, defaultdict

    THREAD_PALETTE = [
        "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
        "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9a6324",
    ]

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def make_node(n, in_deg, out_deg, thread_id, thread_color):
        # заливка по степени, как раньше
        weight = in_deg + out_deg
        if weight >= 6:
            fill = "#5b8def"
        elif weight >= 3:
            fill = "#8fb3f5"
        elif in_deg and not out_deg:
            fill = "#a8d5a8"
        else:
            fill = "#e8f0fe"
        return {
            "id": f"{n[0]}#{n[1]}",
            "label": f"{short_class(n[0])}\n{n[1]}",
            "title": f"{n[0]}.{n[1]}\nпоток: {thread_id}",
            "shape": "box",
            "color": {"background": fill, "border": thread_color},
            "borderWidth": 3,
            "font": {"size": 13, "face": "Consolas, monospace"},
        }

    result: list[dict] = []

    for t_idx, (thread_id, events) in enumerate(events_by_thread.items()):
        thread_color = THREAD_PALETTE[t_idx % len(THREAD_PALETTE)]

        # прогоняем стек только для этого потока
        nested = defaultdict(set)
        sequential = defaultdict(set)
        nodes_seen: set[Node] = set()
        stack: list[Node] = []
        last_root: Node | None = None

        for ev in events:
            n = (ev["className"], ev["methodName"])
            ntype = ev["type"].upper()
            nodes_seen.add(n)

            if ntype == "ENTER":
                if stack:
                    nested[stack[-1]].add(n)
                else:
                    if last_root is not None and last_root != n:
                        sequential[last_root].add(n)
                    last_root = n
                stack.append(n)
            elif ntype == "EXIT":
                if stack and stack[-1] == n:
                    stack.pop()
                elif n in stack:
                    while stack and stack[-1] != n:
                        stack.pop()
                    if stack:
                        stack.pop()

        # степени для цветовой заливки
        in_deg = defaultdict(int)
        out_deg = defaultdict(int)
        for caller, callees in nested.items():
            out_deg[caller] += len(callees)
            for c in callees:
                in_deg[c] += 1
        for n in nodes_seen:
            in_deg[n] += 0
            out_deg[n] += 0

        nodes_payload = [
            make_node(n, in_deg[n], out_deg[n], thread_id, thread_color)
            for n in sorted(nodes_seen)
        ]

        def eid(n):
            return f"{n[0]}#{n[1]}"

        edges_payload: list[dict] = []
        for caller, callees in nested.items():
            for callee in callees:
                edges_payload.append({
                    "from": eid(caller),
                    "to": eid(callee),
                    "arrows": "to",
                    "color": {"color": "#555555", "highlight": "#000000"},
                    "width": 1.5,
                    "title": f"[вложенный] {caller[0]}.{caller[1]} "
                             f"-> {callee[0]}.{callee[1]}",
                    "kind": "nested",
                })

        if show_sequential:
            for caller, callees in sequential.items():
                for callee in callees:
                    if callee in nested.get(caller, set()):
                        continue
                    edges_payload.append({
                        "from": eid(caller),
                        "to": eid(callee),
                        "arrows": "to",
                        "color": {"color": "#e6194b", "highlight": "#a00030"},
                        "width": 1.2,
                        "dashes": [6, 4],
                        "title": f"[последовательный] {caller[0]}.{caller[1]} "
                                 f"-> {callee[0]}.{callee[1]}",
                        "kind": "sequential",
                    })

        result.append({
            "thread_id": thread_id,
            "nodes": nodes_payload,
            "edges": edges_payload,
        })

    return result

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

    # общая сводка (для консоли) — считаем по объединённому графу
    graph, seq_graph, node_threads, thread_calls = build_call_graph(events_by_thread)
    print(f"\nThreads: {len(events_by_thread)}, "
          f"Nodes: {len(graph)}, "
          f"Nested edges: {sum(len(v) for v in graph.values())}, "
          f"Sequential edges: {sum(len(v) for v in seq_graph.values())}")

    # payload на каждый поток
    per_thread = build_per_thread_data(
        events_by_thread,
        show_full_class=SHOW_FULL_CLASS,
        show_sequential=SHOW_SEQUENTIAL,
    )

    from render_html import render_by_thread_html

    render_by_thread_html(
        per_thread,
        out_path=OUTPUT_HTML,
        show_sequential=SHOW_SEQUENTIAL,
        level_separation=180,
        node_spacing=280,   # увеличено, чтобы не накладывались
        tree_spacing=320,
    )

    print(f"Saved: {OUTPUT_HTML}")

    if OPEN_BROWSER:
        try:
            webbrowser.open(OUTPUT_HTML.resolve().as_uri())
        except Exception as e:
            print(f"(не удалось открыть браузер: {e})")


if __name__ == "__main__":
    main()