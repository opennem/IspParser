# ISP Parser

Parses AEMO's ISP Excel workbooks into JSON and publishes an interactive chart site to GitHub Pages.

## What is the ISP?

The **Integrated System Plan (ISP)** is a roadmap published by **AEMO** (Australian Energy Market Operator) that forecasts the cheapest way to supply reliable electricity to the National Electricity Market (NEM) over the next 20–30 years. AEMO publishes draft and final ISP reports every two years, each containing multiple scenarios (e.g. "Step Change", "Progressive Change") and development pathways (CDPs). The workbooks contain projections for generation, capacity, emissions, and costs broken down by technology, region, and pathway.

## Australian energy landscape — what to expect in the data

The broad trend in Australian energy is a transition from fossil fuels to renewables, with storage filling the gaps. When reviewing output data, these patterns are normal:

- **Coal declining** — Both brown and black coal capacity/generation should trend down over time, reaching zero in most scenarios by the 2040s–2050s.
- **Solar and wind growing rapidly** — Rooftop solar, utility solar, and wind (onshore and offshore) should show strong growth across all scenarios.
- **Storage expanding** — Battery (utility and distributed) and pumped hydro capacity should grow substantially to firm up variable renewables.
- **Gas as transition fuel** — Gas generation may hold steady or decline slowly; some scenarios show gas peaking capacity persisting longer.
- **Emissions falling** — Total NEM emissions should decline roughly in line with coal retirement.
- **Interconnectors and transmission** — Imports/exports between regions grow as the grid becomes more interconnected.

Anomalies worth flagging: coal or emissions *increasing* over time, negative capacity values, renewables declining, or any scenario where total generation doesn't roughly track demand growth.

## How it works

1. **Parse** — `src/ispparser.py` reads Excel workbooks from `input/{release_id}/`, normalises technology/region names using mappings in `src/report_config.json`, runs integrity checks, and writes JSON to `output/releases/{release_id}/`.
2. **Deploy** — On push to `master`, GitHub Actions (`.github/workflows/deploy-pages.yml`) runs the parser, copies `pages-template/` (interactive Chart.js frontend) and JSON output into `site/`, and deploys to GitHub Pages.

## Speeding up development runs

Processing Excel workbooks is very slow. `src/ispparser.py` has flags to speed things up, but be aware they can give a false picture if the cache is stale:

- `--use-cache` — Skip re-processing workbooks and use cached `.parquet` files from a previous run. Fast, but you'll miss any changes to input files or parsing logic.
- `--max-to-process N` — Only process the first N scenario workbooks per release. Useful for quick smoke tests, but the output will be incomplete.
