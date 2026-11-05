# build_graph.py
from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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
# 0. МОДЕЛЬ: ЭКЗЕМПЛЯР ВЫЗОВА (CALL)
# ============================================================

@dataclass
class Call:
    """Один экземпляр вызова метода."""
    call_id: int                 # уникальный id в пределах потока (только ENTER)
    class_name: str
    method_name: str
    thread_id: str
    parent_id: int | None        # call_id вызывающего (None для корневых)
    depth: int                   # глубина стека в момент ENTER
    step: int                    # индекс ENTER-события в списке events потока
    children: list[int] = field(default_factory=list)  # call_id детей


# ============================================================
# 1. ПОСТРОЕНИЕ CALL TREE
# ============================================================

def build_call_tree(events: list[dict], thread_id: str) -> dict[int, Call]:
    """
    Проходит события потока и строит call tree: call_id -> Call.

    - каждый ENTER создаёт новый Call (уникальный call_id)
    - parent_id = call_id того, кто был на вершине стека в момент ENTER
      (или None, если стек пуст — корневой вызов)
    - depth = len(stack) на момент ENTER
    - step  = индекс ENTER-события в events (хронологический номер)

    При рассинхроне (EXIT не на вершине / EXIT без ENTER) — мягкое закрытие:
    ищем сверху вниз ближайший call с тем же class+method, удаляем всё от
    него и выше. Если не нашли — EXIT игнорируется (это норма для
    частичного инструментирования, не warning).
    """
    calls: dict[int, Call] = {}
    stack: list[int] = []        # call_id активных вызовов
    next_id = 0

    for i, ev in enumerate(events):
        class_name = ev["className"]
        method_name = ev["methodName"]
        ntype = ev["type"].upper()

        if ntype == "ENTER":
            call_id = next_id
            next_id += 1
            parent_id = stack[-1] if stack else None
            call = Call(
                call_id=call_id,
                class_name=class_name,
                method_name=method_name,
                thread_id=thread_id,
                parent_id=parent_id,
                depth=len(stack),
                step=i,
            )
            calls[call_id] = call
            if parent_id is not None:
                calls[parent_id].children.append(call_id)
            stack.append(call_id)

        elif ntype == "EXIT":
            found_idx = None
            for idx in range(len(stack) - 1, -1, -1):
                c = calls[stack[idx]]
                if c.class_name == class_name and c.method_name == method_name:
                    found_idx = idx
                    break
            if found_idx is None:
                continue
            del stack[found_idx:]

        else:
            continue

    return calls


# ============================================================
# 2. ГРАФ (по call tree, уникальные узлы)
# ============================================================

def build_call_graph(events_by_thread: dict[str, list[dict]]):
    """
    Возвращает граф на уровне ЭКЗЕМПЛЯРОВ вызовов (call_id).

      graph            : caller_call_id -> set(callee_call_id)   (вложенность)
      sequential_graph : caller_call_id -> set(callee_call_id)   (порядок корневых)
      node_threads     : call_id -> Counter(thread_id -> 1)
      thread_calls     : thread_id -> set(call_id)
      calls_by_thread  : thread_id -> {call_id -> Call}
    """
    graph: dict[int, set[int]] = defaultdict(set)
    sequential_graph: dict[int, set[int]] = defaultdict(set)
    node_threads: dict[int, Counter] = defaultdict(Counter)
    thread_calls: dict[str, set[int]] = defaultdict(set)
    calls_by_thread: dict[str, dict[int, Call]] = {}

    for thread_id, events in events_by_thread.items():
        calls = build_call_tree(events, thread_id)
        calls_by_thread[thread_id] = calls

        # вложенность: parent -> child
        for call in calls.values():
            node_threads[call.call_id][thread_id] += 1
            thread_calls[thread_id].add(call.call_id)
            if call.parent_id is not None:
                graph[call.parent_id].add(call.call_id)

        # последовательность корневых в порядке call_id (он же порядок ENTER)
        roots = sorted(c.call_id for c in calls.values() if c.parent_id is None)
        for prev, nxt in zip(roots, roots[1:]):
            sequential_graph[prev].add(nxt)

    # гарантируем присутствие всех узлов в обоих графах
    for calls in calls_by_thread.values():
        for cid in calls:
            graph.setdefault(cid, set())
            sequential_graph.setdefault(cid, set())

    return (
        dict(graph),
        dict(sequential_graph),
        dict(node_threads),
        dict(thread_calls),
        calls_by_thread,
    )


# ============================================================
# 3. PAYLOAD ДЛЯ VIS-NETWORK (уникальные узлы + step)
# ============================================================

def build_per_thread_data(
    events_by_thread: dict[str, list[dict]],
    *,
    show_full_class: bool,
    show_sequential: bool,
) -> list[dict]:
    """
    Payload для vis-network. Каждый экземпляр вызова — отдельный узел.

      id    = "Class#method@call_id"     (уникальный)
      label = "Class\\nmethod #step"      (step — номер шага в логе)
      title = полный контекст: step, call_id, depth, parent, поток
    """

    def short_class(name: str) -> str:
        return name if show_full_class else name.rsplit(".", 1)[-1]

    def nid(call: Call) -> str:
        return f"{call.class_name}#{call.method_name}@{call.call_id}"

    def make_node(call: Call, in_deg: int, out_deg: int,
                  thread_color: str) -> dict:
        weight = in_deg + out_deg
        if weight >= 6:
            fill = "#5b8def"
        elif weight >= 3:
            fill = "#8fb3f5"
        elif in_deg and not out_deg:
            fill = "#a8d5a8"
        else:
            fill = "#e8f0fe"

        label = (
            f"{short_class(call.class_name)}\n"
            f"{call.method_name} #{call.step}"
        )
        parent_txt = (
            str(call.parent_id) if call.parent_id is not None else "root"
        )
        return {
            "id": nid(call),
            "label": label,
            "title": (
                f"{call.class_name}.{call.method_name}\n"
                f"step: {call.step}\n"
                f"call_id: {call.call_id}\n"
                f"depth: {call.depth}\n"
                f"parent: {parent_txt}\n"
                f"поток: {call.thread_id}"
            ),
            "shape": "box",
            "color": {"background": fill, "border": thread_color},
            "borderWidth": 3,
            "font": {"size": 12, "face": "Consolas, monospace"},
        }

    result: list[dict] = []

    for t_idx, (thread_id, events) in enumerate(events_by_thread.items()):
        thread_color = THREAD_PALETTE[t_idx % len(THREAD_PALETTE)]

        calls = build_call_tree(events, thread_id)
        if not calls:
            result.append({"thread_id": thread_id, "nodes": [], "edges": []})
            continue

        # вложенность: parent -> child
        nested: dict[int, set[int]] = defaultdict(set)
        for call in calls.values():
            if call.parent_id is not None:
                nested[call.parent_id].add(call.call_id)

        # последовательность корневых
        sequential: dict[int, set[int]] = defaultdict(set)
        roots = sorted(c.call_id for c in calls.values() if c.parent_id is None)
        for prev, nxt in zip(roots, roots[1:]):
            sequential[prev].add(nxt)

        # степени для раскраски
        in_deg: dict[int, int] = defaultdict(int)
        out_deg: dict[int, int] = defaultdict(int)
        for caller, callees in nested.items():
            out_deg[caller] += len(callees)
            for c in callees:
                in_deg[c] += 1
        for cid in calls:
            in_deg[cid] += 0
            out_deg[cid] += 0

        nodes_payload = [
            make_node(calls[cid], in_deg[cid], out_deg[cid], thread_color)
            for cid in sorted(calls)
        ]

        edges_payload: list[dict] = []

        # nested: parent -> child
        for caller_id, callees in nested.items():
            caller = calls[caller_id]
            for callee_id in callees:
                callee = calls[callee_id]
                edges_payload.append({
                    "from": nid(caller),
                    "to": nid(callee),
                    "arrows": "to",
                    "color": {"color": "#555555", "highlight": "#000000"},
                    "width": 1.5,
                    "title": (
                        f"[вложенный] step {caller.step} -> step {callee.step}\n"
                        f"{caller.class_name}.{caller.method_name}@{caller.call_id}"
                        f" -> "
                        f"{callee.class_name}.{callee.method_name}@{callee.call_id}"
                    ),
                    "kind": "nested",
                })

        # sequential: между корневыми (если нет nested-дубля)
        if show_sequential:
            for caller_id, callees in sequential.items():
                caller = calls[caller_id]
                for callee_id in callees:
                    if callee_id in nested.get(caller_id, set()):
                        continue
                    callee = calls[callee_id]
                    edges_payload.append({
                        "from": nid(caller),
                        "to": nid(callee),
                        "arrows": "to",
                        "color": {"color": "#e6194b", "highlight": "#a00030"},
                        "width": 1.2,
                        "dashes": [6, 4],
                        "title": (
                            f"[последовательный] step {caller.step} -> step {callee.step}\n"
                            f"{caller.class_name}.{caller.method_name}@{caller.call_id}"
                            f" -> "
                            f"{callee.class_name}.{callee.method_name}@{callee.call_id}"
                        ),
                        "kind": "sequential",
                    })

        result.append({
            "thread_id": thread_id,
            "nodes": nodes_payload,
            "edges": edges_payload,
        })

    return result


# ============================================================
# 4. ЗАГРУЗКА ДАННЫХ
# ============================================================

def load_one_stack(json_path: Path) -> dict[str, list[dict]] | None:
    """
    Читает один JSON. Форматы:
      a) {thread_id: [events...]}
      b) [events...]  -> ключ = имя файла (stem)
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
# 5. РЕНДЕР ОДНОГО HTML
# ============================================================

def _render_one(events_by_thread: dict[str, list[dict]],
                out_path: Path, *, title: str) -> None:
    (graph, seq_graph, node_threads,
     thread_calls, calls_by_thread) = build_call_graph(events_by_thread)

    total_nodes = sum(len(c) for c in calls_by_thread.values())
    total_nested = sum(len(v) for v in graph.values())
    total_seq = sum(len(v) for v in seq_graph.values())

    log.info(
        "[%s] threads=%d nodes=%d nested=%d sequential=%d",
        title, len(events_by_thread), total_nodes, total_nested, total_seq,
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
# 6. ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def generate_flow_htmls(*, config_path: Path | None = None) -> Path | None:
    """
    Читает конфиг, данные, генерирует HTML в <flow.stack-output>/html.
    Возвращает путь к директории или None, если не удалось.

    Вызывается:
      - лениво из AppContext при первом /flow-list;
      - пакетно через `python -m flow_graph.build_graph`.
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
# 7. ПАКЕТНЫЙ РЕЖИМ
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