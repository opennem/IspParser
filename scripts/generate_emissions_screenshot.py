#!/usr/bin/env python3
"""Regenerate docs/emissions-comparison.png — the emissions-comparison hero
image used in the README.

It serves the built ``site/`` directory, opens the chart viewer in compare mode
with a curated set of ISP releases, and screenshots the "Emissions Comparison"
card. The most recent release is drawn in the brand colour by the frontend
(see renderEmissionsComparison in pages-template/app.js); older vintages are red
and told apart by dash pattern.

Prerequisites (run once):
    python src/ispparser.py            # parse workbooks -> output/releases/
    python src/build.py all            # build site/ + releases.json
    pip install playwright             # then: playwright install chromium

Usage:
    python scripts/generate_emissions_screenshot.py
    python scripts/generate_emissions_screenshot.py --releases 2024_ISP_final,2026_ISP_final
"""

import argparse
import functools
import http.server
import os
import threading

from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(REPO_ROOT, "site")
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "docs", "emissions-comparison.png")

# Curated vintages for the README image (oldest -> newest): the final release of
# each ISP, no drafts. The frontend highlights the newest release in the brand
# colour, so 2026_ISP_final stands out. (The 2018 ISP is omitted — it has no
# emissions data, so it would contribute no line.)
DEFAULT_RELEASES = [
    "2020_ISP_final",
    "2022_ISP_final",
    "2024_ISP_final",
    "2026_ISP_final",
]


def serve_site(directory):
    """Start a background HTTP server for `directory`; return (server, port)."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    # port 0 -> let the OS pick a free port
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = server.socket.getsockname()[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--releases", default=",".join(DEFAULT_RELEASES),
                    help="Comma-separated release ids to compare (oldest first).")
    ap.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path.")
    ap.add_argument("--site-dir", default=SITE_DIR, help="Built site/ directory to serve.")
    # A narrow viewport renders the charts single-column, so the emissions card
    # is sized to its own content (no empty space from the equal-height 2-col grid).
    ap.add_argument("--width", type=int, default=760, help="Viewport width (px).")
    ap.add_argument("--height", type=int, default=1100, help="Viewport height (px).")
    args = ap.parse_args()

    if not os.path.exists(os.path.join(args.site_dir, "releases.json")):
        raise SystemExit(
            f"No releases.json in {args.site_dir!r}. Build the site first:\n"
            "  python src/ispparser.py && python src/build.py all"
        )

    server, port = serve_site(args.site_dir)
    url = f"http://127.0.0.1:{port}/?shot=1#compare=true&releases={args.releases}"
    print(f"Serving {args.site_dir} on port {port}")
    print(f"Opening {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": args.width, "height": args.height},
                device_scale_factor=2,  # crisp 2x output
            )
            page.goto(url, wait_until="networkidle")
            # Wait for the emissions chart to exist, then let its load animation settle.
            page.wait_for_selector("#chart-emissions", state="visible", timeout=15000)
            page.wait_for_timeout(1500)
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            page.locator("#card-emissions").screenshot(path=args.output)
            browser.close()
    finally:
        server.shutdown()

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
