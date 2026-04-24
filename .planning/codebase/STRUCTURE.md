# Directory & File Structure

## Annotated Tree

```
space-cds-etl-core-feature-rca-agent/
│
├── rca_agent/                        # PRIMARY: Autonomous RCA investigation agent
│   ├── agent_runner.py               # ReAct loop orchestrator — core entry point
│   ├── run_pipeline.py               # CLI entrypoint for running investigations
│   ├── llm_providers.py              # LLM abstraction (Gemini / OpenAI / Claude)
│   ├── models.py                     # Pydantic data models (Investigation, Tool call, etc.)
│   ├── config.py                     # Environment config via pydantic-settings
│   ├── mcp_server.py                 # MCP server exposing agent as tool
│   ├── snow_image_ocr_agent.py       # Standalone: OCR extraction from ServiceNow images
│   ├── snow_story_reader.py          # Reads ServiceNow incident narratives
│   ├── requirements.txt              # Agent-specific Python dependencies
│   ├── AGENTS.md                     # Agent behaviour specification (for Claude/Gemini)
│   ├── README.md                     # Usage documentation
│   ├── RESEARCH_NOTES.md             # Development research log
│   ├── command.txt                   # Scratch / example invocation
│   ├── .env                          # Local secrets (gitignored)
│   ├── .env.example                  # Secrets template
│   │
│   ├── tools/                        # Tool functions called by the ReAct loop
│   │   ├── __init__.py
│   │   ├── bigquery_tool.py          # Query BigQuery ETL tables
│   │   ├── snow_tool.py              # Fetch ServiceNow incident data
│   │   └── wiki_tool.py              # Search wiki pattern knowledge base
│   │
│   ├── wiki/                         # Knowledge base for pattern matching
│   │   └── wiki_state.json           # Persisted wiki entries
│   │
│   ├── attachments/                  # ServiceNow image attachments (runtime)
│   ├── my_reports/                   # Generated RCA report output
│   │   └── _all_incidents.json       # Cached incident list
│   └── rca_reports/                  # Archived investigation outputs
│
├── rca_copilot_agent/                # SECONDARY: Copilot/assistant variant (in development)
│   ├── __init__.py
│   ├── config.py                     # Config (mirrors rca_agent/config.py structure)
│   ├── mcp_server.py                 # MCP server for copilot mode
│   └── tools/
│       ├── __init__.py
│       ├── bigquery_tool.py          # BQ tool (diverges from rca_agent version)
│       ├── incident_store.py         # Local incident caching/store
│       └── snow_reader.py            # ServiceNow reader (vs snow_tool.py in rca_agent)
│
├── .github/
│   └── agents/
│       └── rca_copilot.agent.md      # GitHub Copilot agent spec for copilot mode
│
├── requirements.txt                  # Root-level dependencies (overlaps with rca_agent/requirements.txt)
├── .env                              # Root-level secrets (gitignored)
├── .env.example                      # Root-level secrets template
└── .gitignore
```

## Key File Roles

| File | Role |
|------|------|
| `rca_agent/agent_runner.py` | Core ReAct loop: think → act → observe → repeat |
| `rca_agent/run_pipeline.py` | CLI entry: accepts incident ID, kicks off investigation |
| `rca_agent/llm_providers.py` | Provider abstraction — switches between Gemini, OpenAI, Claude |
| `rca_agent/models.py` | Shared data contracts (Investigation state, tool schemas) |
| `rca_agent/tools/bigquery_tool.py` | Runs SQL against BigQuery ETL monitoring tables |
| `rca_agent/tools/snow_tool.py` | Fetches incident metadata, comments, attachments from ServiceNow |
| `rca_agent/tools/wiki_tool.py` | Searches wiki_state.json for matching known RCA patterns |
| `rca_agent/snow_image_ocr_agent.py` | Sub-agent: extracts text from image attachments via vision LLM |
| `rca_copilot_agent/mcp_server.py` | MCP interface for copilot variant (active development) |

## Configuration Files

| File | Controls |
|------|----------|
| `rca_agent/config.py` | LLM provider selection, API keys, BQ project/dataset, SNOW URL |
| `rca_agent/.env` | Local secret values (SNOW credentials, GCP SA key path, API keys) |
| `rca_agent/.env.example` | Required env var names — reference for deployment |

## Notable Structural Observations

- **Dual requirements.txt**: both root and `rca_agent/` have one — content likely overlaps, potential drift risk
- **rca_copilot_agent/ is active**: contrary to initial notes, it has 5 Python files (not empty)
- **No tests/ directory**: zero project-owned test files exist anywhere in the tree
- **wiki_state.json**: mutable runtime state checked into the repo — will cause merge conflicts if multiple users run the agent
- **rca_reports/ and my_reports/**: generated output directories, likely gitignored partially

## Where to Add New Code

| What | Where |
|------|-------|
| New investigation tool | `rca_agent/tools/<name>_tool.py` + register in agent_runner |
| New LLM provider | `rca_agent/llm_providers.py` |
| New data model | `rca_agent/models.py` |
| Copilot-mode feature | `rca_copilot_agent/` |
| Tests | Create `tests/unit/` and `tests/integration/` at root |
