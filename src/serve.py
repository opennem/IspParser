#!/usr/bin/env python3
"""Local HTTP server for testing the ISP chart viewer."""

import http.server
import functools
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(SCRIPT_DIR, "..", "site")

os.chdir(DIR)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIR)
server = http.server.HTTPServer(("127.0.0.1", PORT), handler)
print(f"Serving site at http://localhost:{PORT}")
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nStopped.")
