## Description

This PR brings the core Agent-1 engine to functional maturity by introducing a robust ReAct agent loop, SWE-bench compliant tooling, robust memory management, and complete end-to-end telemetry.

### 🚀 Core Features & Agent Loop
- Built the main `Agent` execution loop (`agent/loop.py`) to process multi-turn interactions.
- Implemented **100% test-covered** SWE-bench compliant tools (`bash`, `file_ops`, `search`, `run_tests`, `submit_patch`).
- Built a command-line entrypoint (`main.py`) using `argparse` to launch the agent against arbitrary directories (`--dir`), models (`--model`), and instances (`--instance-id`).

### 🧠 Memory Management & Cost Optimization
- **Prompt Caching:** Engineered a 3-layer Anthropic-style prompt caching system. Implemented static caching on the System Prompt and Issue Description, plus a **Rolling Sliding Window Cache** on the `N-2` trajectory message to achieve up to 90% cost reduction on long sequences.
- **Sawtooth Compaction:** Built a dynamic memory truncation system to summarize history once it hits the `compaction_threshold`. Includes a critical patch to guarantee the truncated tail strictly begins with an `assistant` message, eliminating Anthropic API `Unexpected tool_use_id` crashes.

### 📊 Telemetry, Configurations & Analytics
- **Configuration:** Transitioned configuration to `configs/default.yaml` and `.env`, upgrading the default execution model to **Gemma 4 31B** (`gemini/gemma-4-31b`).
- **Trajectory Logging:** Built `memory/trajectory.py` to output deterministic `.jsonl` files for every run, completely compatible with the newly merged `trajectory_viewer` app.
- **SQLite Analytics:** Automatically tracks `total_steps`, `total_tokens`, `cost` (using LiteLLM's `completion_cost`), and `duration_seconds` into a persistent `runs/metrics.db`.
- **Data Science Integration:** Pushed two interactive Jupyter Notebooks (`notebooks/visualize_metrics.ipynb` and `notebooks/visualize_swe_lite.ipynb`) with Pandas/Seaborn visualization scripts for tracking agent ROI over time.

### ✅ Testing & CI
- **100% Code Coverage:** Verified via `pytest-cov`.
- Created robust test mocks for `litellm` network calls to validate prompt cache tagging without incurring network fees.
- Un-ignored the `runs/` tracking path to strictly source-control agent baselines.
