# Extensive Testing Plan for `recall-agent`

## 1. Goal
Achieve **99% test coverage** with meaningful, distinct test scenarios for every component of the system. Avoid "junk" or completely redundant tests.

## 2. Directory Restructuring
We will reorganize `tests/` into domains matching the source tree:
- `tests/agent/` for the ReAct loop
- `tests/memory/` for trajectory logging
- `tests/tools/` for the various tool implementations
- `tests/test_config.py` for root configuration parsing

### Current state to target state:
- `tests/test_bash_and_run.py` -> Split into `tests/tools/test_bash.py` and `tests/tools/test_run_tests.py`
- `tests/test_file_ops.py` -> `tests/tools/test_file_ops.py`
- `tests/test_registry.py` -> `tests/tools/test_registry.py`
- `tests/test_search.py` -> `tests/tools/test_search.py`
- `tests/test_submit.py` -> `tests/tools/test_submit.py` & `tests/tools/test_submit_patch.py`

## 3. Component Test Scenarios

### A. Configuration (`config.py`)
- **T1:** Verify default configs fall back cleanly when `RECALL_CONFIG` is unset.
- **T2:** Verify `RECALL_CONFIG` loading works with custom `.yaml` paths.
- **T3:** Verify `get_system_prompt()` successfully reads from `prompts/system_prompt.txt`.

### B. Trajectory Memory (`memory/trajectory.py`)
- **T1:** Verify `init_db()` correctly sets up `metrics.db` and the schema.
- **T2:** Verify `save_trajectory()` correctly formats the JSONL history.
- **T3:** Verify `save_trajectory()` upserts metrics (cost, duration, steps) into the SQLite DB.
- **T4:** Verify graceful handling if the destination path doesn't initially exist.

### C. Agent ReAct Loop (`agent/loop.py`)
- **T1 (Standard Loop):** The agent correctly loops Reason -> Act -> Observe.
- **T2 (Tool Interception):** When `submit_patch` is called, the loop intercepts it and triggers `run_tests` natively.
- **T3 (Submission Success):** If `run_tests` yields `[SUCCESS]`, the loop acknowledges it without hard breaking prematurely.
- **T4 (Submission Failure):** If tests fail, it reflects the logs back to the LLM and keeps looping until `MAX_SUBMISSIONS`.
- **T5 (Max Steps):** When `step_count` exceeds `MAX_STEPS`, it breaks gracefully.
- **T6 (Sawtooth Compaction):** When history length > `COMPACTION_THRESHOLD`, it accurately summarizes the middle and keeps the anchor/tail.
- **T7 (Token Tracking):** Token accumulation and cost API handling via `litellm.completion_cost()`.
- **T8 (API Errors):** If LiteLLM throws an exception, the loop catches it and exits safely.

### D. Tools (`tools/*.py`)
- **T1 (Base & Utils):** `validate_args` handles valid JSON, missing args, extra args.
- **T2 (Bash):** Successful bash, syntax errors, timeout logic handling.
- **T3 (File Ops):** Reading non-existent files, editing valid/invalid ranges, creating directories.
- **T4 (Registry):** Ensuring `get_openai_tools()` correctly formats all Pydantic models.
- **T5 (Search):** Querying with and without regex, matching lines natively vs file list.
- **T6 (Run Tests):** Translating unstructured pytest outputs to LLM-friendly XML.

## 4. Execution Checklist
- [ ] Write `doc/testing-plan.md` (This file).
- [ ] Create folder structure (`tests/agent/`, `tests/memory/`, `tests/tools/`).
- [ ] Move existing tests and verify they pass (`pytest tests/`).
- [ ] Run `pytest --cov=. --cov-report=term-missing` to find the exact gaps.
- [ ] Write `tests/test_config.py`.
- [ ] Write `tests/memory/test_trajectory.py`.
- [ ] Refactor & expand `tests/tools/*.py`.
- [ ] Mock LiteLLM responses and write `tests/agent/test_loop.py`.
- [ ] Final coverage check (Target: > 99%).
