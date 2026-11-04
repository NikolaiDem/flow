import random
from flow_graph.config import *

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