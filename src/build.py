#!/usr/bin/env python3
"""
Build ISP site output: zip archives and releases.json manifest.

Usage:
    python build.py all                     # everything
    python serve.py                         # local HTTP server for testing
"""

import argparse
import json
import os
import zipfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def discover_releases(json_base):
    """Auto-discover releases from the output/releases directory."""
    if not os.path.isdir(json_base):
        return []
    releases = []
    for entry in sorted(os.listdir(json_base)):
        release_dir = os.path.join(json_base, entry)
        if not os.path.isdir(release_dir):
            continue
        json_files = [f for f in os.listdir(release_dir) if f.endswith(".json")]
        if json_files:
            releases.append(entry)
    return releases


def get_scenarios(json_dir):
    """Get scenario names from JSON files in a release directory."""
    return [f.replace(".json", "") for f in sorted(os.listdir(json_dir)) if f.endswith(".json")]


def make_release_label(release_id):
    """Turn '2024_ISP_draft' into '2024 ISP Draft'."""
    return release_id.replace("_", " ").replace("ISP", "ISP").title().replace("Isp", "ISP")


def generate_releases_json(releases, json_base, output_dir):
    """Generate releases.json manifest from the output JSON files."""
    manifest = []
    for release_id in releases:
        json_dir = os.path.join(json_base, release_id)
        scenarios = get_scenarios(json_dir)
        manifest.append({
            "id": release_id,
            "label": make_release_label(release_id),
            "scenarios": scenarios,
        })

    path = os.path.join(output_dir, "releases.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  {path}")


def create_release_zips(output_dir):
    """Create a zip file for each release directory containing JSON files."""
    for entry in sorted(os.listdir(output_dir)):
        release_dir = os.path.join(output_dir, entry)
        if not os.path.isdir(release_dir):
            continue
        json_files = [f for f in os.listdir(release_dir) if f.endswith(".json")]
        if not json_files:
            continue
        zip_path = os.path.join(output_dir, f"{entry}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for jf in sorted(json_files):
                zf.write(os.path.join(release_dir, jf), jf)
        print(f"  {zip_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build ISP site output")
    sub = parser.add_subparsers(dest="command")

    all_parser = sub.add_parser("all", help="Build everything")
    all_parser.add_argument("--max-to-process", type=int, default=None,
                            help="Max number of releases to process")

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_base = os.path.join(script_dir, "..", "output", "releases")
    output_base = os.path.join(script_dir, "..", "site")
    os.makedirs(output_base, exist_ok=True)

    if args.command == "all":
        releases = discover_releases(json_base)
        max_to_process = getattr(args, 'max_to_process', None)
        if max_to_process is not None:
            releases = releases[:max_to_process]

        print("Generating releases.json")
        generate_releases_json(releases, json_base, output_base)

        print("Creating zip files")
        create_release_zips(output_base)

        print("\nDone.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
