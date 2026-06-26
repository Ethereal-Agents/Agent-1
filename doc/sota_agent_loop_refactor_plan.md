# Implementation: Agent Loop "Guided Autonomy" Architecture

## Objective
Migrate the agent's termination logic from a rigid, framework-enforced `submit_patch` validation cycle to a "Guided Autonomy" approach. The agent is responsible for manually running targeted tests, reasoning about failures, and explicitly signaling task completion using a `finish` tool. The framework provides a pre-existing failure baseline and a "soft nudge" guardrail against premature termination.

## Implemented State vs. Previous State

| Feature | Previous State | Implemented State |
| :--- | :--- | :--- |
| **Termination Signal** | `submit_patch` tool or "no tools called" | Explicit `finish` tool. |
| **Verification** | Framework intercepts `submit_patch` and runs full test suite automatically. | Agent manually runs tests using the `run_tests` tool before finishing. Framework captures a baseline of pre-existing failures to guide the agent. |
| **Failure Handling** | Framework forces the agent to fix *any* test failure via `get_test_failure_prompt` forced re-entry. | Agent decides relevance of test failures. System prompt instructs agent to fix related failures and ignore unrelated/pre-existing ones. |
| **Submission Limits** | Hardcapped by `MAX_SUBMISSIONS` (e.g., 3 attempts), creating artificial scarcity. | Removed. Bounded only by the overarching `MAX_STEPS` and budget constraints. |
| **Termination Guardrail** | Hard gating — impossible to finish if any unrelated test fails. | "Soft nudge" — if the agent calls `finish` without running tests, the framework nudges it once to reconsider. If it calls `finish` again, it is accepted. |

---

## Implementation Details

### 1. Pre-Existing Failure Baseline
To prevent the agent from rabbit-holing on pre-existing test failures, the framework now runs the full test suite *once* before the agent loop starts to capture a baseline.
* **Component**: `agent/loop.py` -> `Agent._capture_test_baseline()`
* **Mechanism**: This baseline of failing tests is injected directly into the initial user prompt, giving the agent ground truth on what it is NOT responsible for fixing.

### 2. The `finish` Tool
A new explicit completion tool evolved from the existing (but unused) `submit.py` tool.
* **Component**: `tools/finish.py` -> `FinishTool`
* **Mechanism**: When called successfully, it automatically stages changes, generates a `fix.patch`, and provides a final summary to signal successful task completion. The old `submit_patch` tool was completely removed.

### 3. "Soft Nudge" Guardrail
We replaced framework-forced re-entry with a "Guided Autonomy" single-nudge pattern to prevent premature termination.
* **Component**: `agent/loop.py` -> `Agent._process_tools()`
* **Mechanism**: If the agent calls `finish` but hasn't run any tests (`self.has_run_tests == False`), the framework intercepts it *once* and returns a `[NOTE]` observation advising verification. If the agent is confident and calls `finish` a second time, it is accepted and the loop terminates.

### 4. System Prompt Overhaul
The prompt was rewritten to provide explicit guidance on targeted testing and when to stop.
* **Component**: `prompts/system_prompt.txt`
* **Key Directives Added**:
  * **Stay Focused**: "Do NOT fix unrelated code... or address pre-existing problems."
  * **Targeted Testing**: Explicitly instruct the agent to run *targeted test paths* rather than the full suite, minimizing exposure to unrelated failures.
  * **Selective Effort**: Clarified that "one successful targeted test run is sufficient. Do not over-verify."

### 5. Config & Framework Cleanup
Removed the restrictive submission caps and the conflicting prompt injection logic that forced the agent into over-verification loops.
* **Component**: `config.py`, `configs/default.yaml`
* **Removed**: `MAX_SUBMISSIONS`, `get_test_failure_prompt`, and associated file paths.
