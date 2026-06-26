# Survey of SOTA Agent Trajectory Logging

This document summarizes how state-of-the-art coding agents handle trajectory logging and evaluation persistence, based on a survey of SWE-agent, OpenHands, and Aider.

## 1. SWE-agent
**Format:** `.traj` files (JSON format)
**Structure:** Each `.traj` file contains a list of execution steps under a `trajectory` key. Each step meticulously records:
- `thought`: The LLM's reasoning or monologue.
- `action`: The exact tool or command called.
- `observation`: The environment output/feedback.
- `state`: Localized environment information (e.g., current directory, active file).
- `query`: The exact prompt passed to the LLM at that specific turn.
**Organization:** Stored locally in nested directories: `trajectories/$USER/$EXPERIMENT_NAME/instance_id.traj`
**Tooling:** SWE-agent provides both a CLI (`sweagent inspect`) and a Web Inspector (`sweagent inspector`) to visualize and replay these JSON files effortlessly.

## 2. OpenHands (formerly OpenDevin)
**Format:** Event-sourced architecture (JSON/JSONL)
**Structure:** Uses an immutable, append-only log of events. Each event is a strongly-typed Pydantic model:
- `MessageEvent`: LLM or User text inputs/outputs.
- `ActionEvent`: Tool calls and environment interactions.
- `ObservationEvent`: Tool execution results.
- `ConversationStateUpdateEvent`: Internal state tracking.
**Organization:** Stored in a local persistence directory (`workspace/conversations/{id}/events/`) or streamed out via OpenTelemetry.
**Tooling:** Deep integration with observability platforms like Laminar, MLflow, and Honeycomb via standard OTLP backends for tracing and session replay.

## 3. Aider
**Format:** Conversational History & Git Commits
**Structure:** Rather than highly formalized schemas for every micro-action, Aider persists the literal conversation history array (standard OpenAI/Anthropic message arrays).
**Tooling:** Aider uniquely relies on **git history** as the ultimate "trajectory" of success. It automatically commits after successful steps, using the LLM's thought process as the commit message, effectively using the repo's native version control as the agent's timeline.

---

## Conclusion & Recommendation for `recall-agent`
Both SWE-agent and OpenHands heavily favor **JSON/JSONL** (or event-streams) over raw relational databases (like SQLite) for storing the raw trajectories. The primary reasons are:
1. **Portability:** JSON files can be trivially shared, zipped, and loaded into web-based visualization tools.
2. **Schema Flexibility:** As the LLM message standard evolves (e.g., adding tool-use blocks, multimodal inputs), JSON schemas adapt gracefully, whereas SQL schemas require rigid migrations.
3. **Diffing:** JSON files can be diffed easily.

**Recommendation:** Instead of only using a SQLite table, `recall-agent` should dump the final ReAct `history` array (which already maps perfectly to the OpenHands `Message/Action/Observation` structure) into a `.jsonl` or `.traj` file per instance in a `runs/` directory. We can still use a lightweight SQLite table, but strictly for tracking high-level metrics (pass/fail, token usage, cost, total duration) to build benchmark dashboards.
