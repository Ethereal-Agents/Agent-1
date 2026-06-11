# ReAct Loop Implementation Plan & Agent Analysis

## 1. In-Depth Analysis: How Existing Coding Agents Implement the ReAct Loop

To build the most effective loop for `recall-agent`, we first analyze the design patterns of state-of-the-art coding agents (circa 2024-2026), focusing strictly on their control flow and ReAct implementation.

### A. The "Rich ACI" Approach (e.g., SWE-agent)
* **Loop Style:** Standard ReAct (Reason -> Act -> Observe).
* **Key Characteristic:** Heavy investment in the "Agent-Computer Interface" (ACI). The agent interacts with a stateful windowed file viewer, specialized linting tools, and a custom bash emulator rather than raw tools.
* **Takeaway:** While the custom tool environment prevents common errors (like editing the wrong line), recent findings suggest that with stronger models (like Claude 3.5 Sonnet or newer), the elaborate scaffolding yields diminishing returns.

### B. The "Bare Metal" Approach (e.g., mini-swe-agent)
* **Loop Style:** Minimal bash-driven ReAct loop.
* **Key Characteristic:** ~100 lines of Python wrapping a basic LLM call that executes raw bash commands.
* **Takeaway:** Proves that **model capability dominates scaffolding**. A strong model can navigate standard Linux tools without needing a bespoke UI built for it. We adopt this minimalism but add typed tool-calling for better observability and cacheability.

### C. The "Triad / Multi-Agent" Approach (e.g., OpenHands / AutoGPT variants)
* **Loop Style:** Delegated ReAct (Planner -> Executor -> Critic).
* **Key Characteristic:** Instead of a single loop, a "Planner" creates steps, an "Executor" runs a ReAct loop on each step, and a "Critic" evaluates the result.
* **Takeaway:** Token-heavy and slow. As noted in Anthropic's "Building Effective Agents", adding full critic/planner nodes is premature complexity unless the task length explicitly demands it. We reject this for a single ReAct loop, saving budget.

### D. The "Pipeline" Approach (e.g., AgentLess)
* **Loop Style:** No continuous loop (or highly constrained).
* **Key Characteristic:** Breaks the problem into a rigid pipeline: Localize -> Generate Candidates -> Validate -> Select.
* **Takeaway:** Extremely cheap and predictable, but brittle for tasks that genuinely require exploratory debugging. We borrow their "localization-first" idea (our pre-step) but maintain a ReAct loop for the actual editing.

### E. The "Bounded Reflection" Approach (Our Design)
* **Loop Style:** Single ReAct loop with a hard cap + execution-based verifier.
* **Key Characteristic:** The agent iterates until it proposes a patch. Then, the loop breaks, a test suite runs, and the agent gets a *strictly bounded* number of attempts (e.g., 2) to reflect on the test failures and try again.

---

## 2. The `recall-agent` Implementation Plan

Based on the design document, our `recall-agent` loop avoids complex triads and instead relies on **native tool calling**, **SQLite memory**, and **anchored summarization**.

### Architecture of the Loop

1. **Initialization:**
   * Load the **System Prompt** (rules, formatting, available mocked tools).
   * Seed the context with the **Issue Description** and the results of the **Localizer** (candidate files).
   
2. **The Core Loop (While `step_count < 30`):**
   * **Reason & Act:** Call LiteLLM to seamlessly route to Anthropic, Gemini, or OpenRouter with the current conversation history. The model outputs a thought block and requests a tool call (native API tools unified by LiteLLM).
   * **Observe (Mocked):** Execute the requested tool against our `mock_tools` module.
   * **Log:** Write the state, token usage, and tool output to the SQLite trajectory log.
   * **Compact:** If the token limit approaches, trigger **Anchored Summarization** (keep the issue, first few steps, and last few steps; summarize the middle).

3. **Verification, State, & Self-Reflection:**
   * **State Ownership:** The core ReAct loop (`agent/loop.py`) maintains all state, including the 3-submission cap. We do NOT use a separate orchestration verifier script.
   * **Exploratory TDD vs Final Submission:**
     * `run_tests`: Can be called freely by the agent for intermediate TDD checks. It internally uses a cheap sub-LLM to parse messy raw stdout into clean XML.
     * `submit_patch`: A dummy schema tool that signals final completion. Calling it triggers the full test suite and increments the submission counter.
   * **The Reflection Flow:** 
     * If tests pass: The loop appends a `[SUCCESS]` tool message, allowing the LLM to generate a final conversational summary before gracefully halting.
     * If tests fail: The loop appends the XML test logs back to the LLM. The Main Agent naturally uses **Self-Reflection** (leveraging its existing full memory of the codebase) to course-correct. This completely avoids the "context-loss" problem found in isolated Critic nodes.
   * If the `submit_patch` cap (3) is reached, a `[HARD STOP]` message is appended and the loop halts.

### Implementation Steps (What to code next)

**Phase 1: Mocked Tools & Schemas (`tools/mock.py`)**
* Define Pydantic schemas for our required tools (`bash`, `read_file`, `write_file`, `edit`, `code_search`, `run_tests`, `arxiv_scholar`).
* Create dummy implementations that return hardcoded or simple string responses so the ReAct loop can be tested in isolation.

**Phase 2: Trajectory Logging (`memory/sqlite_log.py`)**
* Set up a simple SQLite table to store `(step_id, role, content, tool_calls, tokens, timestamp)`.
* This ensures we have our evaluation data source ready from day 1.

**Phase 3: The Core Agent (`agent/loop.py`)**
* Implement the main `run_agent(task)` function.
* Setup the LiteLLM router (using standard OpenAI message formats) and the history array.
* Write the `while` loop that handles the API response, parses tool calls, invokes the mocks, and appends the observations back to the history array.
* Add Prompt Caching headers (supported by LiteLLM for Anthropic/Gemini) to the system prompt and stable early turns to keep costs near zero during development.

**Phase 4: Inner-Loop Bounded Reflection (`agent/loop.py`)**
* Implement the interception logic for `submit_patch` directly inside the ReAct loop.
* Track the submission counter internally.
* Implement the sub-LLM step within `run_tests` to format the test stdout into LLM-readable XML before returning it to the Main Agent.
