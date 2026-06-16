import json
import os
import re

import streamlit as st

st.set_page_config(page_title="JSONL Trajectory Viewer", layout="wide", initial_sidebar_state="expanded")

st.sidebar.title("📁 File Explorer")

if "current_dir" not in st.session_state:
    st.session_state.current_dir = "/Users/ayushdubey/Downloads"

def change_dir():
    sel = st.session_state.dir_selector
    if sel == "..":
        st.session_state.current_dir = os.path.dirname(st.session_state.current_dir)
    elif sel:
        st.session_state.current_dir = os.path.join(st.session_state.current_dir, sel)

new_dir = st.sidebar.text_input("Current Path", value=st.session_state.current_dir)
if os.path.isdir(new_dir) and new_dir != st.session_state.current_dir:
    st.session_state.current_dir = new_dir
    st.rerun()

current_dir = st.session_state.current_dir

try:
    items = os.listdir(current_dir)
except Exception as e:
    st.sidebar.error(f"Cannot access directory: {e}")
    items = []

dirs = [".."] + sorted([d for d in items if os.path.isdir(os.path.join(current_dir, d)) and not d.startswith(".")])
jsonl_files = sorted([f for f in items if f.endswith(".jsonl")])

st.sidebar.selectbox("Navigate to Subdirectory", dirs, key="dir_selector", on_change=change_dir, index=None)

st.sidebar.divider()

if jsonl_files:
    selected_file = st.sidebar.radio("Select JSONL File", jsonl_files)
    file_path = os.path.join(current_dir, selected_file)
else:
    st.sidebar.info("No .jsonl files found in this directory.")
    file_path = None

st.title("🤖 Trajectory Viewer")

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
                _ = parts[idx] # 'thought' or 'thinking'
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
    if not file_path:
        st.info("👈 Please select a JSONL file from the sidebar to view its trajectory.")
