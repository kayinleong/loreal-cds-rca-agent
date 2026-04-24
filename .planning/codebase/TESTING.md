# Testing Analysis

## Status: NO TESTS EXIST

Zero test files in the project source tree. All test-related Python files found are inside `.venv/` (third-party packages). There is no `tests/`, `test/`, or `__tests__/` directory anywhere.

---

## Test Framework
- **None configured** — no pytest.ini, setup.cfg [tool:pytest], or pyproject.toml [tool.pytest.ini_options]
- pytest is not listed in any requirements.txt

## Test Directory Structure
```
(none — no test directories or files)
```

## What Is Tested

| Area | Status |
|------|--------|
| RCA agent ReAct loop (agent_runner.py) | Not tested |
| BigQuery tool (rca_agent/tools/bigquery_tool.py) | Not tested |
| ServiceNow tool (rca_agent/tools/snow_tool.py) | Not tested |
| Wiki pattern tool (rca_agent/tools/wiki_tool.py) | Not tested |
| LLM provider abstraction (llm_providers.py) | Not tested |
| OCR agent (snow_image_ocr_agent.py) | Not tested |
| Data models (models.py) | Not tested |
| Config loading (config.py) | Not tested |
| rca_copilot_agent/ (all files) | Not tested |

## Known Broken: Gemini Tool-Calling
Per project memory, **Gemini tool-calling is broken**. With no tests, this is:
- Undetected by CI
- Uncatchable on regression
- Likely silently broken whenever Gemini is selected as LLM provider

The breakage is probably in `llm_providers.py` where tool schemas are serialized — Gemini's function-calling format differs from OpenAI's.

## How to Run Tests
```bash
# Nothing to run — no tests exist
pytest  # would fail: ModuleNotFoundError: No module named 'pytest'
```

## Coverage
**0%** — no measurement possible.

---

## Recommended Test Setup

```bash
# Install test dependencies
pip install pytest pytest-mock pytest-asyncio

# Create test structure
mkdir -p tests/unit/tools tests/integration
touch tests/__init__.py
touch tests/unit/__init__.py tests/unit/tools/__init__.py
touch tests/integration/__init__.py
```

## Priority Test Gaps

### P0 — Gemini Tool-Calling Regression
The known broken behavior should be the first test written:
```python
# tests/unit/test_llm_providers.py
def test_gemini_tool_calling_sends_correct_schema():
    # Regression test: Gemini requires different tool schema format than OpenAI
    ...
```

### P1 — Core ReAct Loop
- Tool dispatch and result injection
- Termination conditions (max iterations, final answer found)
- Error handling when a tool fails

### P2 — Tool Functions (with mocks)
- `bigquery_tool.py`: mock BigQuery client, verify SQL generation
- `snow_tool.py`: mock HTTP responses, verify incident parsing
- `wiki_tool.py`: test pattern matching against known wiki_state.json fixtures

### P3 — Integration
- End-to-end investigation with a known incident fixture
- Prompt template rendering
- Config loading from environment variables
