# Claim: quick-kayinleong-014
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: done
- summary: fix bq CLI not found in rca_copilot_agent when launched via VS Code MCP (PATH stripped)

## What will change
- `rca_copilot_agent/tools/bigquery_tool.py`: add `_find_bq()` with fallback paths (mirrors `_find_gcloud()` pattern from gcloud_tool.py), update `_bq_cli_available()` and `_bq_cli_execute()` to use it

## What has changed
- Added `_find_bq()` to `rca_copilot_agent/tools/bigquery_tool.py` — mirrors `_find_gcloud()` from `gcloud_tool.py`. Tries `shutil.which("bq")` first, then probes `~/Documents/google-cloud-sdk/bin/bq`, `~/google-cloud-sdk/bin/bq`, Homebrew paths, and `/snap/bin/bq`.
- Updated `_bq_cli_available()` and `_bq_cli_execute()` to call `_find_bq()` instead of hard-coded `"bq"`.
- Added `os` and `shutil` imports.

## Verification
- Regression surface: only `_bq_cli_available()` and `_bq_cli_execute()` are changed; all BQ safety layers (blocklist, dry-run, byte cap, row limit, timeout) are untouched.
- If `bq` is on PATH, `shutil.which("bq")` returns it immediately — behaviour identical to before.
- If `bq` is not on PATH (VS Code stripped PATH), the fallback list finds the SDK binary at the well-known location. The same approach was validated in quick-kayinleong-013 for gcloud.
- No new dependencies introduced (os and shutil are stdlib).
