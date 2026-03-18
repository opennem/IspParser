#!/usr/bin/env python3
"""Local HTTP server for testing the ISP chart viewer."""

import http.server
import functools
import os
import shutil
import sys

from build import discover_releases, generate_releases_json

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
DIR = os.path.join(PROJECT_ROOT, "site")
JSON_BASE = os.path.join(PROJECT_ROOT, "output", "releases")

# Assemble site directory: pages-template + JSON output
os.makedirs(DIR, exist_ok=True)
for src_dir in [os.path.join(PROJECT_ROOT, "pages-template"),
                os.path.join(PROJECT_ROOT, "output", "releases")]:
    if os.path.isdir(src_dir):
        shutil.copytree(src_dir, DIR, dirs_exist_ok=True)

# Generate releases.json manifest
releases = discover_releases(JSON_BASE)
generate_releases_json(releases, JSON_BASE, DIR)

os.chdir(DIR)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIR)
server = http.server.HTTPServer(("127.0.0.1", PORT), handler)
print(f"Serving site at http://localhost:{PORT}")
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopped.")
