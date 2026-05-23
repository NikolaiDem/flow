import json


# ---------------------------
# BUILD TREE (REPLAY STACK)
# ---------------------------
def build_tree(events):
    stack = []
    roots = []

    for e in events:
        name = f'{e["className"]}.{e["methodName"]}'

        if e["type"] == "ENTER":
            node = {
                "name": name,
                "children": [],
                "depth": len(stack),
                "ts": e.get("ts", 0)
            }

            if stack:
                stack[-1]["children"].append(node)
            else:
                roots.append(node)

            stack.append(node)

        else:
            if stack:
                stack.pop()

    return roots


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
                display: block;
                border-left: 1px solid #ddd;
                padding-left: 8px;
            }
        </style>
    </head>

    <body>

    <div id="toolbar">
        <h3>Trace Viewer</h3>

        <label>Min depth:</label>
        <input type="range" min="0" max="20" value="0" id="minDepth">
        <span id="minVal">0</span>

        <br/>

        <label>Max depth:</label>
        <input type="range" min="0" max="20" value="20" id="maxDepth">
        <span id="maxVal">20</span>

        <br/>

        <button onclick="setRange(0,2)">Top level</button>
        <button onclick="setRange(2,5)">Mid level</button>
        <button onclick="setRange(5,20)">Deep</button>
    </div>

    <div id="tree">
    """

    # ---------------- TREE ----------------
    def render_node(node):
        children = "".join(render_node(c) for c in node["children"])

        return f"""
        <div class="node" data-depth="{node['depth']}">
            <div class="title">{node['name']} (lvl {node['depth']})</div>
            <div class="children">
                {children}
            </div>
        </div>
        """

    for thread_id, trees in trees_by_thread.items():
        html += f"<h2>Thread {thread_id}</h2>"

        for t in trees:
            html += render_node(t)

    # ---------------- JS ----------------
    html += """
    </div>

    <script>
        // collapse / expand
        document.querySelectorAll('.title').forEach(el => {
            el.onclick = () => {
                el.parentElement.classList.toggle('open');
            };
        });

        const minSlider = document.getElementById("minDepth");
        const maxSlider = document.getElementById("maxDepth");

        const minVal = document.getElementById("minVal");
        const maxVal = document.getElementById("maxVal");

        function applyFilter() {
            const min = parseInt(minSlider.value);
            const max = parseInt(maxSlider.value);

            minVal.innerText = min;
            maxVal.innerText = max;

            document.querySelectorAll(".node").forEach(n => {
                const depth = parseInt(n.dataset.depth);

                if (depth >= min && depth <= max) {
                    n.style.display = "block";
                } else {
                    n.style.display = "none";
                }
            });
        }

        minSlider.oninput = applyFilter;
        maxSlider.oninput = applyFilter;

        function setRange(min, max) {
            minSlider.value = min;
            maxSlider.value = max;
            applyFilter();
        }

        applyFilter();
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
    with open("/Users/nikolajdemin/work/projects/stacks/stack1.json") as f:
        data = json.load(f)

    trees_by_thread = {}

    for thread_id, events in data.items():
        trees_by_thread[thread_id] = build_tree(events)

    export_html(trees_by_thread)

    print("trace2.html generated")