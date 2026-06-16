# ReAct Loop Implementation & Mechanics: SOTA Research & Plan

Before writing a single line of code for `agent/loop.py`, we must align our loop mechanics with the latest research on coding agent behavior. This document surveys how State-of-the-Art (SOTA) agents handle the literal `while` loop, context management, and token optimization, followed by a concrete implementation plan.

---

## 1. SOTA Research & Paper Survey

### A. Forcing the Reasoning Step (The `<thought>` Block)
* **Research / Papers:** "Reason-Plan-ReAct" (arXiv 2512.03560), Anthropic's "Building Effective Agents" (2026).
* **The Problem:** If an agent is allowed to output a tool call immediately, it often acts impulsively. 
* **SOTA Solution:** SOTA agents enforce a strict syntax where the LLM *must* generate a block of reasoning text before generating the JSON tool call. 
* **Implementation Detail:** In native tool calling (LiteLLM/OpenAI), the API naturally separates the `content` (reasoning) from `tool_calls`. Our loop must log the `content` string to understand *why* the agent did something.

### B. Context Management & The "Sawtooth" Pattern
* **Research / Papers:** "Memory for Autonomous LLM Agents" (arXiv 2603.07670), JetBrains 2025 Studies.
* **The Problem:** A ReAct loop can easily exceed 200,000 tokens if `read_file` dumps massive strings. Standard truncation deletes the original Issue Description (amnesia).
* **SOTA Solution:** The "Sawtooth Memory" or "Anchored Summarization" pattern. 
* **Implementation Detail:** 
  1. Pin the System Prompt and Issue Description to the top (Never delete).
  2. Pin the last ~5 steps to the bottom.
  3. When tokens > N, compress the *middle* steps into a summarized string: `[Steps 5-15: Explored the parser logic, found no bugs]`.

### C. Prompt Caching Economics
* **Research / Papers:** Anthropic API Guidelines (2024–2026).
* **The Problem:** On a 30-step loop, sending a 100k token context 30 times costs hundreds of dollars per SWE-bench run.
* **SOTA Solution:** Prefix caching.
* **Implementation Detail:** The system prompt, the AST map, and the initial rules must be marked as "cacheable" blocks. LiteLLM handles this, but we must ensure the *beginning* of the `history` array never changes, or else the cache is invalidated.

### D. Architectural Patterns (Event-Driven vs. Procedural)
* **OpenHands (OpenDevin):** Uses an asynchronous Event Stream. Every thought, tool call, and observation is an Event dispatched to a central bus. Highly scalable but overly complex for a single-agent budget.
* **mini-swe-agent:** Uses a basic Python `while` loop. The history is just a Python list appended to dynamically.
* **Our Choice:** We adopt the `mini-swe-agent` procedural approach for simplicity, utilizing the standard LiteLLM array structure: `[{"role": "user"}, {"role": "assistant", "tool_calls": [...]}, {"role": "tool", "content": "..."}]`.

---

## 2. Implementation Plan for `agent/loop.py`

Based on the research, here is the architectural plan for our ReAct loop. **(Do not implement yet).**

### Step 1: Initialization
1. Setup `litellm` (or OpenRouter/Anthropic).
2. Load the System Prompt (which includes the AST Map or BM25 Localizer results).
3. Initialize the `history` array.
4. Set `step_count = 0`, `submit_count = 0`.

### Step 2: The ReAct `while` Loop
```python
while step_count < MAX_STEPS (e.g., 30):
```

### Step 3: LLM Inference
* Call `litellm.completion` passing the `history` and `tools.get_openai_tools()`.
* Append the exact assistant response object to the `history` array (required by API rules).

### Step 4: Interception & Tool Dispatch
* Check if the LLM made a `tool_call`.
* **If tool == `submit_patch`:**
  * Increment `submit_count`.
  * If `submit_count >= 3`: Append `[HARD STOP]` and break loop.
  * Else: Execute `run_tests()`.
    * If success: break loop (Issue solved!).
    * If failure: Format the XML failure logs, append as a `tool` role message matching the `submit_patch` ID. The loop continues for Self-Reflection.
* **If tool is a standard tool (e.g., `read_file`):**
  * Call `tools.execute_tool(name, args)`.
  * Append the observation as a `tool` role message.
  * `step_count += 1`.

### Step 5: Memory Management (End of Loop Step)
* Track cumulative tokens using LiteLLM's usage stats.
* If `tokens > 100k`: Trigger a separate, cheap background LLM call to summarize steps `[3 to current_step - 5]`.
* Replace those middle dicts in the `history` array with a single `{"role": "user", "content": "Summary of steps: ..."}`.

### Step 6: Trajectory Logging
* After the loop terminates (either via success, cap limit, or error), dump the entire `history` array and token metrics to `memory/sqlite_log.py` for evaluation benchmarking.
