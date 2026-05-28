import json
from pathlib import Path


# ---------------------------
# BUILD TREE (REPLAY STACK)
# ---------------------------
def build_tree(events, thread_id="unknown"):
    tests = []
    stack = []

    stats = {
        "source_events": len(events),
        "enter_events": 0,
        "exit_events": 0,
        "tree_nodes": 0,
        "lost_events": [],
        "errors": []
    }

    has_tests = any(e["type"] == "START_TEST" for e in events)

    # Если тестов нет — создаем root THREAD
    if not has_tests:
        root = {
            "name": "THREAD",
            "type": "THREAD",
            "children": [],
            "ts": events[0].get("ts", 0) if events else 0,
            "depth": 0
        }

        tests.append(root)
        stack = [root]

        stats["tree_nodes"] += 1

    for idx, e in enumerate(events):
        etype = e.get("type")

        # ---------------------------
        # START_TEST
        # ---------------------------
        if etype == "START_TEST":
            node = {
                "name": f'TEST.{e.get("name", "unknown")}',
                "type": "TEST",
                "children": [],
                "ts": e.get("ts", 0),
                "depth": 0
            }

            tests.append(node)
            stack = [node]

            stats["tree_nodes"] += 1
            continue

        # ---------------------------
        # END_TEST
        # ---------------------------
        if etype == "END_TEST":

            # Проверяем что стек закрыт
            if len(stack) > 1:
                stats["errors"].append(
                    f"[{thread_id}] END_TEST with unclosed stack "
                    f"({len(stack)-1} nodes remain)"
                )

            stack = []
            continue

        # ---------------------------
        # ENTER
        # ---------------------------
        if etype == "ENTER":

            stats["enter_events"] += 1

            name = f'{e.get("className", "?")}.{e.get("methodName", "?")}'

            node = {
                "name": name,
                "type": "METHOD",
                "children": [],
                "ts": e.get("ts", 0),
                "depth": len(stack)
            }

            # ENTER без родителя
            if not stack:
                stats["errors"].append(
                    f"[{thread_id}] ENTER without parent "
                    f"at index {idx}: {name}"
                )

                stats["lost_events"].append(idx)
                continue

            stack[-1]["children"].append(node)
            stack.append(node)

            stats["tree_nodes"] += 1

        # ---------------------------
        # EXIT
        # ---------------------------
        elif etype == "EXIT":

            stats["exit_events"] += 1

            name = f'{e.get("className", "?")}.{e.get("methodName", "?")}'

            # EXIT без ENTER
            if not stack:
                stats["errors"].append(
                    f"[{thread_id}] EXIT without ENTER "
                    f"at index {idx}: {name}"
                )

                stats["lost_events"].append(idx)
                continue

            current = stack[-1]

            # Проверяем совпадение метода
            if current["name"] != name:
                stats["errors"].append(
                    f"[{thread_id}] STACK MISMATCH at index {idx}: "
                    f"expected EXIT '{current['name']}', got '{name}'"
                )

            stack.pop()

        # ---------------------------
        # UNKNOWN EVENT
        # ---------------------------
        else:
            stats["errors"].append(
                f"[{thread_id}] UNKNOWN EVENT TYPE at index {idx}: {etype}"
            )

    # ---------------------------
    # FINAL VALIDATION
    # ---------------------------

    # Остались незакрытые методы
    if stack:
        remaining = [n["name"] for n in stack]

        stats["errors"].append(
            f"[{thread_id}] UNCLOSED STACK: {remaining}"
        )

    expected_method_nodes = stats["enter_events"]

    # tree_nodes включает TEST/THREAD
    actual_method_nodes = count_method_nodes(tests)

    if expected_method_nodes != actual_method_nodes:
        stats["errors"].append(
            f"[{thread_id}] LOST EVENTS DETECTED: "
            f"ENTER events = {expected_method_nodes}, "
            f"nodes in tree = {actual_method_nodes}"
        )

    return tests, stats


# ---------------------------
# COUNT METHOD NODES
# ---------------------------
def count_method_nodes(nodes):
    total = 0

    for node in nodes:
        if node.get("type") == "METHOD":
            total += 1

        total += count_method_nodes(node.get("children", []))

    return total


# ---------------------------
# LOAD JSON FILE
# ---------------------------
def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# HTML RENDER
# ---------------------------
def render_node(node):
    children_html = "".join(render_node(c) for c in node["children"])

    return f"""
    <div class="node" data-depth="{node['depth']}">
        <div class="title">
            {node['name']} (lvl {node['depth']})
        </div>

        <div class="children">
            {children_html}
        </div>
    </div>
    """


# ---------------------------
# EXPORT HTML
# ---------------------------
def export_html(trees_by_thread, out_file):
    html = """
<html>
<head>
<meta charset="utf-8"/>

<style>

body {
    font-family: monospace;
    font-size: 13px;
}

#toolbar {
    position: sticky;
    top: 0;
    background: white;
    padding: 10px;
    border-bottom: 1px solid #ccc;
    z-index: 1000;
}

.node {
    margin-left: 20px;
}

.title {
    padding: 2px;
    cursor: pointer;
}

.title:hover {
    background: #f0f0f0;
}

.children {
    margin-left: 20px;
    border-left: 1px solid #ddd;
    padding-left: 8px;
}

.error {
    color: red;
    font-weight: bold;
}

.ok {
    color: green;
}

</style>
</head>

<body>

<div id="toolbar">
    <h3>Trace Viewer</h3>

    <label>Max depth:</label>

    <input type="range"
           min="0"
           max="50"
           value="10"
           id="depthSlider">

    <span id="depthVal">10</span>
</div>

<div id="tree">
"""

    for thread_id, trees in trees_by_thread.items():

        html += f"<h2>{thread_id}</h2>"

        for t in trees:
            html += render_node(t)

    html += """
</div>

<script>

const slider = document.getElementById("depthSlider");
const label = document.getElementById("depthVal");

function applyFilter() {

    const maxDepth = parseInt(slider.value);

    label.innerText = maxDepth;

    document.querySelectorAll(".node").forEach(n => {

        const d = parseInt(n.dataset.depth);

        n.style.display = (d <= maxDepth)
            ? "block"
            : "none";
    });
}

slider.oninput = applyFilter;

applyFilter();

</script>

</body>
</html>
"""

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------
# PROCESS ONE FILE
# ---------------------------
def process_file(json_file: Path, output_dir: Path):

    try:
        data = load_json(json_file)

        trees_by_thread = {}

        print("\n" + "=" * 80)
        print(f"FILE: {json_file.name}")
        print("=" * 80)

        for thread_id, events in data.items():

            trees, stats = build_tree(events, thread_id)

            trees_by_thread[thread_id] = trees

            print(f"\nTHREAD: {thread_id}")

            print(f"  source_events : {stats['source_events']}")
            print(f"  enter_events  : {stats['enter_events']}")
            print(f"  exit_events   : {stats['exit_events']}")
            print(f"  lost_events   : {len(stats['lost_events'])}")

            if stats["errors"]:

                print("  STATUS        : FAIL")

                for err in stats["errors"]:
                    print(f"    ERROR: {err}")

            else:
                print("  STATUS        : OK")

        output_file = output_dir / f"{json_file.stem}.html"

        export_html(trees_by_thread, output_file)

        print(f"\nHTML: {output_file.name}")

    except Exception as e:
        print(f"\nFAIL: {json_file.name}")
        print(e)


# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":

    INPUT_DIR = Path("./stacks")
    OUTPUT_DIR = Path("./html")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list(INPUT_DIR.glob("*.json"))

    if not files:
        print("No json files found in ./stacks")
        exit(0)

    for json_file in files:
        process_file(json_file, OUTPUT_DIR)

    print("\nDONE")