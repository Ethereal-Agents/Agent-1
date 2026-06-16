## Description

This PR updates the agent's default language model configuration and explicitly forces the inclusion of local trajectory files and the metrics database into the repository for visibility and debugging purposes.

### Summary of Changes:
1. **Model Configuration:** 
   - Switched the `default_model` in `configs/default.yaml` from Gemini Flash Lite to Google's massive **Gemma 4 31B** (`gemini/gemma-4-31b`). This drastically increases the agent's reasoning capabilities.
2. **Trajectory Logging:**
   - Force-added the `runs/` directory (which was previously blocked by `.gitignore`) to source control.
   - Included all historical `.jsonl` execution trajectories.
   - Included the `metrics.db` SQLite database to allow developers to query historical agent performance, token usage, and API costs out-of-the-box.

### Motivation
With the introduction of the new `trajectory_viewer` app, having the `.jsonl` logs committed directly to the repository allows any team member to pull the branch, run the streamlit viewer, and immediately audit past agent behavior without needing to execute the agent locally. It also serves as a baseline set of test data for memory compaction and prompt caching evaluations.

### Impact & Testing
- **Impact:** Minimal operational impact. The agent now defaults to a heavier model, meaning token consumption costs will be higher but outputs will be substantially higher quality.
- **Testing:** No new tests required. The model string change is transparently handled by `litellm`. Trajectory logs have been validated and render correctly in the streamlit `trajectory_viewer/app.py`.
