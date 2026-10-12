---
status: complete
claim: quick-kayinleong-028
topic: dependency audit (rca_copilot_agent minimal set + root requirements.txt cleanup)
researched: 2026-10-12
confidence: HIGH (imports read from source and confirmed by running in scratch venvs; version constraints read from PyPI JSON)
---

# quick-kayinleong-028: Dependency Audit

## Method (reproducible)

- **AST import scan** of every `*.py` in the four packages, `tests/` included: `scratchpad/scan/scan.py`, run with `venv/bin/python -I`. It records each non-stdlib, non-local import with `file:line` and its enclosing context (`module`, `def X`, `try[ImportError]`). I ran it twice and got identical output (`imports.tsv` == `imports2.tsv`).
- **Import probes** in scratch venvs. `venvbare` is 3.12 with no third-party packages. `venv39` is `/usr/bin/python3` 3.9.6 with `requests` and `python-dotenv` only. `venvfloor` is 3.9.6 with the lower bounds `python-dotenv==1.0.0`, `requests==2.32.0`, `urllib3==1.26.18`. `venv` is 3.12 with the full root file minus sentence-transformers. `venvmcp2` is 3.12 with the latest `mcp` (2.3.0).
- **Dependency tree:** `importlib.metadata.requires()` in `venv` (`scan/tree.py`).
- **Version constraints:** `https://pypi.org/pypi/<pkg>/<ver>/json` → `requires_python`. A declared `>=3.10` is a present constraint.
- **No SNOW, BigQuery, SMTP or LLM calls.** I launched one headless Edge to `about:blank` only, to test the Playwright channel.

Path shorthand: `RCA` = `rca_copilot_agent`, `TAS` = `ticketasg_copilot_agent`, `MOCK` = `mockdata_copilot_agent`, `RAG` = `rca_agent`.

---

## Key findings (read first)

1. **The CLI path of rca_copilot_agent needs only `requests` (+ `urllib3`) and `python-dotenv`.** `playwright` is needed only for automatic SSO login. `mcp` is needed only for `mcp_server.py`. `google-cloud-bigquery` is never imported. [VERIFIED: import probes below; `google.cloud.bigquery in sys.modules` = False after `init_from_schema()` in all venvs]
2. **The test suite (119 tests) needs no third-party packages at all.** It passes in `venvbare`: `Ran 119 tests in 1.086s / OK`. [VERIFIED: run this session]
3. **The root `requirements.txt` cannot install on macOS system Python 3.9.6.** Pasted failure (pip 21.2.4, `/usr/bin/python3 -m venv`):
   ```
   ERROR: Could not find a version that satisfies the requirement anyio==4.13.0 (from versions: ... 4.12.0, 4.12.1)
   ERROR: No matching distribution found for anyio==4.13.0
   ```
   15 of the 51 exact pins declare `requires_python >=3.10` (list below; all 51 checked). This is a likely cause of the reported install failures, alongside sentence-transformers/torch. [VERIFIED: PyPI JSON + install attempt]
4. **`mcp` 2.x breaks all four MCP servers.** `rca_agent/requirements.txt` has `mcp>=1.0.0` (no upper bound), and the latest is `mcp 2.3.0` (uploaded 2026-10-02). With it, `create_mcp_server(...)` raises `AttributeError 'Server' object has no attribute 'list_tools'` in RCA, TAS, MOCK and RAG. With mcp 1.27.0 it succeeds. **Every requirements file must pin `mcp>=1.x,<2`.** [VERIFIED: `venvmcp2` vs `venv` probe]
5. **No entry in the root file is UNUSED.** It is a `pip freeze`: 7 entries are direct deps of some agent and 44 are transitive. Cleaning it up means replacing 51 exact pins with about 6 direct, range-bounded requirements and moving `sentence-transformers` to an opt-in file. Deleting individual pins does not achieve this.
6. **`google-cloud-bigquery` is dead code in all three Copilot agents. It is live only in `rca_agent`.** All Copilot agents query through the `bq` CLI subprocess. `rca_agent/tools/bigquery_tool.py:269` `result = executor.execute(sql)` uses the Python client.
7. **Install friction that is not about pip (relevant to "one-command setup"):** `gcloud_tool.ensure_gcloud_auth()` still runs the ADC check (`gcloud_tool.py:231-232`), and can launch `gcloud auth application-default login` interactively on every `run_tool.py` call. This happens even though AGENTS.md / the agent .md say "ADC is NOT used". Separately, `.vscode/mcp.json` hard-codes the macOS-only `${workspaceFolder}/.venv/bin/python`.

---

## rca_copilot_agent minimal set

Startup sequence of `run_tool.py` [VERIFIED: rca_copilot_agent/run_tool.py:170-208, read this session]:

1. `from config import load_config`. config.py is stdlib-only and parses `.env` itself (`_load_env_file`, config.py:28-39). No dotenv.
2. `try: from tools.bigquery_tool import init_from_schema; init_from_schema()` / `except Exception` (177-182). This reads `schema.json` and builds `SafeBigQueryExecutor` objects. Their `client` property (the only place `from google.cloud import bigquery` runs) is never touched.
3. `load_store(...)` if `_all_incidents.json` exists. stdlib only.
4. `try: from tools.auth_tool import ensure_credentials ...` / `except Exception as e: logger.warning(f"[AUTH] Credential check failed: ...")` (190-195). auth_tool.py:22 `from dotenv import set_key, find_dotenv` is module-level, so a missing dotenv is caught here as `ModuleNotFoundError`.
5. `try: from tools.gcloud_tool import ensure_gcloud_auth ...` / `except Exception` (197-202). Subprocess only, stdlib only.
6. `from mcp_server import _dispatch` (205). mcp_server.py's module level is stdlib only: `argparse, json, logging, os, re, sys, pathlib` (lines 46-54). It imports `mcp` only inside `create_mcp_server` (112-114) and `main` (1022-1026).

| Package | Why (file:line) | Eager / Optional | Feature lost if missing |
|---|---|---|---|
| `requests` | `tools/snow_reader.py:21-22` `import requests` / `from requests.adapters import HTTPAdapter`, module-level. Loaded by `_build_reader()` (mcp_server.py:84) for `fetch_incidents`, `get_incident`, `analyze_incident` (fetch branch), `post_comment`, `download_attachments`, and by `auth_tool.is_session_valid` (auth_tool.py:37) | **Required** for every SNOW tool | All SNOW tools fail with `ModuleNotFoundError`. `is_session_valid` returns False (auth_tool.py:42-43), so with playwright installed the Edge SSO window would open on every call. Offline tools (`get_schema`, `list_bq_tables`, `query_bigquery`, `get_rca_template`, `save_rca_report`, `send_rca_email`, `list_incidents`, `search_incidents`, `extract_identifiers`, `get_incident_summary`) still work. [VERIFIED: venvbare import probe: `FAIL tools.snow_reader ModuleNotFoundError No module named 'requests'`, all other modules OK] |
| `urllib3` | `tools/snow_reader.py:23` `from urllib3.util.retry import Retry`, module-level, a **direct** import. It is also a transitive dependency of requests (`urllib3<3,>=1.26` in requests 2.33.1 metadata) | Required. Always present when requests is | Same as requests. Declare it explicitly (direct import) with a range matching requests: `urllib3>=1.26,<3`. `Retry(total=3, backoff_factor=1, status_forcelist=[...])` works on 1.26.18 [VERIFIED: venvfloor] |
| `python-dotenv` | `tools/auth_tool.py:22` `from dotenv import set_key, find_dotenv`, module-level in auth_tool. `set_key(..., quote_mode="never")` at :164-165; `find_dotenv(usecwd=True)` at :207 | **Required in practice.** Technically guarded: run_tool.py:191-195 catches the ImportError | No credential validation or auto-refresh at startup (`[AUTH] Credential check failed: ModuleNotFoundError: No module named 'dotenv'`). Users must paste COOKIE/X_USERTOKEN by hand. Reading `.env` still works (config.py does not use dotenv). Floor `>=1.0.0` has `quote_mode` [VERIFIED: venvfloor `inspect.signature(set_key)` shows `quote_mode: str = 'always'`] |
| `playwright` | `tools/auth_tool.py:66-71` `from playwright.async_api import async_playwright` inside `capture_credentials_via_browser`, wrapped in `try/except ImportError` → `RuntimeError("playwright not installed. Run: pip install playwright")`. Launch at :83: `p.chromium.launch(channel="msedge", headless=False)` | **Optional (recommended)**. Lazy, only when credentials are missing or expired | Automatic Edge SSO login and write-back of COOKIE/X_USERTOKEN to `.env`. Fallback: `ensure_credentials` prints `[AUTH] playwright not installed...` and returns (auth_tool.py:200-204); the user copies cookies manually per `.env.example`. If playwright is installed but Edge is missing, a `playwright._impl._errors.Error` (subclass of plain `Exception`, not `RuntimeError`) escapes `ensure_credentials`. run_tool.py:194 still catches it as a warning, so it is non-fatal either way [VERIFIED: `Error.__mro__` = `(Error, Exception, BaseException, object)`] |
| `certifi` | `tools/email_tool.py:24-28` `try: import certifi; return ssl.create_default_context(cafile=certifi.where())` / `except ImportError: return ssl.create_default_context()` | **Optional**. Lazy, only for `send_rca_email`. Always installed anyway as a requests dependency (`certifi>=2023.5.7`) | Nothing. Falls back to the system trust store. No need to list it |
| `mcp` | `mcp_server.py:112-114` (`create_mcp_server`) and `:1022-1026` (`main`, `try/except ImportError` → `_run_jsonrpc_fallback`) | **Optional**. Only for `python rca_copilot_agent/mcp_server.py` (the `.vscode/mcp.json` "snow-mcp" server). Never on the `run_tool.py` path | MCP server mode. The JSON-RPC fallback (mcp_server.py:934-971) only handles `tools/list` and `tools/call`, with no `initialize`, so a real MCP client (VS Code) cannot use it. **Must be `<2`** (finding 4) |
| `google-cloud-bigquery` | `tools/bigquery_tool.py:211`, `:240`, `:256`, inside `SafeBigQueryExecutor.client` / `.dry_run` / `.execute` | **Never needed.** Unreachable: no caller of `.client`, `.dry_run`, `.execute`, `.list_tables`, `executor.get_schema`, or `_get_executor()` exists outside bigquery_tool.py's own class (grep this session). `query_bigquery_result` (:659-668) calls `executor.validate_query` (pure regex) then `_bq_cli_execute` (`bq` subprocess). The module docstring says so too (:17-18 "SafeBigQueryExecutor.dry_run()/execute() (python client, ADC) are retained but are not used by query_bigquery.") | None. [VERIFIED: venvbare and venv39 `init_from_schema OK ... google loaded: False`] |

**Minimal complete install for rca_copilot_agent CLI (what Copilot uses):** `requests`, `urllib3`, `python-dotenv`, `playwright`. That is 4 direct packages. With transitives: certifi, charset-normalizer, idna, pyee, greenlet, typing-extensions, so about 10 packages in total. Playwright adds a ~42 MB wheel on macOS arm64 and ~38 MB on win_amd64 [VERIFIED: PyPI JSON for playwright 1.59.0]. No compiler is needed.

### Tests

| Test file | Third-party needs | Skip behaviour |
|---|---|---|
| `tests/test_bq_crossplatform.py` | none (imports `tools.bigquery_tool`, `tools.gcloud_tool`; subprocess mocked) | n/a. One test uses `self.assertNoLogs` (:203), which is a Python 3.10+ unittest API |
| `tests/test_dispatch_rca_flow.py` | none (`_build_reader` patched with `mock.patch.object`) | n/a |
| `tests/test_email_tool.py` | none | n/a |
| `tests/test_rca_report_tool.py` | none | n/a |
| `tests/test_run_tool.py` | none | n/a |

There is **no test of `create_mcp_server`**, and no test imports `mcp`, `requests`, `dotenv` or `playwright`. Nothing needs skipping. Bare 3.12 gives `Ran 119 tests ... OK` [VERIFIED]. A `create_mcp_server` smoke test with `@unittest.skipUnless(importlib.util.find_spec("mcp"), ...)` would have caught the mcp 2.x break. Recommend adding one, plus a dependency self-check test.

---

## Per-agent direct deps

### rca_copilot_agent
See the table above. Summary: required = `requests`, `urllib3`, `python-dotenv`; optional = `playwright` (SSO), `mcp<2` (MCP server mode), `certifi` (transitive anyway); `google-cloud-bigquery` is dead code.

### ticketasg_copilot_agent

| Package | file:line | Eager / Optional | Notes |
|---|---|---|---|
| `requests` | `tools/snow_reader.py:21-22` | Required (module-level) | Same snow_reader as RCA. [VERIFIED: venvbare `FAIL tools.snow_reader ... 'requests'`] |
| `urllib3` | `tools/snow_reader.py:23` | Required (module-level, direct) | transitive of requests too |
| `python-dotenv` | `tools/auth_tool.py:22` | Required in practice (module-level in auth_tool) | [VERIFIED: venvbare `FAIL tools.auth_tool ... 'dotenv'`] |
| `playwright` | `tools/auth_tool.py:67` | Optional (lazy, try/except ImportError) | SSO auto-login |
| `certifi` | `tools/email_tool.py:22` | Optional (lazy, try/except ImportError) | transitive of requests |
| `mcp` | `mcp_server.py:94-96`, `:1078-1082` | Optional (MCP server mode only) | must be `<2` [VERIFIED: venvmcp2] |
| `google-cloud-bigquery` | `tools/bigquery_tool.py:143`, `:172`, `:188` | Never reached | `query_bigquery` → `_bq_cli_execute` (:544-553). `_get_executor` (:471) has no callers |
| `sentence-transformers` | `tools/retrieval_tool.py:68` | **Optional** (lazy, try/except ImportError → RuntimeError) | Lost: `find_similar_incidents` and `build_retrieval_index` error out. `recommend_assignment_v2` degrades gracefully: `assignment_tool.py:467-468` `except RuntimeError as e: retrieval_block = {"available": False, "error": str(e)}`. This is the torch dependency (~250 MB per the requirements comment) |
| `numpy` | `tools/retrieval_tool.py:81` | Optional (lazy) | Reads `retrieval_index.npz` (committed). Not listed anywhere; arrives via sentence-transformers |

### mockdata_copilot_agent

| Package | file:line | Eager / Optional | Notes |
|---|---|---|---|
| (none required) | — | — | CLI runs with **zero** third-party packages. [VERIFIED: venvbare: config, mcp_server, run_tool, tools.bigquery_tool, tools.gcloud_tool, tools.mockdata_tool all `OK`]. No snow_reader, no auth_tool |
| `mcp` | `mcp_server.py:56-57`, `:459-463` | Optional (MCP server mode) | must be `<2` [VERIFIED: venvmcp2 `AttributeError ... 'list_tools'`; 1.27.0 OK] |
| `google-cloud-bigquery` | `tools/bigquery_tool.py:143`, `:172`, `:188` | Never reached | `query_bigquery` / `query_bigquery_rows` → `_bq_cli_execute` (:553, :573) |
| `openpyxl` | `tools/mockdata_tool.py:508` | Optional (lazy, try/except ImportError → RuntimeError "paste the seed as JSON instead") | **Missing from both requirements files** |

### rca_agent (standalone ReAct agent + its MCP server)

| Package | file:line | Eager / Optional | Notes |
|---|---|---|---|
| `pydantic` | `models.py:11`, `agent_runner.py:35` | Required for `agent_runner.py` (module-level). Not imported by `mcp_server.py` | [VERIFIED: venvbare `FAIL models`, `FAIL agent_runner`; `OK mcp_server`] |
| `requests` | `snow_story_reader.py:26` (module-level) | Required for snow_story_reader | |
| `urllib3` | `snow_story_reader.py:64` (in `__init__`) | Required with snow_story_reader | transitive of requests |
| `google-cloud-bigquery` | `tools/bigquery_tool.py:90`, `:120`, `:137` | **Required for BQ queries.** Live path: `query_bigquery` → `executor.execute(sql)` (:265-270) | **Must NOT be removed from `rca_agent/requirements.txt`** |
| `mcp` | `mcp_server.py:53` (`_check_mcp_sdk`), `:95-97`, `:415` | Optional (falls back to JSON-RPC, :425-427) | currently `mcp>=1.0.0` → resolves to 2.3.0 → broken. Pin `<2` |
| `anthropic` | `llm_providers.py:75` (in `AnthropicProvider.__init__`) | Lazy; needed for the default `LLM_PROVIDER=anthropic` (config.py:53) | listed in rca_agent/requirements.txt |
| `openai` | `llm_providers.py:166` | Lazy; only `LLM_PROVIDER=openai` | commented out in rca_agent/requirements.txt |
| `google-generativeai` | `llm_providers.py:236`, `:245`, `:258`, `:290`, `:353` | Lazy; only `LLM_PROVIDER=google` | listed; PyPI classifier `Development Status :: 7 - Inactive` (latest 0.8.6) [VERIFIED: PyPI JSON]. Out of scope to migrate; flag only |
| `Pillow` (`PIL`), `pytesseract` | `snow_image_ocr_agent.py:37-38` (module-level `try/except ImportError` → prints help, `sys.exit(1)` at :45) | Required only for that script | commented out in rca_agent/requirements.txt; also needs the Tesseract binary |

---

## Root requirements.txt line-by-line

The file has 54 lines: 51 `==` pins, 2 comment lines (45-46) and `sentence-transformers>=2.5.0` [VERIFIED: `wc -l` = 54, `grep -c ==` = 51]. The "Needed by" column comes from `importlib.metadata.requires()` in `venv` (`scan/tree.py`) plus the AST scan. ST = sentence-transformers. **py≥3.10** marks pins whose PyPI `requires_python` is `>=3.10`, so they fail on 3.9.

| # | Package (pin) | Needed by | Direct / Transitive / UNUSED |
|---|---|---|---|
| 1 | annotated-types==0.7.0 | pydantic ← mcp; pydantic ← RAG | Transitive |
| 2 | anyio==4.13.0 **py≥3.10** | mcp, httpx, starlette, sse-starlette | Transitive (mcp) |
| 3 | attrs==26.1.0 | jsonschema, referencing ← mcp | Transitive (mcp) |
| 4 | certifi==2026.4.22 | RCA email_tool.py:25, TAS email_tool.py:22 (optional); requests, httpx, httpcore | Direct-optional + Transitive (requests) |
| 5 | cffi==2.0.0 | cryptography | Transitive (google-auth / pyjwt[crypto]) |
| 6 | charset-normalizer==3.4.7 | requests | Transitive (requests) |
| 7 | click==8.3.3 **py≥3.10** | uvicorn ← mcp | Transitive (mcp) |
| 8 | cryptography==47.0.0 | google-auth ← google-cloud-bigquery; pyjwt[crypto] ← mcp (`pyjwt[crypto]>=2.10.1`) | Transitive |
| 9 | google-api-core==2.30.3 | google-cloud-bigquery (`google-api-core[grpc]`) | Transitive (bq client) |
| 10 | google-auth==2.50.0 | google-cloud-bigquery, google-api-core, google-cloud-core | Transitive (bq client) |
| 11 | google-cloud-bigquery==3.41.0 | **RAG only, live** (tools/bigquery_tool.py:269). RCA/TAS/MOCK: imported lazily, unreachable | Direct (RAG). Dead code in Copilot agents |
| 12 | google-cloud-core==2.5.1 | google-cloud-bigquery | Transitive (bq client) |
| 13 | google-crc32c==1.8.0 | google-resumable-media | Transitive (bq client) |
| 14 | google-resumable-media==2.8.2 | google-cloud-bigquery | Transitive (bq client) |
| 15 | googleapis-common-protos==1.74.0 | google-api-core, grpcio-status | Transitive (bq client) |
| 16 | greenlet==3.5.0 **py≥3.10** | playwright (`greenlet<4.0.0,>=3.1.1`) | Transitive (playwright) |
| 17 | grpcio==1.80.0 | google-api-core[grpc] extra ← google-cloud-bigquery | Transitive (bq client) |
| 18 | grpcio-status==1.80.0 | google-api-core[grpc] extra | Transitive (bq client) |
| 19 | h11==0.16.0 | httpcore, uvicorn | Transitive (mcp) |
| 20 | httpcore==1.0.9 | httpx | Transitive (mcp) |
| 21 | httpx==0.28.1 | mcp | Transitive (mcp) |
| 22 | httpx-sse==0.4.3 | mcp | Transitive (mcp) |
| 23 | idna==3.13 | requests, anyio, httpx | Transitive |
| 24 | jsonschema==4.26.0 **py≥3.10** | mcp | Transitive (mcp) |
| 25 | jsonschema-specifications==2025.9.1 | jsonschema | Transitive (mcp) |
| 26 | mcp==1.27.0 **py≥3.10** | RCA/TAS/MOCK/RAG `mcp_server.py` (MCP mode only) | Direct-optional. **Keep `<2`** |
| 27 | packaging==26.2 | google-cloud-bigquery | Transitive (bq client) |
| 28 | playwright==1.59.0 | RCA auth_tool.py:67, TAS auth_tool.py:67 | Direct-optional |
| 29 | proto-plus==1.27.2 | google-api-core | Transitive (bq client) |
| 30 | protobuf==6.33.6 | google-api-core, googleapis-common-protos, proto-plus, grpcio-status | Transitive (bq client) |
| 31 | pyasn1==0.6.3 | pyasn1-modules | Transitive (bq client) |
| 32 | pyasn1_modules==0.4.2 | google-auth | Transitive (bq client) |
| 33 | pycparser==3.0 **py≥3.10** | cffi | Transitive |
| 34 | pydantic==2.13.3 | RAG models.py:11 / agent_runner.py:35; mcp; pydantic-settings | Direct (RAG) + Transitive (mcp) |
| 35 | pydantic-settings==2.14.0 **py≥3.10** | mcp | Transitive (mcp) |
| 36 | pydantic_core==2.46.3 | pydantic | Transitive |
| 37 | pyee==13.0.1 | playwright | Transitive (playwright) |
| 38 | PyJWT==2.12.1 | mcp | Transitive (mcp) |
| 39 | python-dateutil==2.9.0.post0 | google-cloud-bigquery | Transitive (bq client) |
| 40 | python-dotenv==1.2.2 **py≥3.10** | RCA auth_tool.py:22, TAS auth_tool.py:22; pydantic-settings | **Direct (RCA, TAS)** + Transitive (mcp) |
| 41 | python-multipart==0.0.27 **py≥3.10** | mcp | Transitive (mcp) |
| 42 | referencing==0.37.0 **py≥3.10** | jsonschema, jsonschema-specifications | Transitive (mcp) |
| 43 | requests==2.33.1 **py≥3.10** | RCA/TAS snow_reader.py:21, RAG snow_story_reader.py:26; google-api-core, google-cloud-bigquery | **Direct (RCA, TAS, RAG)** |
| 44 | rpds-py==0.30.0 **py≥3.10** | jsonschema, referencing | Transitive (mcp) |
| 45-46 | `# Retrieval (kNN) ...` comments | — | — |
| 47 | sentence-transformers>=2.5.0 (unpinned; latest 6.1.0, requires torch>=2.2, transformers, scikit-learn, scipy, numpy, huggingface-hub, tqdm) | TAS retrieval_tool.py:68 (optional) | Direct-optional (TAS). **Move to an opt-in file** |
| 48 | six==1.17.0 | python-dateutil | Transitive (bq client) |
| 49 | sse-starlette==3.4.1 **py≥3.10** | mcp | Transitive (mcp) |
| 50 | starlette==1.0.0 **py≥3.10** | mcp, sse-starlette | Transitive (mcp) |
| 51 | typing-inspection==0.4.2 | mcp, pydantic, pydantic-settings | Transitive |
| 52 | typing_extensions==4.15.0 | anyio, grpcio, mcp, pydantic, pyee, referencing, starlette, ... | Transitive |
| 53 | urllib3==2.6.3 | RCA/TAS snow_reader.py:23, RAG snow_story_reader.py:64; requests | **Direct (RCA, TAS, RAG)** + Transitive (requests) |
| 54 | uvicorn==0.46.0 **py≥3.10** | mcp | Transitive (mcp) |

**UNUSED: none.** The pins split into four groups:
- **Direct:** 7 entries: requests, urllib3, python-dotenv, playwright, mcp, google-cloud-bigquery, pydantic. certifi and sentence-transformers are direct-optional.
- **mcp transitives:** about 20 pins.
- **google-cloud-bigquery transitives:** about 15 pins. These are only needed by rca_agent.
- **playwright transitives:** 2 pins (greenlet, pyee).

**Windows note:** the freeze was taken on macOS. On Windows, pip also pulls `pywin32>=310` (mcp: `pywin32>=310; sys_platform == 'win32'`) and `colorama` (click: `colorama; platform_system == 'Windows'`). These are not pinned, so pip resolves them automatically [VERIFIED: venv metadata]. The exact-pin file is not a cross-platform lock in any case.

**`requires_python >=3.10` pins (exactly 15 of 51):** anyio 4.13.0, click 8.3.3, greenlet 3.5.0, jsonschema 4.26.0, mcp 1.27.0, pycparser 3.0, pydantic-settings 2.14.0, python-dotenv 1.2.2, python-multipart 0.0.27, referencing 0.37.0, requests 2.33.1, rpds-py 0.30.0, sse-starlette 3.4.1, starlette 1.0.0, uvicorn 0.46.0. These are the ones bolded in the table. [VERIFIED: PyPI JSON `requires_python` queried for all 51 pins; output in `scratchpad/scan/pins_rp.txt`]

### rca_agent/requirements.txt (existing, 25 lines)

| Line | Entry | Status |
|---|---|---|
| `pydantic>=2.0` | RAG models/agent_runner | Keep |
| `requests>=2.31` | RAG snow_story_reader | Keep (raise to `>=2.32` for the CVE-2024-35195 fix [ASSUMED]) |
| `anthropic>=0.40.0` | RAG llm_providers.py:75 (default provider) | Keep. Latest is 1.13.0 (`>=3.10`), a major-version jump. API compatibility not tested [ASSUMED risk] |
| `# openai>=1.50.0` | llm_providers.py:166 | Commented; keep as is |
| `google-generativeai` | llm_providers.py:236+ | Keep (inactive upstream; flag) |
| `google-cloud-bigquery>=3.20` | **live** in RAG | **Must keep** |
| `mcp>=1.0.0` | RAG mcp_server | **Change to `mcp>=1.0,<2`** (2.3.0 breaks `@server.list_tools()`) |
| `# pytesseract` / `# Pillow` | snow_image_ocr_agent.py:37-38 | Commented; keep, or move to `rca_agent/requirements-ocr.txt` |

---

## Missing-from-requirements imports

| Import (dist) | Where | In root? | In rca_agent/? | Recommendation |
|---|---|---|---|---|
| `openpyxl` | MOCK tools/mockdata_tool.py:508 (lazy, optional) | no | no | Add to `mockdata_copilot_agent/requirements.txt` (`openpyxl>=3.1`; small, pure-Python) |
| `numpy` | TAS tools/retrieval_tool.py:81 (lazy) | no (via ST) | no | Arrives with sentence-transformers. Optionally list it in the retrieval extras file. Latest numpy 2.5.4 needs `>=3.12`; let ST pick the version |
| `PIL` (Pillow), `pytesseract` | RAG snow_image_ocr_agent.py:37-38 | no | commented | Keep commented, or add an OCR extras file. Also needs the Tesseract binary |
| `openai` | RAG llm_providers.py:166 | no | commented | as is |
| `anthropic`, `google.generativeai` | RAG llm_providers.py | no | yes | as is (RAG-only) |
| `pywin32`, `colorama` | transitive on Windows (mcp, click) | no | no | none; resolved automatically by pip |

---

## Min Python version, with evidence

| Check | Result |
|---|---|
| `ast.parse(..., feature_version=(3,X))` for X = 7, 8, 9, 10, 11 on every file in all 4 packages | All **OK** (no `match`, no syntax newer than 3.7). Caveat: `feature_version` is best-effort [CITED: docs.python.org/3/library/ast.html#ast.parse, ASSUMED wording] |
| `from __future__ import annotations` | Present in every RCA module except the two `__init__.py`, `tests/test_run_tool.py` and `tests/test_bq_crossplatform.py`, so `X \| Y` / `list[str]` annotations are not evaluated at runtime. RAG `run_pipeline.py` lacks it but uses PEP 585 annotations (lines 42, 120, 232). It imports fine on 3.12; on 3.8 it would fail (not tested) |
| `tomllib`, `datetime.UTC`, `zoneinfo`, `match`, `str.removeprefix`, `zip(strict=)`, `isinstance(x, A \| B)` | None found (`scan/pyver.py`) |
| Runtime on **3.9.6** (`/usr/bin/python3`) with requests+dotenv | All 10 RCA modules import; `run_tool.py --help` works; `init_from_schema` OK. Test suite: `Ran 119 tests ... FAILED (errors=1)`. The one error is `AttributeError: 'OverrideWarningTests' object has no attribute 'assertNoLogs'` (test_bq_crossplatform.py:203). That is a test-only use of a 3.10+ unittest API [VERIFIED: run this session] |
| 3.9 + lower bounds (`python-dotenv==1.0.0`, `requests==2.32.0`, `urllib3==1.26.18`) | Same result: 119 run, 1 error (same `assertNoLogs`) [VERIFIED] |
| macOS system Python 3.9.6 environment | urllib3 2.x warns on every run: `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'`. It ships **pip 21.2.4** (no `--dry-run`, old resolver). The root file fails at `anyio==4.13.0` (Key finding 3) [VERIFIED] |
| Dependency floors | `mcp` (any 1.2x release) `>=3.10`; latest `requests` 2.34.2, `python-dotenv` 1.2.4, `urllib3` 2.8.0, `playwright` 1.63.0 are all `requires_python >=3.10` [VERIFIED: PyPI JSON]. 3.9 still resolves older releases (requests 2.32.5, python-dotenv 1.2.1 were selected on 3.9) |
| gcloud CLI | "requires Python 3.10 to 3.15" (macOS); Windows "supported versions are Python 3.10 to 3.15". Both bundle their own Python [CITED: docs.cloud.google.com/sdk/docs/install-sdk] |
| Top end | Pinned compiled deps (pydantic-core 2.46.3, rpds-py 0.30.0, greenlet 3.5.0, google-crc32c 1.8.0, cffi 2.0.0, grpcio 1.80.0) have win_amd64 wheels for cp310–cp314 and **none for cp315** (3.15 is rc). Torch 2.14.1 has wheels for cp310–cp314, only `macosx_14_0_arm64` / `win_amd64` / manylinux: **no Intel-Mac, no win_arm64, no sdist** [VERIFIED: PyPI JSON file lists] |

**Conclusion:**
- **Code floor:** 3.9 for runtime, 3.10 for the test suite.
- **Supported floor to document:** Python **3.10**. mcp, every current dependency and the gcloud CLI all require it, and macOS system 3.9.6 is a poor runtime (LibreSSL, pip 21).
- **Recommended:** **3.12** (what was tested here; torch wheels available).
- **Avoid:** 3.15 pre-release.
- **CLAUDE.md conflict:** CLAUDE.md:24 says "Python 3.11+". Either keep "3.11+ (3.12 recommended)" in docs for consistency, or relax CLAUDE.md to 3.10+. This is a doc decision (see Open questions).

---

## External prerequisites (rca_copilot_agent)

| Prerequisite | macOS | Windows | Evidence / notes |
|---|---|---|---|
| Python 3.10+ (3.12 recommended) and a venv `.venv` at repo root | python.org installer, Homebrew, or `uv python install 3.12`. **Not** `/usr/bin/python3` (3.9.6) | python.org installer or `winget`; `py -3.12 -m venv .venv` | Docs tell users to activate `.venv` (.github/agents/rca_copilot.agent.md:89). PowerShell may need `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` for `Activate.ps1` [ASSUMED] |
| **Google Cloud CLI (`gcloud` + `bq`)** | install.sh or Homebrew cask; bundles Python | Windows installer (bundles Python) | `bq` is a default component: "the following components are installed by default: gcloud, bq, gsutil, core" [CITED: docs.cloud.google.com/sdk/docs/components]. Auto-detected via PATH plus fallbacks (bigquery_tool.py:40-55, gcloud_tool.py:34-52); override with `BQ_BIN` / `GCLOUD_BIN` |
| `gcloud auth login` with an `@loreal.com` account | ✓ | ✓ | gcloud_tool.py `_ensure_user_auth`; `set_project()` defaults to `oa-apmena-spacecds-ap-pd` (gcloud_tool.py:177) |
| **ADC** (`gcloud auth application-default login`) | ✓ | ✓ | Docs say not used, but `ensure_gcloud_auth` calls `_ensure_adc_auth(required_domain)` (gcloud_tool.py:232). If ADC is missing it runs `gcloud auth application-default login` interactively (:263-272, timeout 600 s) **on every run_tool call**. Either run it once during setup, or (code change, separate decision) drop or gate the ADC step |
| IAM | BigQuery `dataViewer` + `jobUser` on the PD/DV projects | same | bigquery_tool.py:11 docstring |
| **Microsoft Edge** | Must be installed (`/Applications/Microsoft Edge.app`) | Normally preinstalled [ASSUMED] | Needed only with playwright. **`playwright install` is NOT needed** for `channel="msedge"`. Proof: with `PLAYWRIGHT_BROWSERS_PATH` set to an empty dir, `chromium.launch(channel='msedge')` → `msedge launched, version 155.0.4283.45`, while bundled chromium → `BrowserType.launch: Executable doesn't exist at .../empty-pw-browsers...` [VERIFIED]. Docs: Playwright "can operate against the branded Google Chrome and Microsoft Edge browsers available on the machine (note that Playwright doesn't install them by default)" [CITED: playwright.dev/python/docs/browsers]. Do **not** run `playwright install msedge`; it overwrites the system Edge install [CITED: same page] |
| `schema.json` at repo root | committed | committed | Resolved as `Path(__file__).resolve().parent.parent.parent / "schema.json"` (bigquery_tool.py:140), so it is CWD-independent. `git ls-files schema.json` → tracked [VERIFIED] |
| `.env` | `cp .env.example .env` at repo root | `copy .env.example .env` | config.py looks in CWD then `rca_copilot_agent/` (config.py:42-48); auth_tool writes back via `find_dotenv(usecwd=True)`, else `CWD/.env` (auth_tool.py:207-209). COOKIE/X_USERTOKEN are auto-filled by the Edge SSO flow; **SMTP_*** values must be filled manually for `send_rca_email` (`SMTP_VERIFY_SSL=false` behind TLS-intercepting proxies). `.env` and `.env.*` are gitignored (.gitignore:131, 191-192) |
| Run from repo root | ✓ | ✓ | Docs use `python rca_copilot_agent/run_tool.py`. run_tool inserts its own dir on `sys.path` (run_tool.py:72) |
| VS Code + GitHub Copilot (agent mode, custom agents in `.github/agents/`) | ✓ | ✓ | [ASSUMED requirement] |
| `.vscode/mcp.json` (optional MCP mode) | works | **broken path**: `"command": "${workspaceFolder}/.venv/bin/python"` is macOS/Linux-only; Windows needs `.venv\Scripts\python.exe` | [VERIFIED: .vscode/mcp.json read this session]. Only matters if mcp is installed and the snow-mcp server is used |
| Network | PyPI access (corporate proxy/TLS interception may break `pip install`) | same | [ASSUMED]. pip ≥ 24.2 can use the OS trust store via `truststore` [ASSUMED]. Upgrade pip inside the venv first (`python -m pip install -U pip`) |

---

## Recommended file layout

Put direct dependencies only in per-agent files, with major-version-bounded ranges instead of `==` pins. The root file aggregates them with `-r`, and heavy or optional features go in opt-in files. Nested `-r` paths resolve relative to the file that contains them: from CWD `/`, `pip install -r <scratch>/reqtest/requirements.txt` containing `-r sub/requirements.txt` installed `requests 2.32.5` and `python-dotenv 1.2.1` from `sub/` with pip 21.2.4 [VERIFIED].

```
requirements.txt                              # root: all Copilot agents incl. MCP mode (no torch, no google-cloud-bigquery)
    -r rca_copilot_agent/requirements.txt
    -r ticketasg_copilot_agent/requirements.txt
    -r mockdata_copilot_agent/requirements.txt
    -r requirements-mcp.txt
requirements-mcp.txt                          # shared: mcp>=1.2,<2   (only for python <agent>/mcp_server.py)
rca_copilot_agent/requirements.txt            # MINIMAL for colleagues
    requests>=2.32,<3
    urllib3>=1.26,<3
    python-dotenv>=1.0
    playwright>=1.40          # optional at runtime (auto SSO via installed Edge); no `playwright install` needed
ticketasg_copilot_agent/requirements.txt      # same four as rca_copilot_agent (identical snow_reader/auth_tool)
ticketasg_copilot_agent/requirements-retrieval.txt   # opt-in kNN: sentence-transformers>=2.5.0  (pulls torch ~250 MB, numpy)
mockdata_copilot_agent/requirements.txt       # openpyxl>=3.1  (optional xlsx seed parsing; CLI otherwise stdlib-only)
rca_agent/requirements.txt                    # existing; ONLY change: mcp>=1.0,<2 (keep google-cloud-bigquery, pydantic, requests, anthropic, google-generativeai)
```

Colleague install for rca_copilot_agent: `python -m pip install -r rca_copilot_agent/requirements.txt`. That is 4 direct packages, about 10 in total, all binary wheels, no compiler, no torch.

**Why this layout:**
- **Per-agent files** make "what does agent X need" auditable and let the RCA install skip torch, mcp's ~20 transitives and the bq client's ~15.
- **Ranges** instead of `==` pins are needed because the macOS-frozen exact pins are the proven 3.9 failure, and exact pins do not lock across OSes anyway (the freeze does not pin pywin32 or colorama).
- **Upper bounds on majors** (`<2` for mcp, `<3` for requests/urllib3) guard against the mcp 2.x break that already exists today.
- **Keeping the root file working** (`pip install -r requirements.txt` still installs everything the three Copilot agents use, including MCP mode) preserves the instruction in CLAUDE.md:128 and the agent docs.
- **`playwright` stays in the RCA core file** because its wheels are prebuilt for macOS and Windows (38–43 MB), it needs no browser download with Edge, and the documented flow (rca_copilot_agent/AGENTS.md:36-47) depends on it. If even that is too heavy, it is the one safe candidate to move to an opt-in file (fallback: manual cookie copy).
- Optional: a `constraints.txt` (or `uv pip compile` per OS) for reproducible builds. It is not needed for "easy install".

**Must NOT be removed (or the other agents break):**
1. `requests`, `urllib3`, `python-dotenv`, `playwright` for ticketasg (same snow_reader/auth_tool as RCA).
2. `sentence-transformers` must remain *available* in `ticketasg_copilot_agent/requirements-retrieval.txt`, and the TAS docs and skill must say to install it. Without it, `find_similar_incidents` and `build_retrieval_index` fail, and `recommend_assignment_v2` silently loses the retrieval signal (assignment_tool.py:467-468).
3. `mcp` (bounded `<2`) for anyone using any `mcp_server.py` / `.vscode/mcp.json`.
4. `google-cloud-bigquery` and `pydantic` must stay in `rca_agent/requirements.txt`, which is the live BQ path for rca_agent. They can be dropped from the root file only because rca_agent has its own file and the root never contained `anthropic` anyway, so rca_agent users already needed `rca_agent/requirements.txt`.
5. `openpyxl` is newly *added* for mockdata (it was missing before).

**Docs to update alongside** (references found by grep):
- CLAUDE.md:24 and :128 (`pip install -r requirements.txt`, Python version)
- rca_agent/README.md:42
- rca_copilot_agent/AGENTS.md:43 (`pip install playwright`)
- .github/agents/rca_copilot.agent.md:89
- .claude/skills/rca-copilot/SKILL.md:25, ticketasg-copilot/SKILL.md:350, mockdata-copilot/SKILL.md:27 (venv activation)

A dependency self-check (e.g. `run_tool.py doctor`, or a small `check_deps.py` using `importlib.util.find_spec` for `requests`, `urllib3`, `dotenv`, `playwright`, plus `shutil.which`/fallback lookup for `gcloud`/`bq` and an Edge path probe) would make "no missing libraries" verifiable without calling any service.

---

## Package Legitimacy Audit

No new packages are introduced. Every package named above is already declared in the repo's requirements files or imported by repo code, except `openpyxl`, which is imported at mockdata_tool.py:508. Names were confirmed via PyPI JSON this session.

| Package | Registry | Seam verdict | Seam reasons | Disposition |
|---|---|---|---|---|
| requests, python-dotenv, urllib3, certifi, playwright, mcp, google-cloud-bigquery, sentence-transformers, openpyxl, numpy, anthropic, google-generativeai, pydantic, pytesseract, pillow | PyPI | SUS (all) | `unknown-downloads` (all); `too-new` (recent latest release) for most; `no-repository` for urllib3, playwright, google-cloud-bigquery, numpy | Existing, long-established dependencies. The flags are seam artifacts (PyPI has no download API; "too-new" refers to the latest release date). Per protocol the planner should still add a `checkpoint:human-verify` before the first install of the **newly added** `openpyxl` line. The others are already installed by today's files |

---

## Assumptions Log

| # | Claim | Risk if wrong |
|---|---|---|
| A1 | `playwright>=1.40` is a safe floor (tested only 1.59.0) | Older playwright lacks an API used (`wait_for_url`); pin to `>=1.59` if unsure |
| A2 | `mcp>=1.2` floor (tested only 1.27.0; `<2` is verified) | Very old 1.x may lack `mcp.server.lowlevel.server.NotificationOptions`; use `>=1.27,<2` if unsure |
| A3 | Edge is preinstalled on Windows 10/11 corporate images | Users without Edge get a non-fatal auth warning and fall back to manual cookies |
| A4 | PowerShell execution policy may block `Activate.ps1` | Setup script should call `.venv\Scripts\python.exe` directly instead of activating |
| A5 | `requests>=2.32` fixes CVE-2024-35195 | Only affects the suggested floor |
| A6 | anthropic 1.x is API-compatible with rca_agent's `messages.create` usage | Only matters if rca_agent's `anthropic>=0.40.0` is tightened or loosened; leave as is |
| A7 | Corporate proxy/TLS interception is a cause of pip failures | Setup docs may need a proxy/trust-store note |
| A8 | `ast.parse(feature_version=...)` coverage is best-effort | Mitigated by the empirical 3.9 run |

## Open questions

1. **Python floor in docs:** CLAUDE.md says 3.11+. The technical floor is 3.10, and 3.12 is recommended. Decide whether to keep "3.11+" or relax it.
2. **ADC prompt:** should `ensure_gcloud_auth` stop running `_ensure_adc_auth` for the Copilot agents (code change), or should setup just run `gcloud auth application-default login` once? Today it blocks every `run_tool.py` call where ADC is missing.
3. **`.vscode/mcp.json` Windows path:** fix it (e.g. a platform-specific command, or document that MCP mode is macOS-only) or leave it, since the Copilot agent uses the CLI.
4. **Playwright in core or opt-in:** recommended core (documented flow). Move it to opt-in only if the 40 MB is a concern.
