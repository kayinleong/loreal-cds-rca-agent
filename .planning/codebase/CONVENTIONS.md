# Coding Conventions

**Analysis Date:** 2026-04-24

## Naming Patterns

**Files:**
- `snake_case.py` throughout — e.g., `agent_runner.py`, `bigquery_tool.py`, `snow_tool.py`
- Tool modules named after their integration: `bigquery_tool.py`, `snow_tool.py`, `wiki_tool.py`
- Entry-point scripts are descriptive verbs or nouns: `run_pipeline.py`, `snow_story_reader.py`, `snow_image_ocr_agent.py`
- Config and models use flat names: `config.py`, `models.py`
- `__init__.py` files re-export public symbols explicitly via `__all__`

**Classes:**
- `PascalCase` — e.g., `RCAAgentRunner`, `SafeBigQueryExecutor`, `IncidentLoader`, `InvestigationWiki`
- `LLMProvider` (abstract base), `AnthropicProvider`, `OpenAIProvider`, `GoogleProvider` (concrete implementations)
- Pydantic models: `BQQueryInput`, `FindingInput`, `RCAReport`, `RCACheck`, `AgentState`
- Config dataclasses: `AgentConfig`, `BigQueryConfig`, `ServiceNowConfig`, `LLMConfig`

**Functions:**
- `snake_case` throughout — e.g., `init_executor`, `query_bigquery`, `lookup_schema`, `get_loader`
- Module-level singletons initialized with `init_*()` and retrieved with `get_*()` — e.g., `init_loader()` / `get_loader()`
- Private helpers prefixed with `_` — e.g., `_resolve_llm_api_key`, `_load_env`, `_build_contents`
- Static methods on classes used for pure transformations: `_extract_section`, `_extract_checks`, `_convert_tools`

**Variables:**
- `snake_case` for local and instance variables
- Module-level singletons prefixed with `_`: `_executor`, `_loader`, `_wiki`, `_dataset`
- Constants in `UPPER_SNAKE_CASE`: `DANGEROUS_KEYWORDS`, `TOOL_FUNCTIONS`, `TOOL_SCHEMAS`, `IMAGE_EXTENSIONS`

**Type Annotations:**
- `from __future__ import annotations` used in all core modules for forward-compatible annotations
- Return types and parameter types annotated on all class methods and module-level functions
- `Optional[T]` used (from `typing`) rather than `T | None` union syntax
- `list[dict]`, `dict[str, str]` used as generic annotations (modern style)
- Pydantic `Field(...)` used for validation metadata on model fields
- `@dataclass` used for internal state/config objects; `pydantic.BaseModel` used for tool I/O and report models

## Code Style

**Formatting:**
- No linter config files present (no `.pylintrc`, `.flake8`, `pyproject.toml`, `setup.cfg`)
- 4-space indentation throughout
- Lines kept to a reasonable length; long strings broken with implicit concatenation or `\` continuation
- Section separators using `# ── Section Name ────────────────────` style comments within files
- Blank lines between logical groups; two blank lines between top-level definitions

**Imports:**
- Standard library first, then third-party, then local — consistent across all files
- Heavy dependencies (e.g., `anthropic`, `google.cloud.bigquery`, `openai`) are imported lazily inside methods/constructors to avoid hard failures when a provider is not installed
- `from __future__ import annotations` always at top when present

**String Formatting:**
- f-strings used exclusively for dynamic strings
- `%s` or `.format()` style not used

## Module Organization

**Package structure:**
- `rca_agent/` — production agent with LLM-agnostic ReAct loop
  - `config.py` — all tunables in one place via `@dataclass` and `os.getenv`
  - `models.py` — Pydantic models for tool I/O and report output
  - `llm_providers.py` — abstract `LLMProvider` + Anthropic/OpenAI/Google implementations
  - `agent_runner.py` — `RCAAgentRunner` class + CLI `main()`
  - `mcp_server.py` — MCP server exposing tools
  - `tools/` — pure function tool implementations (BQ, SNOW, Wiki)
- `rca_copilot_agent/` — Copilot variant using GitHub Copilot as the LLM, no LLM libraries

**Singleton pattern:**
- Each tool module maintains a module-level `_singleton` variable
- `init_*()` creates/replaces it, `get_*()` retrieves it with a `RuntimeError` guard
- Example in `rca_agent/tools/bigquery_tool.py`:
  ```python
  _executor: Optional[SafeBigQueryExecutor] = None

  def init_executor(project: str, dataset: str, **kwargs):
      global _executor, _dataset
      ...

  def _get_executor() -> SafeBigQueryExecutor:
      if _executor is None:
          raise RuntimeError("BigQuery executor not initialized. Call init_executor() first.")
      return _executor
  ```

**Tool functions are pure wrappers:**
- Module-level functions (e.g., `query_bigquery`, `search_incident`, `update_findings`) are thin wrappers around class methods
- This makes them usable directly by both `agent_runner.py` (via `TOOL_FUNCTIONS` dict dispatch) and `mcp_server.py` (via MCP tool handlers)

## Error Handling

**Strategy:** Defensive — catch broadly, return error strings to the LLM rather than raising.

**Patterns:**
- Tool functions in `agent_runner.py` catch `(ValidationError, TypeError)` separately from `Exception` — the former for input validation, the latter for runtime errors:
  ```python
  try:
      result = fn(**tc.arguments)
  except (ValidationError, TypeError) as e:
      result = f"Validation error: {e}"
  except Exception as e:
      result = f"Tool error: {type(e).__name__}: {e}"
  ```
- BigQuery executor always returns a `QueryResult` object — never raises; errors captured in `QueryResult.error`
- MCP server catches all tool errors and returns them as text: `f"Tool error ({name}): {type(e).__name__}: {e}"`
- OCR agent uses `try/except Exception as e` and returns `f"[OCR ERROR: {e}]"` as the text
- No custom exception classes defined anywhere

**Validation errors:**
- Pydantic `ValidationError` from the `pydantic` library is the primary input validation mechanism
- SQL keyword blocklist validated before any BQ call via `validate_query()` returning `(bool, Optional[str])`

## Logging

**Framework:** Python standard library `logging`

**Setup pattern:**
```python
import logging
logger = logging.getLogger(__name__)
```
Used in every module (`agent_runner.py`, `bigquery_tool.py`, `snow_tool.py`, `wiki_tool.py`, `mcp_server.py`). Module-level `logger` created at import time.

**Initialization:**
- `logging.basicConfig(level=logging.INFO, format="%(message)s")` called in `main()` of `agent_runner.py` and `mcp_server.py`
- MCP server sends logging to `sys.stderr` to avoid contaminating the MCP stdio channel

**Log messages use bracketed prefixes:**
- `[BQ]` — BigQuery operations
- `[SNOW]` — ServiceNow operations
- `[WIKI]` — Wiki persistence
- `[MCP]` — MCP server events
- `[INIT]`, `[Step N]`, `[Act]`, `[Observe]`, `[Think]`, `[Done]` — Agent loop steps (via `print()`)

**Mix of `logger.*` and `print()`:**
- `logger.info/warning/error` for library-style module messages
- `print()` used in agent loop for live user feedback (progress indicators)

## Documentation / Docstrings

**Module-level docstrings:**
- Every `.py` file starts with a module docstring using a consistent 3-line header pattern:
  ```python
  """
  Module Name — Short Tagline
  ============================
  Longer description of purpose, architecture notes, and usage examples.
  """
  ```

**Class docstrings:**
- All classes have docstrings describing purpose and sometimes usage example
- `@dataclass` fields documented inline with comments, not per-field docstrings

**Method docstrings:**
- Public methods on classes have docstrings; private helpers (`_*`) sometimes do, sometimes don't
- Pydantic `Field(description=...)` used to document model fields — these double as LLM-visible parameter descriptions

**Inline comments:**
- Section separators `# ── Section ───────────────` used heavily to organize long files
- Significant logic blocks annotated with brief `# Step N: ...` comments (e.g., BQ executor's 3-step validation flow)

## Type Annotation Style

- `from __future__ import annotations` at top of core modules
- Function signatures annotated for parameters and return types
- `Optional[T]` from `typing` used (not `T | None` union)
- `list[dict]`, `dict[str, list[str]]` as parameterized generics (Python 3.9+ style)
- Pydantic models declare types inline on class body attributes
- `@dataclass` fields typed with class-level annotations

## Constants and Configuration

- Config entirely driven by `os.getenv()` with defaults baked in at `@dataclass` field level
- No hardcoded secrets; all credentials come from `.env` or environment variables
- `AgentConfig` in `rca_agent/config.py` is the single source of truth for all tunables
- `rca_copilot_agent/config.py` duplicates some config patterns (separate module, no LLM config)

---

*Convention analysis: 2026-04-24*
