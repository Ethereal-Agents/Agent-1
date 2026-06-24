import json
import os
import re

import streamlit as st

st.set_page_config(
    page_title="JSONL Trajectory Viewer", layout="wide", initial_sidebar_state="expanded"
)

st.sidebar.title("🏃 Run Explorer")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE_DIR = os.path.join(PROJECT_ROOT, "eval_results")

if "base_dir" not in st.session_state:
    st.session_state.base_dir = DEFAULT_BASE_DIR

new_dir = st.sidebar.text_input("Base Directory (e.g. eval_results)", value=st.session_state.base_dir)
if new_dir != st.session_state.base_dir:
    st.session_state.base_dir = new_dir
    st.rerun()

BASE_DIR = st.session_state.base_dir

if not os.path.exists(BASE_DIR):
    st.sidebar.error(f"Directory not found at {BASE_DIR}")
    st.stop()

items = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
items = sorted(items, key=lambda d: os.path.getmtime(os.path.join(BASE_DIR, d)), reverse=True)

if not items:
    st.sidebar.info("No items found in the base directory.")
    st.stop()

selected_item = st.sidebar.selectbox("Select Experiment / Run", items, index=0)
item_path = os.path.join(BASE_DIR, selected_item)
trajectories_dir = os.path.join(item_path, "trajectories")

if os.path.exists(trajectories_dir):
    instances = [d for d in os.listdir(trajectories_dir) if os.path.isdir(os.path.join(trajectories_dir, d))]
    instances = sorted(instances, key=lambda d: os.path.getmtime(os.path.join(trajectories_dir, d)), reverse=True)
    
    if not instances:
        st.sidebar.info("No instances found.")
        st.stop()
        
    selected_run = st.sidebar.selectbox("Select Instance (SWE Bench ID)", instances, index=0)
    run_path = os.path.join(trajectories_dir, selected_run)
else:
    selected_run = selected_item
    run_path = item_path

file_path = os.path.join(run_path, "trajectory.jsonl")
config_path = os.path.join(run_path, "config.json")

# Handle double-nested instance directories gracefully
if not os.path.exists(file_path):
    nested_file_path = os.path.join(run_path, selected_run, "trajectory.jsonl")
    if os.path.exists(nested_file_path):
        file_path = nested_file_path
        config_path = os.path.join(run_path, selected_run, "config.json")

st.title("🤖 Trajectory Viewer")

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        try:
            config_data = json.load(f)
            with st.expander("⚙️ Run Configuration", expanded=False):
                st.json(config_data)
        except json.JSONDecodeError:
            pass

def generate_summary(traj_path, test_out_path, patch_path, passed, out_path):
    prompt = f"""You are an expert AI debugger and evaluation analyst. Your task is to analyze a completed autonomous agent run and provide a comprehensive post-mortem summary. The user relies on your summary entirely to understand what happened—do not force them to read the raw logs.

Here are the absolute paths to the data you need to read:
1. Trajectory (Agent's thoughts and actions): {traj_path}
2. Test Output (The final evaluation results): {test_out_path if test_out_path else 'NOT AVAILABLE'}
3. Final Patch (What the agent actually changed): {patch_path if patch_path else 'NOT AVAILABLE'}
4. Run Status: {'PASSED' if passed is True else 'FAILED' if passed is False else 'UNKNOWN (Evaluation not run yet)'}

Read these files carefully using your tools, and then create a markdown file at `{out_path}` following this EXACT structure:

### 🎯 Task & Outcome
* **Goal:** Briefly state the bug or feature the agent was trying to solve.
* **Outcome:** {'✅ Passed' if passed else '❌ Failed'}

### 🛠️ The Agent's Approach
* Summarize the high-level steps the agent took (e.g., "Explored `models.py`, found the issue in `save()`, and attempted to add a null check").
* What was the core logic of its attempted solution?

### 🚨 Root Cause Analysis (CRITICAL SECTION)
* **What happened in the tests:** Summarize the specific errors or failed assertions from the Test Output (if available). If test output is NOT AVAILABLE, analyze the final state of the agent's trajectory to explain if it seemed to solve the problem, got stuck, or gave up.
* **Why the agent failed (or struggled):** Correlate the outcomes with the agent's reasoning in the trajectory. 
    * If it failed: Did it hallucinate a non-existent function? Did it misunderstand the codebase architecture? Did it get stuck in an endless loop of fixing syntax errors? Did it solve the wrong problem?
    * If it passed: Did it go down any rabbit holes or waste significant time before finding the right answer?

### 💡 Takeaways & Optimization
* What should the agent have done differently?
* How could the agent's system prompt or tooling be improved to prevent this specific failure mode in the future?

Do not just dump raw logs into the summary. Synthesize the information into clear, insightful, human-readable bullet points.
"""
    import subprocess
    import os
    import fcntl
    import time

    cmd = [
        "agy", "--print", prompt, "--dangerously-skip-permissions", "--print-timeout", "15m"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    
    # Make stdout non-blocking
    fd = process.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    while process.poll() is None:
        try:
            chunk = process.stdout.read(1024)
            if chunk:
                yield chunk
        except (TypeError, BlockingIOError):
            pass
        time.sleep(0.1)

    # Read any remaining output after process exits
    try:
        chunk = process.stdout.read()
        if chunk:
            yield chunk
    except (TypeError, BlockingIOError):
        pass

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"agy execution failed with exit code {return_code}")

st.header("📋 Run Summary")
summary_path = os.path.join(run_path, "run_summary.md")
if os.path.exists(summary_path):
    with open(summary_path, "r", encoding="utf-8") as f:
        st.markdown(f.read())
else:
    experiment_path = os.path.dirname(os.path.dirname(run_path))
    results_json_path = os.path.join(experiment_path, "results.json")
    can_generate = True  # Always allow generation based on trajectory
    passed = None
    test_out_path = ""
    patch_path = ""
    
    if os.path.exists(results_json_path):
        with open(results_json_path, "r", encoding="utf-8") as f:
            try:
                results = json.load(f)
                instance_data = next((r for r in results if r.get("instance_id") == selected_run), None)
                if instance_data:
                    model_path = instance_data.get("model_name_or_path", "")
                    model_mangled = model_path.replace("/", "__")
                    experiment_name = os.path.basename(experiment_path)
                    
                    logs_dir = os.path.join(PROJECT_ROOT, "logs", "run_evaluation", experiment_name, model_mangled, selected_run)
                    test_out_path = os.path.join(logs_dir, "test_output.txt")
                    patch_path = os.path.join(logs_dir, "patch.diff")
                    
                    report_json_path = os.path.join(logs_dir, "report.json")
                    if os.path.exists(report_json_path):
                        with open(report_json_path, "r", encoding="utf-8") as rf:
                            report_data = json.load(rf)
                            passed = report_data.get(selected_run, {}).get("resolved", False)
                else:
                    st.warning(f"Note: Instance '{selected_run}' not found in results.json. Summary will be based only on trajectory.")
            except Exception as e:
                st.warning(f"Could not parse results.json: {e}")
    else:
        st.info(f"Note: Evaluation results not found. Generating summary based on trajectory only.")

    if can_generate:
        if st.button("🧠 Generate AI Run Summary"):
            import time
            with st.status("🧠 Generating summary using agy headless CLI... (This takes 2-5 minutes)", expanded=True) as status:
                log_placeholder = st.empty()
                logs = ""
                last_update = time.time()
                try:
                    for chunk in generate_summary(file_path, test_out_path, patch_path, passed, summary_path):
                        logs += chunk
                        # Throttle UI updates to twice a second to prevent Streamlit from freezing
                        if time.time() - last_update > 0.5:
                            log_placeholder.code(logs)
                            last_update = time.time()
                    
                    log_placeholder.code(logs) # final flush
                    status.update(label="Summary generated successfully!", state="complete", expanded=False)
                    st.rerun()
                except Exception as e:
                    status.update(label="Failed to generate summary.", state="error", expanded=True)
                    st.error(f"Error generating summary: {e}")
    else:
        st.info("Could not resolve test outputs to generate summary automatically. Ensure you are viewing runs from eval_results.")

st.divider()


def render_assistant_content(content_str):
    thought_pattern = re.compile(r"<(thought|thinking)>(.*?)</\1>", re.DOTALL)
    parts = thought_pattern.split(content_str)

    if len(parts) > 1:
        idx = 0
        while idx < len(parts):
            if parts[idx].strip():
                st.markdown(parts[idx])
            idx += 1

            if idx < len(parts):
                _ = parts[idx]  # 'thought' or 'thinking'
                idx += 1

                if idx < len(parts):
                    thought_content = parts[idx]
                    with st.expander("💭 Thinking Process", expanded=True):
                        st.markdown(thought_content)
                    idx += 1
    else:
        if content_str.strip():
            st.markdown(content_str)


def parse_tool_output(content_str):
    # Try to extract stdout, stderr, exit_code
    stdout_match = re.search(r"<stdout>\n?(.*?)\n?</stdout>", content_str, re.DOTALL)
    stderr_match = re.search(r"<stderr>\n?(.*?)\n?</stderr>", content_str, re.DOTALL)
    exit_code_match = re.search(r"<exit_code>\n?(.*?)\n?</exit_code>", content_str, re.DOTALL)

    if stdout_match or stderr_match or exit_code_match:
        if stdout_match and stdout_match.group(1).strip():
            st.markdown("**Standard Output**")
            st.code(stdout_match.group(1).strip(), language="bash")
        if stderr_match and stderr_match.group(1).strip():
            st.markdown("**Standard Error**")
            st.code(stderr_match.group(1).strip(), language="bash")
        if exit_code_match:
            exit_code = exit_code_match.group(1).strip()
            color = "green" if exit_code == "0" else "red"
            st.markdown(f"**Exit Code:** :{color}[{exit_code}]")
    else:
        # Render as raw text/code
        # Might be JSON
        if content_str.strip().startswith("{") or content_str.strip().startswith("["):
            try:
                formatted_json = json.dumps(json.loads(content_str), indent=2)
                st.code(formatted_json, language="json")
                return
            except json.JSONDecodeError:
                pass
        st.code(content_str, language="text")


if file_path and os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    st.sidebar.markdown(f"**Total Steps:** {len(lines)}")

    messages = []
    tool_calls_map = {}

    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = data.get("role", "unknown")
        if role == "assistant":
            for tc in data.get("tool_calls", []):
                tc_id = tc.get("id")
                if tc_id:
                    tool_calls_map[tc_id] = {"call": tc, "output": None}
            messages.append(data)
        elif role == "tool":
            tc_id = data.get("tool_call_id")
            if tc_id in tool_calls_map:
                tool_calls_map[tc_id]["output"] = data
            else:
                messages.append(data)
        else:
            messages.append(data)

    for data in messages:
        role = data.get("role", "unknown")

        # parse content
        content = data.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, dict) and item.get("type") == "image_url":
                    text_parts.append("[Image URL Provided]")
                else:
                    text_parts.append(str(item))
            content_str = "\n".join(text_parts)
        else:
            content_str = str(content) if content else ""

        if role == "system":
            if "[MEMORY COMPACTION TRIGGERED]" in content_str:
                with st.chat_message("system", avatar="🗜️"):
                    st.warning("**Memory Compaction Triggered**")
                    with st.expander("View Compacted Summary", expanded=False):
                        st.markdown(content_str.replace("[MEMORY COMPACTION TRIGGERED]\n", ""))
            else:
                with st.chat_message("system", avatar="⚙️"):
                    st.markdown("**System Instructions**")
                    with st.expander("Show System Prompt"):
                        st.markdown(content_str)
        elif role == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(content_str)
        elif role == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                render_assistant_content(content_str)

                tool_calls = data.get("tool_calls", [])
                for tc in tool_calls:
                    tc_id = tc.get("id")
                    func = tc.get("function", {})
                    name = func.get("name", "unknown_tool")
                    args = func.get("arguments", "")

                    tool_out_data = tool_calls_map.get(tc_id, {}).get("output")

                    with st.expander(f"🛠️ Tool: `{name}`", expanded=True):
                        st.markdown("**Input:**")
                        try:
                            formatted_args = json.dumps(json.loads(args), indent=2)
                            st.code(formatted_args, language="json")
                        except Exception:
                            st.code(args, language="json")

                        if tool_out_data:
                            st.markdown("**Output:**")
                            parse_tool_output(tool_out_data.get("content", ""))
        elif role == "tool":
            name = data.get("name", "unknown_tool")
            with st.chat_message("tool", avatar="🔧"):
                with st.expander(f"📥 Orphaned Tool Output: `{name}`", expanded=False):
                    parse_tool_output(content_str)
        else:
            with st.chat_message(role):
                st.markdown(content_str)
else:
    st.info(f"👈 No trajectory.jsonl found in run directory: {selected_run}")
