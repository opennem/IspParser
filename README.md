![logo](https://openelectricity.org.au/img/logo.svg)

<a href="https://opennem.github.io/IspParser/#compare=true"><img src="docs/emissions-comparison.png" alt="Emissions Comparison" width="500"></a>
<!-- Regenerate this image with: python scripts/generate_emissions_screenshot.py
     (requires the built site/ plus `pip install playwright && playwright install chromium`) -->

**[View verification charts on GitHub Pages](https://opennem.github.io/IspParser/)**

# ISP Workbook Parser

A Python script for generating JSON representations from AEMO's ISP Outlook (Excel) Workbooks.

## Usage

```bash
python src/ispparser.py
python src/ispparser.py --use-cache     # skip reprocessing if cached parquet files exist
python src/ispparser.py --input /path/to/input --output /path/to/output
python src/ispparser.py --config /path/to/report_config.json
```

| Flag | Default | Description |
|---|---|---|
| `--use-cache` | off | Skip reprocessing if cached parquet files exist |
| `--input` | `input/` | Input folder containing ISP workbooks |
| `--output` | `output/` | Output folder for generated files |
| `--config` | `src/report_config.json` | Path to report config JSON |
| `--max-to-process` | no limit | Max scenario workbooks to process per release |
| `--no-concurrency` | off | Disable parallel processing, run workbooks sequentially |
| `--unified` | off | Generate a unified long-format parquet file combining all releases |

## Output Files

Each scenario in a release is output as a JSON file in the `output` folder corresponding to the release. The scenario file includes the capacity, energy, emissions and cost data for each development pathway, and each region (where available) and an `_all` region, being the sum of all regions.

For example, the `step_change` scenario from the `2024 final ISP` release will be generated to `output/releases/2024_ISP_final/step_change.json`.

### Unified Parquet

When `--unified` is passed, the parser also generates `output/all_isps.parquet` — a single long-format file combining all releases. This is published to GitHub Pages at [`all_isps.parquet`](https://opennem.github.io/IspParser/all_isps.parquet).

| Column | Type | Description |
|---|---|---|
| Release | string | ISP publication ID (e.g. `2024_ISP_final`) |
| Scenario | string | Scenario name (e.g. `step_change`) |
| Type | string | `energy`, `capacity`, `emissions`, or `cost` |
| CDP | string | Development pathway (e.g. `CDP1`, `default`) |
| Region | string | `_all`, `nsw1`, `qld1`, `vic1`, `sa1`, `tas1` |
| Technology | string | Normalised fuel tech or cost category |
| Year | int16 | Projection year |
| Value | float32 | Projection value |
| Units | string | `GWh`, `MW`, `ktCO2e`, or `$000s` |

## Supported ISP Releases

| Release | Format | Year range | Scenarios | Download |
|---|---|---|---|---|
| 2018 ISP | 2018 | Calendar years | Neutral, Neutral with Storage, Fast, High DER, IRFG, Slow | [2018_ISP.zip](site/2018_ISP.zip) |
| 2020 ISP Draft | 2020 | Calendar years | Central, Fast, High DER, Slow, Step | [2020_ISP_draft.zip](site/2020_ISP_draft.zip) |
| 2020 ISP Final | 2020 | Calendar years | Central, Step Change, Slow Change (×8 DPs each) | [2020_ISP_final.zip](site/2020_ISP_final.zip) |
| 2022 ISP Draft | standard | 2024–2051 (calendar) | Step Change, Hydrogen Superpower, Progressive Change, Slow Change | [2022_ISP_draft.zip](site/2022_ISP_draft.zip) |
| 2022 ISP Final | standard | 2024–2051 (calendar) | Step Change, Hydrogen Superpower, Progressive Change, Slow Change | [2022_ISP_final.zip](site/2022_ISP_final.zip) |
| 2024 ISP Draft | standard | 2025–2052 (calendar) | Step Change, Progressive Change, Green Energy Exports | [2024_ISP_draft.zip](site/2024_ISP_draft.zip) |
| 2024 ISP Final | standard | 2024-25–2051-52 (financial) | Step Change, Green Energy Exports, Progressive Change | [2024_ISP_final.zip](site/2024_ISP_final.zip) |
| 2026 ISP Draft | standard | 2026-27–2049-50 (financial) | Step Change, Accelerated Transition, Slower Growth | [2026_ISP_draft.zip](site/2026_ISP_draft.zip) |
| 2026 ISP Final | standard | 2026-27–2049-50 (financial) | Step Change, Accelerated Transition, Slower Growth + 6 Step Change sensitivities | [2026_ISP_final.zip](site/2026_ISP_final.zip) |

### Release notes

- **2018 ISP** — First ISP. Single cost category (generation investment). No emissions data.
- **2020 ISP Draft** — Introduces 8 cost categories (VOM, FOM, fuel, build, rehab, DSP+USE, REZ/IC transmission). Adds pumped hydro and VPP battery types.
- **2020 ISP Final** — 3 scenarios × 8 development pathways = 24 workbooks.
- **2022 ISP Draft / Final** — Calendar years 2024–2051. Adds offshore wind, hydrogen turbines, solar thermal, gas with CCS. Capacity includes "Existing and Committed" column. Emissions for NEM only (mapped to `_all`).
- **2024 ISP Draft** — Calendar years 2025–2052. CDP names normalised (`CDP11 (ODP)` → `CDP11`, `Least-cost DP` rows dropped).
- **2024 ISP Final** — First release using financial years. Introduces subregions (collapsed during processing) and per-region emissions. Adds emissions cost category.
- **2026 ISP Draft** — Financial years 2026-27 to 2049-50. Renamed technology labels (e.g. `Rooftop and other small-scale solar`). 14 cost categories including retirement, distribution, system security. 24 CDPs including Counterfactual.
- **2026 ISP Final** — Same workbook structure as the 2026 Draft. Adds 6 Step Change sensitivity scenarios (Constrained Delivery, Higher/Lower Energy Efficiency, Higher Demand, No Further CER Coordination, No Further VPP Uptake). 35 CDPs in the Core scenarios including Counterfactual (up from 24 in the draft).

## Interactive Charts

An interactive chart viewer comparing generation, capacity, emissions, and costs across all ISP releases is published via [GitHub Pages](https://opennem.github.io/IspParser/).

## Contact

 - File an issue or contact the author on Twitter at [@simonahac](https://twitter.com/simonahac)
