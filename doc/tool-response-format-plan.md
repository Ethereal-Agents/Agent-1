# Phase 1: Tool Response Formatting & Schema Plan

## 1. Survey of State-of-the-Art Tool Observation Formats (2024–2026)

When an LLM executes a tool, the format of the resulting "observation" string critically impacts whether the agent successfully iterates or spirals into a retry loop. Our survey of current coding agents and literature highlights several proven patterns.

### A. SWE-agent & The Agent-Computer Interface (ACI)
* **Finding:** Raw Linux terminal output is "hostile" to LLMs. Terminals lack pagination memory and dump thousands of lines, polluting context.
* **Approach:** SWE-agent introduced the ACI. When a file is opened, it returns a fixed window (e.g., 100 lines) preceded by a header: `[File: src/main.py (100 lines total)]`. It explicitly tells the model how to scroll.
* **Format Takeaway:** Always provide contextual headers (file name, total size) and line numbers. 

### B. Aider & Search/Replace Editing
* **Finding:** Agents frequently hallucinate code replacements, leading to "string not found" errors.
* **Approach:** When an edit fails, Aider doesn't just say "Failed." It returns the closest fuzzy-matched block in the file and says: `Error: Could not find exact match. Did you mean this block: ...`
* **Format Takeaway:** Edit tools must return highly actionable diffs or fuzzy-match hints on failure.

### C. JetBrains Observation-Masking Study (2025)
* **Finding:** Dumping raw `stderr` or full test suite outputs degrades next-step accuracy by up to 18% due to the "lost in the middle" phenomenon.
* **Approach:** Use structured summarization. Wrap the test output in XML tags and separate the *test names* from the *tracebacks*.
* **Format Takeaway:** Use XML tags (`<test_results>`, `<failure_trace>`) to structure large multi-part outputs. LLM attention mechanisms natively segment XML effectively.

### D. Zylos "LLM-Readable Errors" (2026)
* **Finding:** 60% of agent death-spirals (infinite loops) are caused by opaque error messages like `Exit code 1`. The agent blindly guesses the fix.
* **Approach:** Standardize all tool errors into a tripartite format: `[Error Type] + [Offending Input] + [Corrective Hint]`.
* **Format Takeaway:** Explicitly encode hints into the tool return string (e.g., `Hint: You tried to read line 500, but the file only has 200 lines.`).

---

## 2. Core Formatting Principles for `recall-agent`

For your teammate implementing the mocked (and eventually real) tools, every tool response must adhere to these four rules:

1. **Strict Truncation with Actionable Footers:** Never return more than ~2,000–3,000 characters. If output is truncated, append exactly: `\n...[OUTPUT TRUNCATED. Use search or pagination tools to see more]`.
2. **Mandatory 1-Indexed Line Numbers:** Any tool returning source code (`read_file`, `code_search`) must prefix lines with `14: ` (line number, colon, space). This is non-negotiable for the `edit` tool to function.
3. **Tripartite Error Strings:** Catch all exceptions at the tool boundary. Never return a raw Python stack trace to the LLM. Return: `ERROR: <reason>\nATTEMPTED: <input>\nHINT: <how to fix>`.
4. **XML Tagging for Metadata:** Wrap structured results in `<tag>` blocks so the LLM can easily parse them during the ReAct reasoning step.

---

## 3. Tool-by-Tool Implementation Plan (Phase 1 Specifications)

Here is exactly how the response strings should be structured for each mocked tool.

### 1. `read_file(path, start_line, end_line)`
* **Success Format:**
  ```text
  [FILE: src/utils.py | Showing lines 10-15 of 150]
  10: def add(a, b):
  11:     """Adds two numbers."""
  12:     return a + b
  13: 
  14: def sub(a, b):
  15:     return a - b
  ```
* **Failure Format:** `ERROR: File 'src/utils.py' not found. HINT: Use the bash tool with 'ls' to check the directory contents.`

### 2. `edit(path, start_line, end_line, old_str, new_str)`
* **Success Format:**
  ```text
  [SUCCESS] Edited src/utils.py. 
  Applied diff:
  -    return a + b
  +    return float(a) + float(b)
  ```
* **Failure Format:** `ERROR: The old_str provided did not perfectly match the contents of src/utils.py between lines 10 and 15. HINT: Ensure you match whitespace perfectly. Use read_file to view the exact lines.`

### 3. `code_search(query, dir)`
* **Success Format:**
  ```text
  [SEARCH RESULTS for 'def add']
  <file path="src/utils.py">
  10: def add(a, b):
  </file>
  <file path="tests/test_utils.py">
  5: def test_add():
  </file>
  ```
* **Failure Format:** `No matches found for 'def add' in directory 'dir'.`

### 4. `bash(command)`
* **Success Format:**
  ```text
  <stdout>
  total 24
  drwxr-xr-x  5 user group  160 Jun 10 10:00 agent
  drwxr-xr-x  3 user group   96 Jun 10 10:00 tools
  </stdout>
  <exit_code>0</exit_code>
  ```
* **Failure Format:** Include `<stderr>` and `<exit_code>`. Truncate `<stdout>` if it exceeded the limit.

### 5. `run_tests(target)`
* **Success Format:** (Must mask raw dumps per JetBrains 2025)
  ```xml
  <test_run_summary>
    <status>FAILED</status>
    <total_passed>45</total_passed>
    <total_failed>1</total_failed>
  </test_run_summary>
  <failure_details>
    <test name="test_utils.test_add">
      AssertionError: expected 5.0, got 5
    </test>
  </failure_details>
  ```

### 6. `arxiv_scholar(query)` (The Differentiator)
* **Success Format:** 
  ```xml
  <retrieved_papers query="attention mechanism">
    <paper id="1706.03762">
      <title>Attention Is All You Need</title>
      <snippet>We propose a new simple network architecture, the Transformer, based solely on attention mechanisms...</snippet>
      <relevance_score>0.98</relevance_score>
    </paper>
  </retrieved_papers>
  ```

---
## Next Steps for the Teammate
1. Create `tools/mock.py`.
2. Define the exact Pydantic `BaseModel` args for these 6 tools to register with LiteLLM.
3. Write mock functions that return strings strictly matching the templates in Section 3.
