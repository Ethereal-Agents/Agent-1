# Survey of Prompt Caching Best Practices in Autonomous Agents

As Large Language Models increase their context windows, input token costs scale linearly with each step of an autonomous agent loop. "Prompt Caching" (pioneered by Anthropic and adopted by others like OpenAI and DeepSeek) allows agents to cache the static prefix of their prompts, yielding up to 90% cost savings and significantly reducing Time-To-First-Token (TTFT).

This document surveys how leading open-source agents implement prompt caching and distills their strategies into actionable best practices.

## 1. Core Principles of Prompt Caching

- **Prefix-Based Matching:** Caches are built top-down. If a single character changes early in the prompt, the entire cache below that point is invalidated.
- **Economics (Write vs. Read):** Writing to the cache generally incurs a slight premium (e.g., 1.25x base cost), while reading from the cache offers massive discounts (e.g., 0.10x base cost). An agent loop guarantees positive ROI because the exact same prefix is submitted repeatedly across many turns.
- **Token Thresholds:** Caching only activates if the prefix meets a minimum token threshold (typically 1,024 tokens for Anthropic). Small, simple agents will not benefit.
- **Breakpoint Limits:** Providers strictly limit the number of cache checkpoints (e.g., Anthropic allows a max of 4 `cache_control` blocks per request).

---

## 2. Survey of Leading Agent Implementations

### Aider
[Aider](https://aider.chat/) is a CLI-based AI pair programmer that extensively leverages prompt caching, particularly for Anthropic's Claude 3.5 Sonnet and Haiku models via the LiteLLM router.
- **Targeted Static Content:** Aider explicitly caches its massive, auto-generated **Repository Map** and any large **Read-Only Files** the user adds to the context. These items are placed at the very top of the prompt.
- **Keepalive Pings:** Anthropic's cache has a strict 5-minute Time-To-Live (TTL). Aider introduced a `--cache-keepalive-pings` flag. If the user steps away to think, Aider silently pings the API with a tiny request just to prevent the cached repo map from expiring.
- **Automatic Handling:** Aider abstracts the cache tags, automatically tagging the system instruction and repo map without user intervention.

### SWE-agent
[SWE-agent](https://swe-agent.com/) takes a highly configurable approach to caching, recognizing that its complex history truncation strategies can easily break cache prefixes.
- **Manual Breakpoints:** SWE-agent requires users to explicitly define cache checkpoints via `history_processors` in their YAML config:
  ```yaml
  history_processors:
    - type: cache_control
      last_n_messages: 2
  ```
- **The "History Elision" Caveat:** SWE-agent warns users that aggressive memory summarization plugins (like `last_n_observations`) fundamentally break prompt caching. Because `last_n_observations` continuously modifies the middle of the history array to save space, the prompt prefix changes every turn, leading to 0% cache hits.
- **Batching Workarounds:** Because Anthropic limits caching slots per API key, SWE-agent recommends running evaluations in batch mode on a single key to prevent concurrent workers from evicting each other's caches.

---

## 3. Recommended Prompt Architecture

Based on these tools, the industry standard for autonomous agents is the **Layered Architecture**. By rigidly separating static context from dynamic context, you maximize the cache hit rate.

### Layer 1: Global / System Layer (Cached)
**Content:** The master system prompt, core persona instructions, and the JSON schemas defining the available tools.
**Why:** This never changes during the entire lifecycle of the application.
**Action:** Place `cache_control: {"type": "ephemeral"}` at the very end of this block.

### Layer 2: Workspace Layer (Cached)
**Content:** The original user issue description, read-only documentation, or a static repository map.
**Why:** This defines the bounds of the current task. It won't change until the user issues a completely new high-level instruction.
**Action:** Place the second `cache_control` block at the end of this layer.

### Layer 3: Rolling Trajectory (Dynamically Cached / "Sliding Window")
**Content:** The history of agent thoughts and tool outputs.
**Why:** This grows every turn. 
**Action:** (Advanced) Place the third `cache_control` block dynamically on the `N-2` message in the history array. As the array grows, the checkpoint slides forward, writing the newly stabilized history to the cache and leaving only the absolute newest step to be processed un-cached.

### Layer 4: Active Session (Un-cached)
**Content:** The current turn, immediate scratchpad reasoning, and the latest tool error/output.
**Why:** This is highly dynamic and changes immediately on the next step. It should never be targeted for caching.

---

## 4. Key Takeaways for Implementation

1. **Protect the Prefix:** Never inject timestamps, random UUIDs, or dynamic variables into your System Prompt. 
2. **Handle Memory Compaction Carefully:** If your agent uses memory summarization (like a Sawtooth approach), understand that the moment you compress the middle of the history, the cache for everything below the compression point is destroyed and must be rebuilt (paying the 1.25x write penalty). Only trigger compaction when absolutely necessary.
3. **Monitor Cache Hit Rates:** Log `cached_tokens` versus `input_tokens` on every LiteLLM response. If your cached tokens are `0` after step 2, a dynamic variable has leaked into your static prefix.
