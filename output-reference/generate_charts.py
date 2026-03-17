#!/usr/bin/env python3
"""
Generate verification charts from ISP JSON output files.

Reads the JSON files produced by ispparser.ipynb and creates line charts
for generation and capacity by technology, for NEM-wide and each region.

Usage:
    python generate_charts.py [--release 2026_ISP_draft] [--scenario step_change] [--cdp CDP1]
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# region display names
REGION_LABELS = {
    "_all": "NEM",
    "nsw1": "NSW",
    "qld1": "QLD",
    "sa1": "SA",
    "tas1": "TAS",
    "vic1": "VIC",
}

REGIONS = ["_all", "nsw1", "qld1", "sa1", "tas1", "vic1"]

# technologies to chart (in display order) and their colors
CHART_TECHS = {
    "energy": [
        ("coal_black",       "Black coal",        "#251C00"),
        ("coal_brown",       "Brown coal",        "#675B42"),
        ("gas_ccgt",         "Mid-merit gas",     "#ED9C2C"),
        ("gas_ocgt",         "Flexible gas",      "#F0AC4A"),
        ("gas_ccgt_ccs",     "Gas with CCS",      "#F1AB4B"),
        ("hydro",            "Hydro",             "#ACE9FE"),
        ("wind",             "Wind",              "#246D36"),
        ("wind_offshore",    "Offshore wind",     "#53AD69"),
        ("solar_utility",    "Utility-scale solar", "#FECE00"),
        ("solar_rooftop",    "Rooftop solar",     "#FFEB5C"),
        ("bioenergy",        "Bioenergy",         "#069FAF"),
        ("battery_discharging", "Battery",        "#3145CE"),
    ],
    "capacity": [
        ("coal_black",       "Black coal",        "#251C00"),
        ("coal_brown",       "Brown coal",        "#675B42"),
        ("gas_ccgt",         "Mid-merit gas",     "#ED9C2C"),
        ("gas_ocgt",         "Flexible gas",      "#F0AC4A"),
        ("gas_ccgt_ccs",     "Gas with CCS",      "#F1AB4B"),
        ("hydro",            "Hydro",             "#ACE9FE"),
        ("wind",             "Wind",              "#246D36"),
        ("wind_offshore",    "Offshore wind",     "#53AD69"),
        ("solar_utility",    "Utility-scale solar", "#FECE00"),
        ("solar_rooftop",    "Rooftop solar",     "#FFEB5C"),
        ("bioenergy",        "Bioenergy",         "#069FAF"),
        ("battery",          "Battery",           "#3145CE"),
    ],
}

TYPE_LABELS = {"energy": "Generation", "capacity": "Capacity"}
TYPE_UNITS = {"energy": "TWh", "capacity": "GW"}
TYPE_DIVISOR = {"energy": 1000, "capacity": 1000}  # GWh->TWh, MW->GW


def load_json(path):
    with open(path) as f:
        return json.load(f)


def extract_series(data, series_type, region, cdp):
    """Extract year->value dict for each fuel_tech matching the filters."""
    results = {}
    for entry in data["data"]:
        if entry["type"] != series_type:
            continue
        if entry["region"] != region:
            continue
        if entry["pathway"] != cdp:
            continue
        ft = entry.get("fuel_tech")
        if ft is None:
            continue
        proj = entry["projection"]
        start_year = int(proj["start"][:4])
        values = proj["data"]
        years = list(range(start_year, start_year + len(values)))
        results[ft] = (years, values)
    return results


def create_chart(data, series_type, region, cdp, release, scenario, output_path):
    """Create and save a single line chart."""
    series = extract_series(data, series_type, region, cdp)
    techs = CHART_TECHS[series_type]
    divisor = TYPE_DIVISOR[series_type]
    unit = TYPE_UNITS[series_type]
    type_label = TYPE_LABELS[series_type]
    region_label = REGION_LABELS.get(region, region)

    fig, ax = plt.subplots(figsize=(12, 6))

    for fuel_tech, label, color in techs:
        if fuel_tech not in series:
            continue
        years, values = series[fuel_tech]
        scaled = [v / divisor for v in values]
        ax.plot(years, scaled, label=label, color=color, linewidth=2)

    release_display = release.replace("_", " ").title()
    scenario_display = scenario.replace("_", " ").title()
    ax.set_title(
        f"{release_display} - {scenario_display} - {region_label} {type_label} ({cdp})",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{type_label} ({unit})")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_color("lightgrey")
    ax.spines["bottom"].set_color("lightgrey")
    ax.tick_params(colors="grey")
    ax.axhline(0, color="grey", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate ISP verification charts")
    parser.add_argument("--release", default="2026_ISP_draft", help="Release ID")
    parser.add_argument("--scenario", default="step_change", help="Scenario name (snake_case)")
    parser.add_argument("--cdp", default="CDP1", help="Candidate Development Path")
    parser.add_argument(
        "--json-dir",
        default=None,
        help="Directory containing scenario JSON files (default: ../output/releases/<release>)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for charts (default: <release>/<scenario>/)",
    )
    args = parser.parse_args()

    # resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = args.json_dir or os.path.join(
        script_dir, "..", "output", "releases", args.release
    )
    output_dir = args.output_dir or os.path.join(script_dir, args.release, args.scenario)

    json_path = os.path.join(json_dir, f"{args.scenario}.json")
    if not os.path.exists(json_path):
        print(f"ERROR: JSON file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {json_path}")
    data = load_json(json_path)

    os.makedirs(output_dir, exist_ok=True)

    for region in REGIONS:
        for series_type in ["energy", "capacity"]:
            region_slug = REGION_LABELS[region].lower()
            filename = f"{region_slug}_{series_type}.png"
            output_path = os.path.join(output_dir, filename)
            create_chart(
                data, series_type, region, args.cdp, args.release, args.scenario, output_path
            )

    print(f"\nDone. Charts written to {output_dir}/")


if __name__ == "__main__":
    main()
