#!/usr/bin/env python3
"""
web/build.py — Embed data/results.json into web/index.html to produce web/report.html.

Usage:
    python web/build.py                        # reads data/results.json
    python web/build.py --serve                # also starts a local HTTP server on :8000
    python web/build.py --json path/to/f.json  # custom JSON path
"""
import argparse
import http.server
import json
import os
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
TEMPLATE = os.path.join(WEB_DIR, "index.html")
OUTPUT = os.path.join(WEB_DIR, "report.html")
DEFAULT_JSON = os.path.join(ROOT, "data", "results.json")


def build(json_path: str = DEFAULT_JSON, output: str = OUTPUT) -> str:
    if not os.path.exists(json_path):
        sys.exit(
            f"[build] JSON not found: {json_path}\n"
            "Run: python report.py --export data/results.json"
        )
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()

    embedded = json.dumps(data, ensure_ascii=False)
    html = template.replace("%%RESULTS_JSON%%", embedded)

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[build] wrote {os.path.relpath(output, ROOT)}")
    return output


def serve(directory: str, port: int = 8000):
    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.HTTPServer(("", port), handler)
    url = f"http://localhost:{port}/report.html"
    print(f"[serve] http://localhost:{port}/report.html  (Ctrl+C to stop)")
    # Try to open in browser non-blocking
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    os.chdir(directory)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] stopped.")


def main():
    p = argparse.ArgumentParser(description="Build AutoSense frontend")
    p.add_argument("--json", default=DEFAULT_JSON, metavar="PATH",
                   help="Path to results JSON (default: data/results.json)")
    p.add_argument("--out", default=OUTPUT, metavar="PATH",
                   help="Output HTML path (default: web/report.html)")
    p.add_argument("--serve", action="store_true",
                   help="Start a local HTTP server after building")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    output = build(args.json, args.out)
    if args.serve:
        serve(WEB_DIR, args.port)


if __name__ == "__main__":
    main()
