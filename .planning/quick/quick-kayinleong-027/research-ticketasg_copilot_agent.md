---
status: complete
package: ticketasg_copilot_agent
---
## Purpose & entry points

This is an RCA + assignment-routing agent. The LLM does the reasoning; the package itself makes no LLM calls (`__init__.py:1-2`). It writes **one bipartite report**: the `rca_copilot_agent` RCA template (`WHAT HAPPENED / CHECKED / FOUND / NEED-DID`), then `### REASSIGNMENT DECISION` as the last section (`AGENTS.md:6-13`, `.github/agents/ticketasg_copilot.agent.md:225-286`). It only **recommends**. Nothing changes `assignment_group` in SNOW.

| Entry point | file:line | Notes |
|---|---|---|
| MCP stdio server `ticketasg-copilot` | `mcp_server.py:1039-1104` | Startup sequence: `init_from_schema` (1057) → `_auto_load_store` (1063) → `ensure_credentials` (1065-1069) → `ensure_gcloud_auth` (1071-1075) → MCP SDK. If the `mcp` SDK is missing, it falls back to bare JSON-RPC (990-1036). |
| CLI `run_tool.py <tool> --json` | `run_tool.py:48-106` | Repeats the same startup steps on **every invocation** (76-101), then calls `mcp_server._dispatch` (104-105). |
| **The CLI is the path that actually gets used** | agent.md:23-31, SKILL.md:24-31, AGENTS.md:445-491 | The docs say "L'Oréal's environment does not allow MCP servers". `.vscode/mcp.json` registers only `snow-mcp`, which runs `rca_copilot_agent/mcp_server.py`. **ticketasg is not registered as an MCP server.** |

## Flow table

| Step | Status | How it works today | Key code (file:line) | Config / env | Gaps & risks |
|---|---|---|---|---|---|
| 1a SNOW auth | Implemented | Checks the session with `GET /api/now/table/incident?sysparm_limit=1`. It requires a 200 status, a JSON content type and a `result` key, because SNOW returns 200 + an HTML login page when a session has expired. If the check fails, it opens a headed **Edge** browser (`channel="msedge"`) through Playwright and waits up to 10 min for `**/now/nav/ui/classic**`. It then reads `window.g_ck` as the token and the cookies matching `loreal.service-now.com`, and writes `COOKIE`/`X_USERTOKEN` back to `.env` with `dotenv.set_key`. Each request then authenticates with session cookies + an `X-UserToken` header. | `auth_tool.py:25-43, 46-149 (83, 94-98, 101-120), 152-166, 169-220`; `snow_reader.py:53-76, 78-101`; `mcp_server.py:63-77` | `COOKIE`, `X_USERTOKEN` (also accepts `X-UserToken`/`X-usertoken`), `SNOW_INSTANCE` (default `https://loreal.service-now.com`); env vars override `.env` (`config.py:62-86`) | Expiry is never tracked. A stale session is only found by the next probe or a 401/403 (`snow_reader.py:105-119`). Failures are **non-fatal**: the server starts anyway and the first SNOW call raises (`auth_tool.py:200-204`). The cookie domain filter is hard-coded to `loreal.service-now.com` and ignores `SNOW_INSTANCE` (115-117). Credentials are stored **in plaintext in `.env`**. In CLI mode every call repeats the live probe and can open the browser mid-session. |
| 1b GCP auth | Implemented (only on paper for ADC) | Shells out to `gcloud`. If `$PATH` lookup fails it tries SDK fallback paths (`_find_gcloud`). (i) User credentials: the active account must end in `@loreal.com` and `auth print-access-token` must succeed. Otherwise it runs interactive `gcloud auth login` → `config set account` → `config set project`. (ii) ADC: `application-default print-access-token`. If that fails: `application-default login` → `set-quota-project`. All gcloud output goes to stderr so it cannot corrupt MCP stdout. | `gcloud_tool.py:43-58, 61-93, 183-196, 199-224 (domain check 201), 227-236, 138-146` | `BQ_PROJECT` read from `os.environ` **only** (not `.env`), default `oa-apmena-spacecds-ap-pd` (141, 169) | After login the new account is **not re-checked** for `@loreal.com` (217-222). The ADC check ignores `required_domain` entirely. The project is set only after a fresh login, so an existing wrong project is kept. Failures are non-fatal and only logged. In CLI mode this costs about 3 `gcloud` subprocesses per tool call. The ADC credential is **not used by the query path** (see step 3). |
| 2 Read tickets | Implemented | **Bulk:** `fetch_incidents(list_url)` parses list-view, `/now/nav/ui/classic`, and `sysparm_tiny` URLs (`sys_tiny_url` lookup). An empty query defaults to `active=true`. Results are paginated 100 at a time, sorted by `sys_updated_on` descending, default limit 500. **Terminal states (resolved/closed/cancelled/complete) are dropped.** For each remaining ticket it fetches the full report: the record, journal entries (`sys_journal_field`, falling back to inline fields), attachment metadata (with optional download), and `rm_story` children. It writes `<INC>.json` + `_all_incidents.json` and reloads the store. **Single:** `get_incident` / `analyze_incident` pick the table from the number prefix (RITM→`sc_req_item`, TASK→`sc_task`, else `incident`) and upsert into the combined JSON. **Cache:** `IncidentStore` is an in-memory index over `_all_incidents.json` (by number or sys_id). It provides keyword search and regex identifier extraction (orders, user/MARS IDs, customer codes, phones, EAN, emails). | `snow_reader.py:166-205, 207-224, 237-288, 305-343, 428-504, 506-531, 535-618 (filter 575-580), 620-666`; `mcp_server.py:573-594, 596-640, 652-711`; `incident_store.py:38-66, 75-138, 158-222, 224-298` | `REPORTS_DIR` (default `<pkg>/my_reports`), `ATTACHMENTS_DIR` (default `<pkg>/attachments`) (`config.py:80-81`). The `--reports-dir` flag exists on the MCP server only. | No assignment-group filter is built in; scope comes entirely from the user's list URL. `analyze_incident` **never refreshes** an incident that is already cached, so the data can go stale. It also re-downloads attachments on every call with no try block (701-709), so an expired cookie fails the whole tool. Attachment `file_name` from SNOW is joined into the save path without sanitising (`snow_reader.py:388`), a path-traversal risk. `_get_related_stories` only queries `parent=`; its docstring also promises `task_rel_task` (506-531). No OCR. |
| 3 Access BQ | Partial | BQ feeds the **RCA half of the report only**, not the routing algorithm. The LLM is told to call `list_bq_tables`/`get_schema` (both read local `schema.json`, no BQ cost) and then `query_bigquery` to check consumer / Mars-ID / order presence for the migrated-vs-ongoing question. `query_bigquery` applies the keyword blocklist and the SELECT/WITH check, then runs **the `bq` CLI as a subprocess** (gcloud user credentials) with `--max_rows=100` and a 60 s timeout. The billing project is chosen from the first backtick-quoted project in the SQL. | `bigquery_tool.py:72, 76-80, 149-167, 423-452, 455-468, 492-541, 544-554`; `mcp_server.py:887-902`; agent.md:161-176 | `schema.json` at repo root (`bigquery_tool.py:72`); `max_bytes=500_000_000`, `timeout=30`, `max_rows=100` are hard-coded (446-451) | **The `bq` CLI path skips the dry-run and `maximum_bytes_billed`.** Those guards exist only in `SafeBigQueryExecutor.execute` (181-224), which no tool calls. That conflicts with the root `CLAUDE.md` rule ("Dry-run before every real query", "maximum_bytes_billed"). If `schema.json` is missing, `query_bigquery` is disabled. The first 200 chars of the SQL are logged to stderr, which can include PII identifiers (552). |
| 4 Output (assignment/RCA) | Implemented (recommend-only) | **`recommend_assignment_v2`** applies a fixed priority order: (1) `hard_rules` regex (4 rules) → confidence 0.95; (2) L3 escalation: 13 regex signals plus an `l2_to_l3` map for 3 L2 groups → 0.85, suppressed when the signal appears only in history and the ticket already sits in the keyword-winning L2; (3) kNN retrieval: top-1 agrees with the keyword winner at ≥0.6 → `0.5+score/2`, or keyword confidence <0.4 with top-1 ≥0.7 and ≥2 of top-k in that group → retrieval wins; (4) otherwise the v1 keyword winner. v1 confidence is `top_score/total_hits`. With no hits it falls back to `O+O.OPERATIONS - L2` at 0.0. All signals are returned so the host LLM can act as judge. **Retrieval:** `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, normalised so a dot product equals cosine similarity. The index is an `.npz` of `numbers`/`groups` (pickled object arrays) + `embeddings`. The committed index holds **378 tickets × 384 dims**, read from the npy headers without unpickling. It is rebuilt via the `build_retrieval_index` tool from `_all_incidents.json`. The label for each ticket is its **current** `assignment_group`. | `assignment_tool.py:26-40, 46-64, 159-280, 292-358, 361-623 (518-522, 486-510, 550-579, 429)`; `retrieval_tool.py:37, 48-59, 89-144, 147-166 (allow_pickle 159), 169-214, 217-251`; `assignment_rules.json` (version 2.0 L2; hard_rules L4; l3_escalation L27; groups L50; 10 groups, 8 marked `USER-CONFIRM`) | `ASSIGNMENT_RULES_FILE` (`config.py:82-85`); the index path defaults to `<pkg>/retrieval_index.npz` | The rules are cached for the life of the process and never reloaded (46-64). Corpus bias: it is built only from the user's **open** tickets (terminal states are filtered out in step 2), labelled with their current group, which may be wrong. The model downloads from HuggingFace on first use. `np.load(allow_pickle=True)` on a committed file is a deserialisation risk. The v2 docstring says 0.7 but the code uses 0.6 (387-389 vs 550). **Bug:** `find_similar_incidents` called with only `incident_number` imports a non-existent `incident_store.get_summary` (`mcp_server.py:800`, outside the try), so it errors out. The only eval harness is `.planning/quick/quick-kayinleong-019/scripts/rescore.py`, which covers v1. |
| 5 Output/delivery | Implemented | `save_assignment_report` writes `<REPORTS_DIR>/assignment_reports/<INC>_assignment_<ts>.md` and registers the path in an in-memory session list. `send_assignment_email` builds an HTML email (STARTTLS or SSL) and attaches the session's reports. `post_comment` sends a PATCH to `comments` or `work_notes` only. The prompts say to post as a work note and to confirm with the user first (agent.md:339; tool description `mcp_server.py:250`). **There is no reassignment write-back**: the report asks a human to reassign (agent.md:270). | `mcp_server.py:904-925, 927-951, 729-755, 974-987`; `email_tool.py:29-39, 42-96, 99-161`; `snow_reader.py:670-709` | `SMTP_HOST/PORT/USER/PASSWORD/FROM/TO/USE_TLS/VERIFY_SSL` (`config.py:105-133`); email is enabled only if host, from and to are all set (100-102) | **In CLI mode (the documented path) the email attaches nothing.** `_session_reports` lives in process memory, and each `run_tool.py` call is a new process. `session_summary` and report names go into the HTML **unescaped** (102-105, 108-112). `SMTP_VERIFY_SSL=false` turns certificate checks off (16-20). Confirm-before-post is enforced by the prompt only. |

## Tool inventory

The schemas are defined in `mcp_server.py` (`list_tools`, lines 100-555) and dispatched in `_dispatch` (570-954). There are 19 tools; the JSON-RPC fallback lists the same set (1008-1016).

| Tool | Purpose | file:line (schema → impl) |
|---|---|---|
| fetch_incidents | Bulk download from a list URL, then reload the store | 104 → 573 |
| get_incident | Live fetch by number (INC/RITM/TASK), upsert into the cache | 137 → 596 |
| get_incident_summary | Formatted text of a cached incident | 160 → 642 |
| list_incidents | List cached incidents | 179 → 647 |
| analyze_incident | One-stop: cache or fetch → summary + identifiers + attachment download | 197 → 652 |
| search_incidents | Keyword search over cached incidents | 219 → 713 |
| post_comment | PATCH comment or work note (live write) | 246 → 729 |
| get_assignment_rules | Show the routing matrix as text | 276 → 757 (`assignment_tool.py:126`) |
| recommend_assignment | v1 keyword scorer | 289 → 761 (`assignment_tool.py:159`) |
| recommend_assignment_v2 | Hybrid hard-rule + L3 + kNN + keyword scorer | 337 → 775 (`assignment_tool.py:361`) |
| find_similar_incidents | kNN neighbours + weighted vote | 366 → 791 (bug at 800) |
| build_retrieval_index | Re-embed `_all_incidents.json` into the `.npz` | 392 → 827 (`retrieval_tool.py:89`) |
| extract_identifiers | Regex identifiers from a cached incident | 407 → 842 (`incident_store.py:224`) |
| download_attachments | Download all attachments to `ATTACHMENTS_DIR/<INC>` | 425 → 850 |
| query_bigquery | Read-only SELECT through the `bq` CLI | 445 → 887 (`bigquery_tool.py:544`) |
| get_schema | Table schema from `schema.json` | 471 → 896 |
| list_bq_tables | All tables from `schema.json` | 493 → 900 |
| save_assignment_report | Write the `.md` report and register it for email | 505 → 904 |
| send_assignment_email | HTML email with the session's reports | 528 → 927 |

`test_config.py` (3 tests, offline, all pass): the default `assignment_rules_file` ends in `assignment_rules.json`, the `ASSIGNMENT_RULES_FILE` env var overrides it, and `SmtpConfig.enabled` is False when the host is empty (`test_config.py:29-67`). **There are no tests** for the routing, retrieval, SNOW, BQ, auth or email code.

## Orchestration (who drives the loop; prompt-enforced vs code-enforced sequencing)

- **The host LLM drives the whole loop** (Copilot agent `.github/agents/ticketasg_copilot.agent.md`; Claude skill `/ticketasg-copilot` in `.claude/skills/ticketasg-copilot/SKILL.md`; `AGENTS.md`). Their content is nearly identical. The prescribed order is: analyze_incident → 3-question framework → get_assignment_rules → build_retrieval_index (if missing) → BQ list/schema/query → recommend_assignment_v2 → LLM-as-judge → write report → save_assignment_report → send_assignment_email once per session (agent.md:56-73; SKILL.md:56-79; AGENTS.md:154-171). The LLM must use only `run_in_terminal` + `read_file` (SKILL.md:100-101).
- **Code enforces only:**
  - Auth runs at startup, non-fatal (`mcp_server.py:1065-1075`; `run_tool.py:89-101`).
  - The store is lazy-loaded (`_ensure_store_loaded` 957-971).
  - `analyze_incident` fetches the ticket when it is not cached.
  - The deterministic priority order inside v2.
- **Prompt only — nothing in code enforces these:**
  - BQ before recommendation.
  - Running the 3-question framework.
  - Saving the report before output.
  - Sending the email exactly once.
  - Confirming before `post_comment`.
  - Rebuilding the index after a fetch.
  - Using canonical group names.

  Nothing stops the LLM from skipping BQ and going straight to `recommend_assignment_v2`, or from posting a comment unconfirmed.
- The `l3_escalation` comment and `note` in `assignment_rules.json` describe the deterministic answer as a "baseline, not a hard answer". The LLM is expected to override it.

## Reusable for the RCA flow

- **Auth:** `auth_tool.py` (Playwright SSO → `.env`) and `gcloud_tool.py` are **byte-identical** to the `rca_copilot_agent` copies (checked with `cmp`), so they are good candidates for one shared module. Fix them before sharing: re-check the account domain after login, read the cookie domain from `SNOW_INSTANCE`, and cache the validation result per session so CLI calls do not re-probe.
- **Ticket reading:** `snow_reader.ServiceNowReader` handles list URLs, tiny URLs, the journal fallback, attachments, and RITM/TASK tables. `incident_store` provides `extract_identifiers` (regex → BQ keys). Each differs from the `rca_copilot_agent` copy by only 2 diff lines.
- **BQ:** the `bigquery_tool` blocklist and `schema.json`-driven executors (2-line diff from rca_copilot). Route `query_bigquery` through `SafeBigQueryExecutor.execute`, or add `--maximum_bytes_billed` / `--dry_run` to the CLI call, to meet `CLAUDE.md`.
- **Routing:** `recommend_assignment_v2` + `retrieval_tool` can plug straight in as an optional "who owns it" step after the RCA.
- **Output:** `find_similar_incidents` can surface prior RCAs for similar tickets. The bipartite report template (RCA + REASSIGNMENT DECISION) is already aligned with the rca_copilot headers.
- **Email:** the pattern needs a persistent session manifest on disk (not in memory) to work in CLI mode.

## Open questions

1. Is the "no MCP servers allowed" constraint real? `.vscode/mcp.json` still registers `snow-mcp` for `rca_copilot_agent`. The answer decides whether the shared RCA flow is MCP-first or CLI-first. CLI-first needs persistent state for auth caching and the email session.
2. 8 of the 10 groups are marked `USER-CONFIRM` in `assignment_rules.json`. Who owns the authoritative SharePoint routing matrix, and is there labelled ground truth beyond quick-019's 64 incidents?
3. Should the kNN corpus include resolved/closed tickets labelled with their *final* group? Today the terminal-state filter (`snow_reader.py:575-580`) excludes exactly the best-labelled data.
4. Should the agent ever write `assignment_group` back to SNOW, or does it stay recommend-only with human reassignment? The current design is recommend-only.
5. Is committing `retrieval_index.npz` acceptable? It holds real INC numbers and embeddings derived from ticket text that may contain PII, it is not gitignored, and it is loaded with `allow_pickle=True`.
