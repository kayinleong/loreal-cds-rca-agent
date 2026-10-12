---
status: complete
---
## Goal
Replace the pip-freeze root requirements.txt with per-agent direct-dependency files and add an offline coverage test.
## Changes Made
- `requirements.txt` (4 `-r` lines), `requirements-mcp.txt` (`mcp>=1.2,<2`)
- `rca_copilot_agent/requirements.txt`, `ticketasg_copilot_agent/requirements.txt` (requests, urllib3, python-dotenv, playwright)
- `ticketasg_copilot_agent/requirements-retrieval.txt` (sentence-transformers, numpy), `mockdata_copilot_agent/requirements.txt` (openpyxl)
- `scripts/tests/test_requirements_coverage.py` (5 tests)
## Verification
uv venv py3.12: all files resolve with --only-binary (requests 2.34.2, urllib3 2.8.0, python-dotenv 1.2.4, playwright 1.63.0, sentence-transformers 5.7.0, torch 2.14.1, numpy 2.5.4, openpyxl 3.1.5, mcp 1.30.0). pip --dry-run --platform win_amd64 --python-version 3.12: rc=0 for all files (negative control rc=1). Tests: 5 OK; injected `import yaml` in scratch copy fails with file:line message.
## Regression
All must-keep packages (requests, urllib3, dotenv, playwright for rca+ticketasg; sentence-transformers+numpy; openpyxl; mcp<2) are declared. No source files touched.
## Blockers
None.
