---
name: pipeline
description: Run the ISP parser pipeline to process Excel workbooks into JSON output
allowed-tools: Bash
---

Run the full ISP parser pipeline:

```bash
python3 src/ispparser.py $ARGUMENTS
```

This parses Excel workbooks from `input/` and writes JSON to `output/releases/`.

Common flags to pass through:
- `--use-cache` — skip re-processing workbooks, use cached parquet files
- `--max-to-process N` — only process N scenario workbooks per release
