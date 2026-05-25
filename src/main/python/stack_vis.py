import json

# ---------------------------
# BUILD TREE (REPLAY STACK)
# ---------------------------
def build_tree(events):
    tests = []
    stack = []
    current_test = None

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
        current_test = root

    for e in events:
        etype = e["type"]

        if etype == "START_TEST":
            current_test = {
                "name": f'TEST.{e.get("name", "unknown")}',
                "type": "TEST",
                "children": [],
                "ts": e.get("ts", 0),
                "depth": 0
            }
            tests.append(current_test)
            stack = [current_test]
            continue

        if etype == "END_TEST":
            stack = []
            current_test = None
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
# FILTER TREE (0..max_depth)
# ---------------------------
def filter_tree(node, max_depth):
    depth = node.get("depth", 0)

    # cut-off rule
    if depth > max_depth:
        return None

    filtered_children = []
    for child in node.get("children", []):
        f = filter_tree(child, max_depth)
        if f is not None:
            filtered_children.append(f)

    return {
        **node,
        "children": filtered_children
    }


def filter_trees(trees, max_depth):
    return [
        t for tree in trees
        if (t := filter_tree(tree, max_depth)) is not None
    ]


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


def export_html(trees_by_thread, out_file="trace.html"):
    html = """
    <html>
    <head>
        <meta charset="utf-8"/>

        <style>
            body {
                font-family: monospace;
                font-size: 13px;
            }

            .node {
                margin-left: 20px;
                cursor: pointer;
            }

            .title {
                padding: 2px;
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

    <div id="tree">
    """

    for thread_id, trees in trees_by_thread.items():
        html += f"<h2>Thread {thread_id}</h2>"

        for t in trees:
            html += render_node(t)

    html += """
    </div>

    <script>
        document.querySelectorAll('.title').forEach(el => {
            el.onclick = () => {
                const c = el.parentElement.querySelector('.children');
                if (c) {
                    c.style.display = (c.style.display === 'none') ? 'block' : 'none';
                }
            };
        });
    </script>

    </body>
    </html>
    """

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    MAX_DEPTH = 5  # 👈 главный параметр фильтра

    with open("/stack1.json") as f:
        data = json.load(f)

    trees_by_thread = {}

    for thread_id, events in data.items():
        trees = build_tree(events)
        trees = filter_trees(trees, MAX_DEPTH)
        trees_by_thread[thread_id] = trees

    export_html(trees_by_thread, out_file="trace.html")

    print("trace.html generated")