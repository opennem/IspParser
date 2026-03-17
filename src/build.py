#!/usr/bin/env python3
"""
Build ISP reference output: verification charts, zip archives, and index pages.

Usage:
    python build.py all                     # everything
    python build.py release 2026_ISP_draft  # single release charts
    python build.py compare                 # cross-release comparison charts
    python serve.py                          # local HTTP server for testing
"""

import argparse
import json
import os
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION_LABELS = {
    "_all": "NEM",
    "nsw1": "NSW",
    "qld1": "QLD",
    "sa1": "SA",
    "tas1": "TAS",
    "vic1": "VIC",
}
REGIONS = list(REGION_LABELS.keys())

DETAIL_TECHS = {
    "energy": [
        ("coal_black",          "Black coal",          "#251C00"),
        ("coal_brown",          "Brown coal",          "#675B42"),
        ("gas_ccgt",            "Mid-merit gas",       "#ED9C2C"),
        ("gas_ocgt",            "Flexible gas",        "#F0AC4A"),
        ("gas_ccgt_ccs",        "Gas with CCS",        "#F1AB4B"),
        ("hydro",               "Hydro",               "#ACE9FE"),
        ("wind",                "Wind",                "#246D36"),
        ("wind_offshore",       "Offshore wind",       "#53AD69"),
        ("solar_utility",       "Utility-scale solar", "#FECE00"),
        ("solar_rooftop",       "Rooftop solar",       "#FFEB5C"),
        ("bioenergy",           "Bioenergy",           "#069FAF"),
        ("battery_discharging", "Battery",             "#3145CE"),
    ],
    "capacity": [
        ("coal_black",    "Black coal",          "#251C00"),
        ("coal_brown",    "Brown coal",          "#675B42"),
        ("gas_ccgt",      "Mid-merit gas",       "#ED9C2C"),
        ("gas_ocgt",      "Flexible gas",        "#F0AC4A"),
        ("gas_ccgt_ccs",  "Gas with CCS",        "#F1AB4B"),
        ("hydro",         "Hydro",               "#ACE9FE"),
        ("wind",          "Wind",                "#246D36"),
        ("wind_offshore", "Offshore wind",       "#53AD69"),
        ("solar_utility", "Utility-scale solar", "#FECE00"),
        ("solar_rooftop", "Rooftop solar",       "#FFEB5C"),
        ("bioenergy",     "Bioenergy",           "#069FAF"),
        ("battery",       "Battery",             "#3145CE"),
    ],
}

COMPARE_GROUPS = {
    "energy": {
        "Coal":    ["coal_black", "coal_brown"],
        "Gas":     ["gas_ccgt", "gas_ocgt", "gas_ccgt_ccs", "gas_hydrogen"],
        "Wind":    ["wind", "wind_offshore"],
        "Solar":   ["solar_utility", "solar_rooftop", "solar_thermal"],
        "Battery": ["battery_discharging", "battery_distributed_discharging", "battery_VPP_discharging"],
        "Hydro":   ["hydro"],
    },
    "capacity": {
        "Coal":    ["coal_black", "coal_brown"],
        "Gas":     ["gas_ccgt", "gas_ocgt", "gas_ccgt_ccs", "gas_hydrogen"],
        "Wind":    ["wind", "wind_offshore"],
        "Solar":   ["solar_utility", "solar_rooftop", "solar_thermal"],
        "Battery": ["battery", "battery_distributed", "battery_VPP"],
        "Hydro":   ["hydro"],
    },
}

COMPARE_COLORS = {
    "Coal":    "#251C00",
    "Gas":     "#ED9C2C",
    "Wind":    "#246D36",
    "Solar":   "#FECE00",
    "Battery": "#3145CE",
    "Hydro":   "#41B6E6",
}

RELEASES = [
    {"id": "2022_ISP_final", "label": "2022 ISP",       "cdp": "CDP2",  "odp": "CDP12",        "linestyle": "dotted"},
    {"id": "2024_ISP_final", "label": "2024 ISP",       "cdp": "CDP1",  "odp": "CDP14",        "linestyle": "dashed"},
    {"id": "2026_ISP_draft", "label": "2026 ISP Draft", "cdp": "CDP1",  "odp": "CDP4 (ODP)",   "linestyle": "solid"},
]

TYPE_LABELS = {"energy": "Generation", "capacity": "Capacity"}
TYPE_UNITS = {"energy": "TWh", "capacity": "GW"}
TYPE_DIVISOR = {"energy": 1000, "capacity": 1000}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path) as f:
        return json.load(f)


def find_odp(data):
    """Find the ODP pathway name if tagged in the data, else None."""
    pathways = set(d["pathway"] for d in data["data"])
    for p in pathways:
        if "ODP" in p:
            return p
    return None


def extract_series(data, series_type, region, cdp):
    results = {}
    for entry in data["data"]:
        if entry["type"] != series_type or entry["region"] != region or entry["pathway"] != cdp:
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


def extract_emissions(data, region, cdp):
    for entry in data["data"]:
        if entry["type"] != "emissions" or entry["region"] != region or entry["pathway"] != cdp:
            continue
        if entry.get("fuel_tech") is not None:
            continue
        proj = entry["projection"]
        start_year = int(proj["start"][:4])
        values = proj["data"]
        years = list(range(start_year, start_year + len(values)))
        return years, values
    return None, None


def sum_group(series, fuel_techs):
    combined_years = None
    combined_values = None
    for ft in fuel_techs:
        if ft not in series:
            continue
        years, values = series[ft]
        if combined_years is None:
            combined_years = list(years)
            combined_values = list(values)
        else:
            for i, y in enumerate(years):
                if y in combined_years:
                    idx = combined_years.index(y)
                    combined_values[idx] += values[i]
    return combined_years, combined_values


def style_axes(ax):
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_color("lightgrey")
    ax.spines["bottom"].set_color("lightgrey")
    ax.tick_params(colors="grey")


# ---------------------------------------------------------------------------
# Per-release detail charts
# ---------------------------------------------------------------------------

def create_detail_chart(data, series_type, region, cdp, release, scenario, output_path):
    series = extract_series(data, series_type, region, cdp)
    techs = DETAIL_TECHS[series_type]
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

    release_display = release.replace("_", " ").title().replace("Isp", "ISP")
    scenario_display = scenario.replace("_", " ").title()
    ax.set_title(
        f"{release_display} — {scenario_display} — {region_label} {type_label} ({cdp})",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{type_label} ({unit})")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    style_axes(ax)
    ax.axhline(0, color="grey", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path}")


def generate_release_charts(release_id, scenario, cdp, json_dir, output_dir):
    json_path = os.path.join(json_dir, f"{scenario}.json")
    if not os.path.exists(json_path):
        print(f"  SKIP {json_path} (not found)")
        return None

    data = load_json(json_path)
    out = os.path.join(output_dir, release_id, scenario)
    os.makedirs(out, exist_ok=True)

    for region in REGIONS:
        for series_type in ["energy", "capacity"]:
            slug = REGION_LABELS[region].lower()
            path = os.path.join(out, f"{slug}_{series_type}.png")
            create_detail_chart(data, series_type, region, cdp, release_id, scenario, path)

    return data


# ---------------------------------------------------------------------------
# Cross-release comparison charts
# ---------------------------------------------------------------------------

def create_comparison_chart(all_data, group_name, fuel_techs, series_type, output_path):
    divisor = TYPE_DIVISOR[series_type]
    unit = TYPE_UNITS[series_type]
    type_label = TYPE_LABELS[series_type]
    color = COMPARE_COLORS[group_name]

    fig, ax = plt.subplots(figsize=(10, 5))
    has_data = False

    for rel in RELEASES:
        data = all_data.get(rel["id"])
        if data is None:
            continue
        series = extract_series(data, series_type, "_all", rel["cdp"])
        years, values = sum_group(series, fuel_techs)
        if years is None:
            continue
        scaled = [v / divisor for v in values]
        ax.plot(years, scaled, label=rel["label"], color=color,
                linestyle=rel["linestyle"], linewidth=2.5)
        has_data = True

    if not has_data:
        plt.close(fig)
        return

    ax.set_title(f"NEM {group_name} {type_label}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel(f"{type_label} ({unit})")
    ax.legend(frameon=False)
    style_axes(ax)
    ax.axhline(0, color="grey", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path}")


def create_emissions_chart(all_data, output_path):
    fig, ax = plt.subplots(figsize=(14, 5))

    for rel in RELEASES:
        data = all_data.get(rel["id"])
        if data is None:
            continue
        years, values = extract_emissions(data, "_all", rel["cdp"])
        if years is None:
            continue
        scaled = [v / 1000 for v in values]
        ax.plot(years, scaled, label=rel["label"], color="black",
                linestyle=rel["linestyle"], linewidth=2.5)

    ax.set_title("NEM Emissions — Step Change", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Emissions (MtCO₂e)")
    ax.legend(frameon=False)
    style_axes(ax)
    ax.axhline(0, color="grey", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {output_path}")


def generate_comparison_charts(json_base, output_dir):
    all_data = {}
    for rel in RELEASES:
        path = os.path.join(json_base, rel["id"], "step_change.json")
        if os.path.exists(path):
            all_data[rel["id"]] = load_json(path)
            print(f"  loaded {path}")

    os.makedirs(output_dir, exist_ok=True)

    group_order = ["Coal", "Gas", "Wind", "Solar", "Battery", "Hydro"]
    for series_type in ["energy", "capacity"]:
        for group_name in group_order:
            fuel_techs = COMPARE_GROUPS[series_type][group_name]
            slug = group_name.lower()
            path = os.path.join(output_dir, f"{slug}_{series_type}.png")
            create_comparison_chart(all_data, group_name, fuel_techs, series_type, path)

    create_emissions_chart(all_data, os.path.join(output_dir, "emissions.png"))


# ---------------------------------------------------------------------------
# GitHub Pages generation
# ---------------------------------------------------------------------------

def generate_release_page(release_id, scenarios, cdp, odp, output_dir):
    """Generate index.md for a release."""
    release_display = release_id.replace("_", " ").replace("ISP", "ISP").title().replace("Isp", "ISP")
    lines = [
        "---",
        f"title: {release_display}",
        "---",
        "",
        f"# {release_display}",
        "",
        f"Optimal Development Path: **{odp}**",
        "",
        f"Charts below show **{cdp}** projections.",
        "",
        "[← Back to overview](../)",
        "",
    ]

    for scenario in scenarios:
        scenario_display = scenario.replace("_", " ").title()
        lines.append(f"## {scenario_display}")
        lines.append("")

        for region in REGIONS:
            slug = REGION_LABELS[region].lower()
            region_label = REGION_LABELS[region]
            rel = f"{scenario}/{slug}"
            lines.append(f"### {region_label}")
            lines.append("")
            lines.append("| Generation | Capacity |")
            lines.append("|:---:|:---:|")
            lines.append(f"| ![]({rel}_energy.png) | ![]({rel}_capacity.png) |")
            lines.append("")

    md_path = os.path.join(output_dir, release_id, "index.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  {md_path}")


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


def generate_top_level_page(output_dir):
    """Generate the top-level index.md with comparison charts."""
    lines = [
        "---",
        "title: ISP Workbook Parser — Reference Output",
        "---",
        "",
        "# ISP Workbook Parser — Reference Output",
        "",
        "Cross-release comparison of **Step Change** scenario (NEM-wide, CDP1/CDP2).",
        "",
        "Line styles: **solid** = 2026 ISP Draft, **dashed** = 2024 ISP, **dotted** = 2022 ISP.",
        "",
    ]

    group_order = ["Coal", "Gas", "Wind", "Solar", "Battery", "Hydro"]
    for group in group_order:
        slug = group.lower()
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| Generation | Capacity |")
        lines.append("|:---:|:---:|")
        lines.append(f"| ![](comparison/{slug}_energy.png) | ![](comparison/{slug}_capacity.png) |")
        lines.append("")

    lines.append("## Emissions")
    lines.append("")
    lines.append("![](comparison/emissions.png)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Per-release detail charts")
    lines.append("")

    for rel in RELEASES:
        lines.append(f"- [{rel['label']}]({rel['id']}/)")

    lines.append("")
    lines.append("## Downloads")
    lines.append("")
    for zf in sorted(os.listdir(output_dir)):
        if zf.endswith(".zip"):
            label = zf.replace(".zip", "").replace("_", " ").replace("ISP", "ISP")
            lines.append(f"- [{label} (JSON)]({zf})")
    lines.append("")

    md_path = os.path.join(output_dir, "index.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate ISP verification charts")
    sub = parser.add_subparsers(dest="command")

    rel_parser = sub.add_parser("release", help="Generate per-release detail charts")
    rel_parser.add_argument("release_id")
    rel_parser.add_argument("--scenario", default=None)
    rel_parser.add_argument("--cdp", default=None)

    sub.add_parser("compare", help="Generate cross-release comparison charts")
    sub.add_parser("all", help="Generate everything")

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_base = os.path.join(script_dir, "..", "output", "releases")
    output_base = os.path.join(script_dir, "..", "site")

    if args.command == "release":
        rel = args.release_id
        json_dir = os.path.join(json_base, rel)
        # find matching release info
        rel_info = next((r for r in RELEASES if r["id"] == rel), None)
        cdp = args.cdp or (rel_info["cdp"] if rel_info else ("CDP2" if "2022" in rel else "CDP1"))
        odp = rel_info["odp"] if rel_info else "unknown"

        if args.scenario:
            scenarios = [args.scenario]
        else:
            scenarios = [f.replace(".json", "") for f in sorted(os.listdir(json_dir)) if f.endswith(".json")]

        print(f"Generating charts for {rel}")
        for scenario in scenarios:
            print(f"  scenario: {scenario}")
            generate_release_charts(rel, scenario, cdp, json_dir, output_base)

        generate_release_page(rel, scenarios, cdp, odp, output_base)

    elif args.command == "compare":
        print("Generating comparison charts")
        generate_comparison_charts(json_base, os.path.join(output_base, "comparison"))
        generate_top_level_page(output_base)

    elif args.command == "all":
        for rel_info in RELEASES:
            rel = rel_info["id"]
            cdp = rel_info["cdp"]
            odp = rel_info["odp"]
            json_dir = os.path.join(json_base, rel)
            if not os.path.isdir(json_dir):
                print(f"SKIP {rel} (no JSON dir)")
                continue
            scenarios = [f.replace(".json", "") for f in sorted(os.listdir(json_dir)) if f.endswith(".json")]
            print(f"Generating charts for {rel}")
            for scenario in scenarios:
                print(f"  scenario: {scenario}")
                generate_release_charts(rel, scenario, cdp, json_dir, output_base)
            generate_release_page(rel, scenarios, cdp, odp, output_base)

        print("Generating comparison charts")
        generate_comparison_charts(json_base, os.path.join(output_base, "comparison"))

        print("Creating zip files")
        create_release_zips(output_base)

        generate_top_level_page(output_base)
        print("\nDone.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
