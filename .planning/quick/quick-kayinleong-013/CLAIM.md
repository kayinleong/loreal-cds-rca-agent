# Claim: quick-kayinleong-013
- owner: kayinleong
- session: claude-code
- branch: feature/rca-agent
- started: 2026-05-06
- status: done
- summary: Fix gcloud CLI not found in VS Code MCP server due to PATH not inheriting shell gcloud SDK location

## What changed
- `rca_copilot_agent/tools/gcloud_tool.py`: added `_find_gcloud()` helper that uses `shutil.which("gcloud")` first, then falls back to a list of well-known SDK install paths (`~/Documents/google-cloud-sdk`, `~/google-cloud-sdk`, Homebrew, snap). All subprocess calls now use `_find_gcloud()` instead of bare `"gcloud"`.

## Why
VS Code spawns MCP server child processes with a stripped PATH that omits shell-customised directories. The Google Cloud SDK at `~/Documents/google-cloud-sdk/bin/` was not on that PATH, causing `FileNotFoundError` and the `[GCLOUD] gcloud CLI not found` warning on every MCP server start.

## Verification
- `gcloud` is at `/Users/ka.yin.leong/Documents/google-cloud-sdk/bin/gcloud` (confirmed via `which gcloud` in terminal).
- The fallback path `~/Documents/google-cloud-sdk/bin/gcloud` is in `_GCLOUD_FALLBACK_PATHS` and will be resolved by `_find_gcloud()` when PATH lookup fails.
- Regression surface: only `gcloud_tool.py` subprocess invocations. All existing auth logic unchanged — only the binary path resolution changes from bare `"gcloud"` to the resolved absolute path.
