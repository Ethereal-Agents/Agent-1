# Survey of Memory Compaction in SOTA Coding Agents

When a ReAct loop runs for 30 steps, dumping massive file reads and test logs into the context window, it rapidly hits the LLM's token limit. Even before hitting the limit, "LLM Amnesia" occurs—the model forgets the original instructions at the top of the prompt. Here is how State-of-the-Art agents solve this.

## 1. SWE-agent
**Strategy:** Output Truncation & Implicit Forgetting
SWE-agent does not explicitly summarize the context window. Instead, it strictly truncates tool outputs. If a file read returns 10,000 lines, SWE-agent truncates it to the first 100 lines and appends `[... truncated ...]`. They rely on the massive context window of Claude to hold the remaining history.

## 2. AgentLess
**Strategy:** Pipeline Isolation
AgentLess completely avoids the infinite-growing context problem by not using a single ReAct loop. It breaks the task into isolated nodes:
- Localizer LLM: Gets the issue, outputs file paths. (Context cleared).
- Editor LLM: Gets the issue + file paths, outputs patches. (Context cleared).
Because the history never carries over, memory compaction is unnecessary.

## 3. MemGPT
**Strategy:** Paging Architecture
MemGPT introduces an operating-system-like paging mechanism. It has a "Main Context" (the LLM's active prompt) and an "External Database". When the context gets full, it forces the LLM to use a `archive_memory` tool to push older thoughts into the database, freeing up the active prompt.

## 4. Anthropic's "Sawtooth" Pattern (Best Practice for Single-Loop)
**Strategy:** Anchored Summarization
Anthropic recommends the "Sawtooth" memory pattern for long-running single loops. 
- **The Anchor:** The System Prompt and the original User Task are permanently pinned to the top of the history.
- **The Tail:** The last `N` steps (e.g., the last 5 tool calls) are kept intact so the agent remembers what it just did.
- **The Middle:** Everything in between is periodically collapsed into a dense summary.
This ensures the prompt size grows like a sawtooth (rises, gets compressed, falls, rises again) but the model never forgets its primary goal.

---

## Conclusion & Implementation for `recall-agent`
For `recall-agent`, we are using a single ReAct loop on a strict budget. The **Sawtooth pattern** is perfectly aligned with our architecture. We will implement a trigger: if the `history` array exceeds a certain length (e.g., 15 messages), we will pin the first 2 messages and the last 5, and compress the middle into a single summary block.
