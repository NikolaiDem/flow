import json
from pathlib import Path


# ---------------------------
# BUILD TREE (REPLAY STACK)
# ---------------------------
def build_tree(events):
    tests = []
    stack = []

    has_tests = any(e["type"] == "START_TEST" for e in events)

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

    for e in events:
        etype = e["type"]

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
            continue

        if etype == "END_TEST":
            stack = []
            continue

        name = f'{e["className"]}.{e["methodName"]}'

        if etype == "ENTER":
            node = {
                "name": name,
                "children": [],
                "ts": e.get("ts", 0),
                "depth": len(stack)
            }

            if stack:
                stack[-1]["children"].append(node)

            stack.append(node)

        elif etype == "EXIT":
            if stack:
                stack.pop()

    return tests


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
</style>
</head>

<body>

<div id="toolbar">
    <h3>Trace Viewer</h3>

    <label>Max depth (0..n): </label>
    <input type="range" min="0" max="30" value="10" id="depthSlider">
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
        n.style.display = (d <= maxDepth) ? "block" : "none";
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

        for thread_id, events in data.items():
            trees_by_thread[thread_id] = build_tree(events)

        output_file = output_dir / f"{json_file.stem}.html"

        export_html(trees_by_thread, output_file)

        print(f"OK: {json_file.name} -> {output_file.name}")

    except Exception as e:
        print(f"FAIL: {json_file.name}: {e}")


# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    INPUT_DIR = Path("./stacks")
    OUTPUT_DIR = Path("./html")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for json_file in INPUT_DIR.glob("*.json"):
        process_file(json_file, OUTPUT_DIR)

    print("DONE")