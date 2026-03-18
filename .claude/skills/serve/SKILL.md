---
name: serve
description: Start the local dev server for the ISP chart viewer
allowed-tools: Bash
---

Start the local development server.

First, check that `output/releases/` contains at least one subdirectory. If it doesn't, stop and tell the user to run `/pipeline` first — the ISP parser hasn't been run yet.

If output exists, start the server:

```bash
python3 src/serve.py
```
