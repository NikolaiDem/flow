# main.py
from __future__ import annotations

import argparse

from server import serve


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="main.py", description="JFR/Tests/Flow viewer")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--threaded", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    serve(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        threaded=args.threaded,
    )


if __name__ == "__main__":
    main()