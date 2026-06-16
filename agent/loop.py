import json
import litellm
import time
from typing import List, Dict, Any
from tools.registry import get_openai_tools, execute_tool
from memory.trajectory import save_trajectory

from config import MAX_STEPS, MAX_SUBMISSIONS, COMPACTION_THRESHOLD, DEFAULT_MODEL, get_system_prompt

SYSTEM_PROMPT = get_system_prompt()

def run_agent(issue_description: str, model: str = DEFAULT_MODEL, instance_id: str = "test_run_001") -> List[Dict[str, Any]]:
    print(f"Starting recall-agent on model: {model}")
    start_time = time.time()
    
    # Initialize conversation history
    history: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Please fix the following issue:\n\n{issue_description}"}
    ]
    
    step_count = 0
    submit_count = 0
    cumulative_tokens = 0
    
    while step_count < MAX_STEPS:
        print(f"\n--- Step {step_count + 1} ---")
        
        # 1. Call LLM
        try:
            response = litellm.completion(
                model=model,
                messages=history,
                tools=get_openai_tools(),
            )
        except Exception as e:
            print(f"API Error: {e}")
            break
            
        # Track tokens
        if hasattr(response, 'usage') and response.usage:
            cumulative_tokens += getattr(response.usage, 'total_tokens', 0)
            
        message = response.choices[0].message
        
        # Append assistant's response exactly as provided by the API
        history.append(message.model_dump(exclude_none=True))
        
        # Print reasoning if available
        if message.content:
            print(f"\n[Reasoning]: {message.content.strip()}")
            
        # 2. Check for tool calls
        if not hasattr(message, 'tool_calls') or not message.tool_calls:
            print("\n[Agent finished. No tools called.]")
            break
            
        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}
                
            print(f"[Tool Call]: {tool_name}({tool_args})")
            
            # --- INTERCEPT submit_patch ---
            if tool_name == "submit_patch":
                submit_count += 1
                if submit_count >= MAX_SUBMISSIONS:
                    print(f"\n[HARD STOP] Submission cap ({MAX_SUBMISSIONS}) reached. Halting.")
                    observation = "[HARD STOP] Submission limit reached. Task failed."
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": observation
                    })
                    break  # Exit agent loop
                    
                print(f"Verifying patch (Attempt {submit_count}/{MAX_SUBMISSIONS})...")
                # Trigger the actual test suite to verify
                test_results = execute_tool("run_tests", {"target": "all"})
                
                if "[SUCCESS]" in test_results:
                    print("\n[SUCCESS] Tests passed! Patch successful.")
                    observation = "[SUCCESS] All tests passed! Please provide a final summary of what you fixed to the user, and do not call any more tools."
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": observation
                    })
                    # We let the loop continue so the LLM can generate a final conversational summary.
                else:
                    print("\n[FAILURE] Tests failed. Feeding back to agent for reflection.")
                    observation = f"TESTS FAILED. Please reflect and try again. Logs:\n{test_results}"
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": observation
                    })
                
                continue
                
            # --- STANDARD TOOLS ---
            observation = execute_tool(tool_name, tool_args)
            
            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": observation
            })
            
        step_count += 1
        
        # --- "Sawtooth" Memory Compaction ---
        # If history gets too long, compress the middle to prevent LLM amnesia and save tokens.
        if len(history) > COMPACTION_THRESHOLD:
            print("\n[Memory Compaction] Triggering Sawtooth compaction...")
            head = history[:2]  # Keep System Prompt and original User Task
            tail = history[-5:] # Keep the most recent context
            
            # In a fully-fledged system, we would do a cheap LLM call here to summarize history[2:-5].
            # For Phase 1, we use a static placeholder.
            middle_summary = {
                "role": "user",
                "content": "[SYSTEM MEMORY COMPACTION] Intermediate steps have been summarized to save context. The agent explored the codebase and ran tools."
            }
            history = head + [middle_summary] + tail
        
    if step_count >= MAX_STEPS:
        print("\n[HARD STOP] Max steps reached.")
        
    duration = time.time() - start_time
    
    # Basic metrics
    metrics = {
        "status": "completed" if step_count < MAX_STEPS else "max_steps_reached",
        "total_steps": step_count,
        "total_tokens": cumulative_tokens,
        "cost": 0.0,
        "duration_seconds": duration
    }
    
    save_trajectory(instance_id, history, metrics)
    return history

if __name__ == "__main__":
    # Toy testing block
    run_agent("There is a bug in the code where add(1, 2) returns 4. Fix it.")
