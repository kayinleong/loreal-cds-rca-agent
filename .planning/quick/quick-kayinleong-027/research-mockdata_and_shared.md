---
status: complete
package: mockdata_copilot_agent + shared
claim: quick-kayinleong-027
researched: 2026-10-12
method: read-only static analysis (Read / grep / diff / md5 / python3 -I JSON parse). No code run against SNOW, BQ, gcloud, SMTP or an LLM.
---

## Part A — mockdata_copilot_agent

What it is: a generator that writes BigQuery GoogleSQL `INSERT` text for mock `external_system_ids` rows, plus synthetic `consumer_pii` rows when needed, aimed at the DV dataset `oa-apmena-spacecds-ap-dv.space_cds_b2c_ds_replica_ase1_dv_public`. It only shows the SQL; it never runs a write. There are 5 tools, with the same dispatch shared by MCP and the CLI (`run_tool.py` → `mcp_server._dispatch`). It has no ServiceNow, ticket, email or RCA features.

### Flow table

| Step | Status | How it works today | Key code (file:line) | Gaps & risks |
|---|---|---|---|---|
| 1a SNOW auth | N/A | No ServiceNow access. No COOKIE/X_USERTOKEN, no `auth_tool.py` | mcp_server.py:35, config.py:4 | — |
| 1b GCP auth | Implemented (lazy) | `ensure_login`, and also checked lazily before `fetch_seed`/`lookup_consumer`, calls `ensure_gcloud_auth("loreal.com")`. That runs a user-creds check (bq CLI) and an ADC check (python client), and starts an interactive login if either fails. No auth at server start | mcp_server.py:241-248, 250-256, 281-286, 450-456; run_tool.py:83-89; tools/gcloud_tool.py:183-236 | (a) Failures are only logged. `ensure_login` always returns `"adc": "checked"` (mcp_server.py:246). (b) After `gcloud auth login`, the new account is **not** re-checked against `@loreal.com` (gcloud_tool.py:217-222). (c) `set_project` / `set_quota_project` fall back to the **PD** project (gcloud_tool.py:141, 169). This is masked only because `BQ_PROJECT` is set to DV with `setdefault` first (mcp_server.py:442, run_tool.py:69). (d) The interactive login can block a stdio MCP session for up to 600 s (gcloud_tool.py:71) |
| 2 Read tickets | N/A | Not in scope. Input is a seed row instead: user-pasted JSON, or `fetch_seed` (a live read-only SELECT), or `parse_seed_xlsx` as a fallback | tools/mockdata_tool.py:435-472, 500-518 | `parse_seed_xlsx` needs `openpyxl`, which is **not** in requirements.txt (lazy import, fails cleanly) |
| 3 Access BQ | Implemented (read-only) | `fetch_seed`: a whitelisted-filter SELECT of the 18 DV columns, LIMIT clamped to 1-25. `lookup_consumer`: an existence SELECT on lucid (+consumerkey/signature/isocountry). Both go through `validate_query`, then the bq CLI. The DV executor is chosen from the backtick project in the SQL | mcp_server.py:258-266, 288-292; tools/mockdata_tool.py:432-497; tools/bigquery_tool.py:455-468, 492-541, 557-576 | (a) **No dry-run and no `maximum_bytes_billed` on this path.** `query_bigquery` and `query_bigquery_rows` call the bq CLI straight after the keyword check (bigquery_tool.py:544-554, 557-576). (b) The `exists` check works by string-matching the output (mcp_server.py:269-274). A *failed* query (`QUERY FAILED`) comes back as `exists: false`, so the agent can generate synthetic `consumer_pii` for a consumer whose existence was never confirmed, which risks duplicate inserts. It also gives a false negative if any returned value contains "error". (c) `fetch_seed` sends real DV identifiers (lucid, sourceconsumerid) into LLM context and into the report |
| 4 Output | Implemented (offline) | `generate_mockdata` builds type-driven literals from `.docs/dv_columns.json` (18 + 32 cols). The PK counter is always bumped. Seed columns missing from live BQ are dropped and listed in a `-- Dropped…` comment. `save_mockdata_report` writes `mockdata/<MMDDYYNN>.md` without overwriting existing files | mcp_server.py:305-321, 330-375; tools/mockdata_tool.py:175-212, 329-427 | Docstrings still say "4 tools" (mcp_server.py:6, 235) but there are 5. The DV project/dataset is hardcoded in the tool (mockdata_tool.py:51-52). `cfg.bq_dataset` is loaded but **never used** (config.py:68). `mockdata/` is gitignored (.gitignore:206) |

### Tool inventory

| Tool | Purpose | file:line |
|---|---|---|
| `ensure_login` | gcloud user creds + ADC check, `@loreal.com` | mcp_server.py:241-248 |
| `fetch_seed` | Read-only live seed row(s) from DV `external_system_ids` | mcp_server.py:280-303 → mockdata_tool.py:435 |
| `lookup_consumer` | Read-only `consumer_pii` existence check on lucid | mcp_server.py:250-278 → mockdata_tool.py:475 |
| `generate_mockdata` | Clone seed into N rows (`vary`: list cycle or `"increment"`); optional `consumer_pii` for `absent_lucids` | mcp_server.py:305-321 → mockdata_tool.py:329, 380 |
| `save_mockdata_report` | Write the report .md with the SQL and a "run manually" reminder | mcp_server.py:323-375 |
| Client wiring | Copilot agent `.github/agents/mockdata_copilot.agent.md` (run_in_terminal only); Claude skill `.claude/skills/mockdata-copilot/SKILL.md` (Bash only). **Not** registered in `.vscode/mcp.json` | — |

`.docs/`: `dv_columns.json` (live INFORMATION_SCHEMA snapshot, `confirmed: true`, tables `external_system_ids`=18 cols, `consumer_pii`=32 cols), `external_system_ids mock up.sql` (Postgres sample, reference only), `external_system_ids.xlsx` (skipped).

## Part B — Shared infrastructure

### Duplicated modules

| Module | Packages | Identical? | Key divergences | Most complete copy |
|---|---|---|---|---|
| `tools/gcloud_tool.py` (236 L) | rca_copilot, ticketasg, mockdata | **Yes** (md5 `f1434dea…` ×3) | — | any. Hardcoded PD fallback at :141, :169 in all three |
| `tools/auth_tool.py` (220 L) | rca_copilot, ticketasg | **Yes** (md5 `cd192018…` ×2) | — | either. Cookie filter hardcodes `"loreal.service-now.com"` (:116) and ignores the `instance_url` argument |
| `tools/bigquery_tool.py` | all 4 | **No** — 4 different md5s | **rca_agent** (291 L): google-cloud-bigquery python client. `execute()` actually runs keyword check → **dry-run** → bytes check → `maximum_bytes_billed` → timeout/row cap (rca_agent/tools/bigquery_tool.py:129-175). Caps come from config (`init_executor`, :248-252; rca_agent/config.py:70-72). Schema comes from live BQ (`lookup_schema`, :273-291). **rca_copilot / ticketasg** (559 L): differ only in a comment (:71). Schema comes from schema.json. One executor per project with routing by SQL project (:423-468). Queries run through the **bq CLI subprocess** (:492-541, 60 s timeout, `--max_rows`). `query_bigquery` (:544-554) does keyword check → CLI only, so **dry-run, bytes cap and `execute()` are dead code** on this path. Caps are hardcoded at :446-451. **mockdata** (581 L) = the ticketasg copy (comment at :71 still says ticketasg) plus `query_bigquery_rows` (:557-576), which has the same unsafe-cost path | Feature superset: **mockdata**. The only copy that **enforces** the cost guardrails CLAUDE.md requires: **rca_agent** |
| `tools/snow_reader.py` (709 L) | rca_copilot, ticketasg | Docstring only (line 4) | Both are trimmed extracts of `rca_agent/snow_story_reader.py` (1224 L, 1317 diff lines). The copilot copy adds `fetch_incidents_from_list` and drops the CLI, `authenticate_from_env`, `_bootstrap_csrf_token` and tiny-URL public API. Retry is 3× on 429/5xx (:48-49) | rca_copilot = ticketasg |
| `tools/incident_store.py` (317 L) | rca_copilot, ticketasg | Docstring only (line 4) | Extract of `rca_agent/tools/snow_tool.py` (336 L, 341 diff lines). rca_agent's `IncidentLoader` merges **OCR** data (`_load_ocr`, snow_tool.py:40-80); the copilot `IncidentStore` has no OCR and adds `list_all` | rca_agent for OCR; copilot copies otherwise |
| `tools/email_tool.py` (161 L) | rca_copilot, ticketasg | **No** (cosmetic + 1 functional) | Wording (RCA vs Assignment). **SMTP timeout 30 s (rca_copilot) vs 120 s (ticketasg)** at :82, :88. ticketasg still names the function `send_rca_email` (:42) | ticketasg (longer timeout) |
| `config.py` | all 4 | No | rca_copilot vs ticketasg differ only by `ASSIGNMENT_RULES_FILE`. rca_agent uses `SNOW_REPORTS_DIR`/`SNOW_ATTACHMENTS_DIR`; copilot pkgs use `REPORTS_DIR`/`ATTACHMENTS_DIR`. Only rca_agent and mockdata read `BQ_*` | — |

### MCP registration (.vscode/mcp.json)
- Only **one** server is registered: `snow-mcp` → `${workspaceFolder}/.venv/bin/python -u ${workspaceFolder}/rca_copilot_agent/mcp_server.py` (mcp.json:3-6).
- env (mcp.json:7-16): `SNOW_INSTANCE`, `REPORTS_DIR`, `ATTACHMENTS_DIR`, `BQ_PROJECT`, `BQ_DATASET`, `BQ_MAX_BYTES`, `BQ_TIMEOUT`, `BQ_MAX_ROWS`. **`BQ_MAX_BYTES`, `BQ_TIMEOUT` and `BQ_MAX_ROWS` have no effect.** rca_copilot never reads them (grep: no `BQ_*` read in rca_copilot_agent besides `BQ_PROJECT` in gcloud_tool.py). `BQ_DATASET` is also unread there.
- Not registered: `rca_agent`, `ticketasg_copilot_agent`, `mockdata_copilot_agent`. The AGENTS.md files say L'Oréal blocks MCP and that `run_tool.py` is the main path.
- `.vscode/settings.json:3` sets `chat.mcp.serverSampling` for key `"space-cds-etl-core-feature-rca-agent/.vscode/mcp.json: snow-mcp"`. That **folder name does not match** the current `space-cds-etl-core`, so the setting is probably stale and has no effect [ASSUMED: VS Code keys this setting by workspace folder name].

### Config & env (names only)
- Root `.env.example`: `COOKIE`, `X_USERTOKEN`, `REPORTS_DIR`, `ATTACHMENTS_DIR`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_VERIFY_SSL`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`. Missing: `SNOW_INSTANCE`, `ASSIGNMENT_RULES_FILE`, `MOCKDATA_OUTPUT_DIR`, `BQ_PROJECT`/`BQ_DATASET` (mockdata).
- `rca_agent/.env.example`: `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY` (commented alternatives: `OPENAI_API_KEY`, `GOOGLE_API_KEY`), `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `BQ_PROJECT`, `BQ_DATASET`, `BQ_MAX_BYTES`, `BQ_TIMEOUT`, `BQ_MAX_ROWS`, `COOKIE`, `X_USERTOKEN`, `SNOW_REPORTS_DIR`, `SNOW_ATTACHMENTS_DIR`, `AGENT_MAX_ITERATIONS`, `AGENT_WIKI_DIR`, `AGENT_OUTPUT_DIR`. Code also reads `LLM_API_KEY`, `GEMINI_API_KEY` (rca_agent/config.py:41, 61).
- Defaults: SNOW `https://loreal.service-now.com` (rca_copilot/config.py:71, ticketasg/config.py:73). rca_agent's `ServiceNowConfig.instance_url` defaults to `""` with no env read (rca_agent/config.py:83). BQ PD `oa-apmena-spacecds-ap-pd` / `space_cds_b2c_ds_replica_ae2_pd_public` (rca_agent/config.py:68-69). Caps are 500 MB / 30 s / 100 rows everywhere. In copilot pkgs they are hardcoded (bigquery_tool.py:446-451) and the CLI timeout is 60 s (:511).
- **Project IDs hardcoded outside config.py: yes.** Found in `*/tools/gcloud_tool.py:141,169` (3 pkgs), `*/tools/bigquery_tool.py` (comment/regex example), `*/mcp_server.py` (rca_agent, rca_copilot, ticketasg ×1 each, mockdata ×2), and `mockdata_tool.py:51-52`. This goes against the CLAUDE.md rule "Do not hardcode the BQ project ID … outside config.py". The copilot pkgs' real source of truth is `schema.json` (`project` + `additional_datasets` keys), not config.py.

### Dependencies
- Root `requirements.txt` (54 lines): fully pinned freeze — `mcp==1.27.0`, `google-cloud-bigquery==3.41.0`, `playwright==1.59.0` (SNOW SSO), `requests==2.33.1`, `pydantic==2.13.3`, plus unpinned `sentence-transformers>=2.5.0` (ticketasg retrieval, ~250 MB torch). No `anthropic`/`openai`/`google-generativeai`, no `openpyxl`, no `pytest`.
- `rca_agent/requirements.txt`: loose ranges — `pydantic>=2.0`, `requests>=2.31`, `anthropic>=0.40.0`, **unpinned** `google-generativeai`, `google-cloud-bigquery>=3.20`, `mcp>=1.0.0`. OCR deps are commented out (`pytesseract`, `Pillow`). The two files can resolve to different versions, so there is no single lock.
- Neither file installs the gcloud SDK / `bq` CLI. Every copilot BQ query needs `bq` on PATH or in a fallback path (bigquery_tool.py:34-50).

### Tests / CI
- Only one test file: `ticketasg_copilot_agent/test_config.py` (3 pytest-style config tests, :29, :40, :52). No pytest config, no `conftest.py`, no `pyproject.toml`, and pytest is not in requirements.
- **No tests** for any `bigquery_tool`, `gcloud_tool`, `auth_tool`, `snow_reader`, `incident_store`, `email_tool` or `mockdata_tool` (even though mockdata_tool.py:347 says `column_types`/`columns` "may be injected for tests").
- **No CI**: `.github/` holds only `agents/*.agent.md`; `.github/workflows/` does not exist.

### schema.json
- Primary: `oa-apmena-spacecds-ap-pd.space_cds_b2c_ds_replica_ae2_pd_public` — **33 tables**.
- `additional_datasets` (all on `oa-apmena-spacecds-ap-dv`): b2b_ae2_dv_cds_tgt 23, b2b_ase1_dv_cds_tgt 23, b2c_ase1_dv_public 3 (`survey`, `survey_qna`, `product_hierarchy_map`), b2c_ae2_dv_public **0** (it relies on "same schema as primary").
- **82 tables in total, plus 12 `common_rca_patterns`.** Other top keys: `dialect`, `auth`, `note`, `all_datasets` (6), `key_identifiers`.
- CLAUDE.md says "45 BQ tables" and gives a regeneration command (`bq ls … > schema.json`) that **cannot** produce this hand-curated structure (purpose/relationships/patterns). Both are stale.
- The mockdata target tables (`external_system_ids`, `consumer_pii`) appear only under the PD primary tables, not under the ase1 DV entry. Routing still works because `init_from_schema` makes a DV executor from the dataset-key prefix.

## Risks & open questions
1. **The BQ cost guardrails are not enforced in 3 of 4 packages.** The copilot/mockdata `query_bigquery` and `query_bigquery_rows` skip dry-run and `maximum_bytes_billed` and go straight to the `bq` CLI. Only the regex blocklist and `--max_rows` (which limits output rows, not bytes scanned) apply. This goes against CLAUDE.md's "BigQuery Safety". Fix: add a dry-run (python client or `bq query --dry_run`) plus `--maximum_bytes_billed=<cap>` to `_bq_cli_execute` [ASSUMED: the bq CLI supports both flags; check with `bq query --help` before planning].
2. **Copy-paste drift.** gcloud and auth are identical copies, but bigquery_tool has 4 versions and email has a different timeout. A fix in one package will not reach the others. Consider a shared `common/` package. That would be a refactor, so it needs its own claim.
3. **The mockdata `lookup_consumer` existence check fails open.** A query or auth error counts as "absent", which leads to synthetic `consumer_pii` INSERTs. Return a tri-state (`exists`/`absent`/`unknown`) from structured rows (reuse `query_bigquery_rows`).
4. **The gcloud auth domain check is weak.** After an interactive login, the `@loreal.com` account is not re-verified, failures are swallowed, and the fallback project is PD even for the DV-only mockdata agent.
5. **The config surface is misleading.** mcp.json `BQ_*` values are ignored by rca_copilot. `BQ_DATASET` in mockdata is unused. Env var names differ between packages (`SNOW_REPORTS_DIR` vs `REPORTS_DIR`). The root `.env.example` lacks several vars that are actually read.
6. **There is no regression net.** One config test, no CI, no pytest dependency. Any shared-module consolidation needs Wave-0 tests first, starting with pure functions: `validate_query`, `_pick_executor`, and `mockdata_tool` generators.
7. Open: is `snow-mcp` (MCP mode) still used at all, given the AGENTS.md statement that L'Oréal blocks MCP? If not, mcp.json and settings.json are dead config.
