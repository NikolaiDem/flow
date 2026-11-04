# build_graph.py
from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

from flow_graph.config import (
    ALLOW_DEMO_FALLBACK,
    DEMO_SEED,
    SAVE_DEMO_JSON,
    SHOW_FULL_CLASS,
    SHOW_SEQUENTIAL,
    THREAD_PALETTE,
    Node,
    get_html_out_dir,
    get_stacks_dir,
    load_config,
    resolve_config_path,
    validate_config,
)
from flow_graph.demo import generate_demo_events
from flow_graph.render_html import render_by_thread_html

log = logging.getLogger(__name__)


# ============================================================
# 1. ГРАФ (чистая логика)
# ============================================================

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
        log.warning(w)

    return dict(graph), dict(sequential_graph), dict(node_threads), dict(thread_calls)


def build_per_thread_data(
    events_by_thread: dict[str, list[dict]],
    *,
    show_full_class: bool,
    show_sequential: bool,
) -> list[dict]:
    """Payload для vis-network: по одному элементу на поток."""

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def make_node(n: Node, in_deg: int, out_deg: int,
                  thread_id: str, thread_color: str) -> dict:
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

    def eid(n: Node) -> str:
        return f"{n[0]}#{n[1]}"

    result: list[dict] = []

    for t_idx, (thread_id, events) in enumerate(events_by_thread.items()):
        thread_color = THREAD_PALETTE[t_idx % len(THREAD_PALETTE)]

        nested: dict[Node, set[Node]] = defaultdict(set)
        sequential: dict[Node, set[Node]] = defaultdict(set)
        nodes_seen: set[Node] = set()
        stack: list[Node] = []
        last_root: Node | None = None

        for ev in events:
            n: Node = (ev["className"], ev["methodName"])
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

        in_deg: dict[Node, int] = defaultdict(int)
        out_deg: dict[Node, int] = defaultdict(int)
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


# ============================================================
# 2. ЗАГРУЗКА ДАННЫХ
# ============================================================

def load_one_stack(json_path: Path) -> dict[str, list[dict]] | None:
    """
    Читает один JSON. Форматы:
      a) {thread_id: [events...]}
      b) [events...]  → ключ = имя файла (stem)
    Возвращает None, если битый/пустой/не того формата.
    """
    try:
        with json_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        log.warning("битый JSON %s: %s", json_path.name, e)
        return None
    except OSError as e:
        log.warning("не удалось прочитать %s: %s", json_path.name, e)
        return None

    if isinstance(data, dict):
        if not data:
            log.warning("пустой словарь в %s", json_path.name)
            return None
        return data

    if isinstance(data, list):
        if not data:
            log.warning("пустой список в %s", json_path.name)
            return None
        return {json_path.stem: data}

    log.warning("неожиданный формат в %s: %s", json_path.name, type(data).__name__)
    return None


def _demo() -> dict[str, list[dict]]:
    demo = generate_demo_events(seed=DEMO_SEED)
    if SAVE_DEMO_JSON is not None:
        SAVE_DEMO_JSON.parent.mkdir(parents=True, exist_ok=True)
        with SAVE_DEMO_JSON.open("w", encoding="utf-8") as f:
            json.dump(demo, f, ensure_ascii=False, indent=2)
        log.info("Demo JSON saved: %s", SAVE_DEMO_JSON)
    return demo


def _demo_or_fail(reason: str) -> dict[str, list[dict]] | None:
    if not ALLOW_DEMO_FALLBACK:
        log.error("реальные данные недоступны (%s); демо запрещён", reason)
        return None
    log.info("Демо-режим: %s", reason)
    return _demo()


# ============================================================
# 3. РЕНДЕР ОДНОГО HTML
# ============================================================

def _render_one(events_by_thread: dict[str, list[dict]],
                out_path: Path, *, title: str) -> None:
    graph, seq_graph, _nt, _tc = build_call_graph(events_by_thread)
    log.info(
        "[%s] threads=%d nodes=%d nested=%d sequential=%d",
        title, len(events_by_thread), len(graph),
        sum(len(v) for v in graph.values()),
        sum(len(v) for v in seq_graph.values()),
    )

    per_thread = build_per_thread_data(
        events_by_thread,
        show_full_class=SHOW_FULL_CLASS,
        show_sequential=SHOW_SEQUENTIAL,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    render_by_thread_html(
        per_thread,
        out_path=out_path,
        show_sequential=SHOW_SEQUENTIAL,
        level_separation=180,
        node_spacing=280,
        tree_spacing=320,
    )
    log.info("Saved: %s", out_path)


# ============================================================
# 4. ГЛАВНАЯ ФУНКЦИЯ (единственная точка входа наружу)
# ============================================================

def generate_flow_htmls(*, config_path: Path | None = None) -> Path | None:
    """
    Читает конфиг, данные, генерирует HTML в <flow.stack-output>/html.
    Возвращает путь к директории или None, если не удалось.

    Вызывается:
      - лениво из AppContext при первом /flow-list;
      - пакетно через `python build_graph.py`.
    """
    # --- конфиг ---
    try:
        path = config_path or resolve_config_path()
        cfg = load_config(path)
        validate_config(cfg)
    except Exception as e:
        log.warning("не удалось прочитать конфиг: %s", e)
        cfg = None
        path = None

    stacks_dir = get_stacks_dir(cfg, path) if cfg and path else None
    html_dir = get_html_out_dir(cfg, path) if cfg and path else Path("html").resolve()

    try:
        html_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error("не удалось создать %s: %s", html_dir, e)
        return None

    log.info("[html] dir: %s", html_dir)
    if stacks_dir is not None:
        log.info("[stacks] dir: %s", stacks_dir)

    # --- демо: конфига нет ---
    if stacks_dir is None:
        events = _demo_or_fail("config.yaml не найден")
        if events is None:
            return None
        try:
            _render_one(events, html_dir / "demo.html", title="demo")
        except Exception:
            log.exception("не удалось отрендерить demo")
            return None
        return html_dir

    # --- демо: директории стеков нет ---
    if not stacks_dir.is_dir():
        events = _demo_or_fail(f"{stacks_dir} не существует")
        if events is None:
            return None
        try:
            _render_one(events, html_dir / "demo.html", title="demo")
        except Exception:
            log.exception("не удалось отрендерить demo")
            return None
        return html_dir

    # --- реальные данные: один HTML на каждый JSON ---
    files = sorted(stacks_dir.glob("*.json"))
    if not files:
        events = _demo_or_fail(f"в {stacks_dir} нет *.json")
        if events is None:
            return None
        try:
            _render_one(events, html_dir / "demo.html", title="demo")
        except Exception:
            log.exception("не удалось отрендерить demo")
            return None
        return html_dir

    log.info("[stacks] %d file(s)", len(files))

    rendered = 0
    skipped = 0
    for json_path in files:
        events = load_one_stack(json_path)
        if not events:
            skipped += 1
            continue
        out_path = html_dir / f"{json_path.stem}.html"
        try:
            _render_one(events, out_path, title=json_path.stem)
            rendered += 1
        except Exception:
            log.exception("не удалось отрендерить %s", json_path.name)
            skipped += 1

    log.info("Done: rendered=%d skipped=%d out_dir=%s",
             rendered, skipped, html_dir)

    if rendered == 0:
        events = _demo_or_fail("ни один JSON не дал данных")
        if events is None:
            return None
        try:
            _render_one(events, html_dir / "demo.html", title="demo")
        except Exception:
            log.exception("не удалось отрендерить demo")
            return None

    return html_dir


# ============================================================
# 5. ПАКЕТНЫЙ РЕЖИМ
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    d = generate_flow_htmls()
    if d is None:
        print("ERROR: flow-HTML не сгенерированы", file=sys.stderr)
        sys.exit(1)
    print(f"Flow HTML: {d}")