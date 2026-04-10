#!/usr/bin/env python3
"""
DIANA-Nexus OS — GUI Web Server

Serves the DIANA-Nexus desktop GUI and exposes a REST API
for live /proc/diana stats. Designed to run as PID 2 inside
the OS (started by /init after the kernel module is loaded).

Features:
  - Serves userspace/gui/ static files (HTML/CSS/JS)
  - /api/status — JSON snapshot of kernel stats
  - /api/p2p    — P2P bus message log
  - /api/hints  — Write LSTM hints

Author: Sahidh — DIANA Architecture
"""

import os
import sys
import json
import http.server
import socketserver
import threading
import time
import signal
from pathlib import Path
from urllib.parse import urlparse

# Add parent for synapse imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = 8080
PROC_PATH = "/proc/diana"

# ── Kernel Interface ──

def read_proc(name):
    """Read a /proc/diana/ file safely."""
    path = os.path.join(PROC_PATH, name)
    try:
        with open(path, "r") as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return None


def parse_stats():
    """Parse /proc/diana/stats into structured JSON."""
    raw = read_proc("stats")
    if not raw:
        return _simulated_stats()

    components = {}
    current = None
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("[") and "SYNAPSE" in line:
            current = line.strip("[]").split()[0]
            components[current] = {}
        elif line.startswith("[") and current:
            current = line.strip("[]").split()[0]
            components[current] = {}
        elif ":" in line and current:
            key, _, value = line.partition(":")
            components[current][key.strip()] = value.strip()
    return components


def _simulated_stats():
    """Generate simulated stats when kernel module isn't loaded."""
    import random
    return {
        "RAM": {
            "patterns_learned": str(random.randint(100, 5000)),
            "predictions": str(random.randint(50, 2000)),
            "accuracy": str(random.randint(75, 95)) + "%",
            "total_allocs": str(random.randint(1000, 50000)),
            "prefetch_hits": f"{random.randint(100, 1000)} / misses: {random.randint(5, 50)}",
        },
        "GPU": {
            "patterns_learned": str(random.randint(100, 3000)),
            "predictions": str(random.randint(50, 1500)),
            "accuracy": str(random.randint(80, 98)) + "%",
            "render_count": str(random.randint(500, 5000)),
        },
        "SSD": {
            "patterns_learned": str(random.randint(200, 4000)),
            "predictions": str(random.randint(100, 2500)),
            "accuracy": str(random.randint(70, 90)) + "%",
            "total_reads": str(random.randint(500, 10000)),
        },
        "CACHE": {
            "patterns_learned": str(random.randint(500, 8000)),
            "predictions": str(random.randint(200, 3000)),
            "accuracy": str(random.randint(90, 99)) + "%",
            "cache_hits": str(random.randint(5000, 50000)),
        },
    }


def parse_p2p():
    """Parse /proc/diana/p2p_log."""
    raw = read_proc("p2p_log")
    if not raw:
        return []
    lines = []
    for line in raw.strip().split("\n"):
        if "->" in line and "TIMESTAMP" not in line and "---" not in line:
            lines.append(line.strip())
    return lines[-20:]  # last 20


def get_cpu_report():
    """Read CPU observer report."""
    raw = read_proc("cpu_report")
    if not raw:
        return {
            "mode": "PASSIVE OBSERVER",
            "commands_issued": 0,
            "status_updates_received": 0,
        }
    data = {}
    for line in raw.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip()
    return data


# ── HTTP Server ──

class DIANAHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves GUI + API."""

    GUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API Routes
        if path == "/api/status":
            self._json_response({
                "kernel": "DIANA-Nexus Kernel",
                "version": "0.1",
                "components": parse_stats(),
                "cpu": get_cpu_report(),
                "p2p_log": parse_p2p(),
                "uptime": time.monotonic(),
            })
            return

        elif path == "/api/p2p":
            self._json_response({"log": parse_p2p()})
            return

        elif path == "/api/hints":
            self._json_response({"hint": read_proc("hints") or "No hints"})
            return

        # Static files from gui/
        if path == "/" or path == "":
            path = "/boot.html"

        filepath = os.path.join(self.GUI_DIR, path.lstrip("/"))
        if os.path.isfile(filepath):
            self._serve_file(filepath)
        else:
            self.send_error(404, f"Not found: {path}")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/hints":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            hints_path = os.path.join(PROC_PATH, "hints")
            try:
                with open(hints_path, "w") as f:
                    f.write(body)
                self._json_response({"status": "ok"})
            except (FileNotFoundError, PermissionError):
                self._json_response({"status": "error", "msg": "Cannot write hints"}, 500)
        else:
            self.send_error(404)

    def _json_response(self, data, code=200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, filepath):
        ext = os.path.splitext(filepath)[1]
        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
        }
        ctype = content_types.get(ext, "application/octet-stream")
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(content))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        """Suppress noisy access logs unless in debug mode."""
        if os.environ.get("DIANA_DEBUG"):
            super().log_message(format, *args)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="DIANA-Nexus OS GUI Server"
    )
    parser.add_argument("--port", type=int, default=8080,
                        help="Port to serve on")
    parser.add_argument("--proc-path", default="/proc/diana",
                        help="Path to DIANA proc interface")
    parser.add_argument("--gui-dir", default=None,
                        help="Override GUI directory")
    args = parser.parse_args()

    global PORT, PROC_PATH
    PORT = args.port
    PROC_PATH = args.proc_path

    if args.gui_dir:
        DIANAHandler.GUI_DIR = args.gui_dir

    print("╔═══════════════════════════════════════════╗")
    print("║  DIANA-Nexus OS — GUI Server Starting     ║")
    print(f"║  Port: {PORT}                               ║")
    print(f"║  GUI : {DIANAHandler.GUI_DIR}")
    print("╚═══════════════════════════════════════════╝")

    with socketserver.TCPServer(("0.0.0.0", PORT), DIANAHandler) as httpd:
        def shutdown_handler(sig, frame):
            print("\nDIANA GUI Server shutting down...")
            httpd.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        print(f"Serving DIANA-Nexus Desktop at http://localhost:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
