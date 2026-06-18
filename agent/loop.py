import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

import litellm

from config import (
    COMPACTION_MODEL,
    COMPACTION_THRESHOLD,
    DEFAULT_MODEL,
    MAX_STEPS,
    MAX_SUBMISSIONS,
    _config,
    get_compaction_prompt,
    get_system_prompt,
    get_test_failure_prompt,
)
from memory.trajectory import append_trajectory_step, dump_run_config, save_metrics
from tools.registry import execute_tool, get_env_system_prompt, get_openai_tools


class Agent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        compaction_model: str = COMPACTION_MODEL,
        instance_id: str = None,
    ):
        if not instance_id:
            instance_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        self.model = model
        self.compaction_model = compaction_model
        self.instance_id = instance_id
        self.system_prompt = get_system_prompt()

        env_prompt = get_env_system_prompt()
        if env_prompt:
            self.system_prompt += f"\n\n{env_prompt}"

        self.compaction_prompt = get_compaction_prompt()
        self.history: List[Dict[str, Any]] = []
        self.full_history: List[Dict[str, Any]] = []

        self.step_count = 0
        self.submit_count = 0
        self.cumulative_tokens = 0
        self.cumulative_cost = 0.0
        self.start_time = 0.0

        # Dump configuration for experiment tracking
        run_config = _config.copy()
        run_config["runtime_overrides"] = {
            "model": self.model,
            "compaction_model": self.compaction_model,
        }
        dump_run_config(self.instance_id, run_config)

    def _append_history(self, message: Dict[str, Any]):
        self.history.append(message)
        self.full_history.append(message)
        append_trajectory_step(self.instance_id, message)

    def run(self, issue_description: str) -> List[Dict[str, Any]]:
        print(f"Starting recall-agent on model: {self.model}")
        self.start_time = time.time()

        # Initialize conversation history with Checkpoints 1 and 2 for Prompt Caching
        initial_history = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Please fix the following issue:\n\n{issue_description}",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
        ]

        self.history = []
        self.full_history = []
        for step in initial_history:
            self._append_history(step)

        while self.step_count < MAX_STEPS:
            print(f"\n--- Step {self.step_count + 1} ---")

            message = self._call_llm()
            if not message:
                break

            # Print reasoning if available
            if message.content:
                print(f"\n[Reasoning]: {message.content.strip()}")

            if not hasattr(message, "tool_calls") or not message.tool_calls:
                print("\n[Agent finished. No tools called.]")
                break

            should_continue = self._process_tools(message.tool_calls)
            if not should_continue:
                break

            self.step_count += 1
            self._compact_memory()

        if self.step_count >= MAX_STEPS:
            print("\n[HARD STOP] Max steps reached.")

        self._finalize_run()
        return self.full_history

    def _call_llm(self):
        import copy

        messages = copy.deepcopy(self.history)

        # Apply Sliding Window Cache (Checkpoint 3) to the N-2 message
        # This keeps the bulk of the trajectory cached, moving forward each turn.
        if len(messages) >= 4:
            target_msg = messages[-2]
            content = target_msg.get("content")
            if content:
                if isinstance(content, str):
                    target_msg["content"] = [
                        {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
                    ]
                elif isinstance(content, list) and len(content) > 0:
                    if isinstance(content[-1], dict):
                        content[-1]["cache_control"] = {"type": "ephemeral"}

        try:
            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=get_openai_tools(),
            )
        except Exception as e:
            print(f"API Error: {e}")
            return None

        self._track_metrics(response)

        message = response.choices[0].message

        # Append assistant's response exactly as provided by the API
        self._append_history(message.model_dump(exclude_none=True))
        return message

    def _process_tools(self, tool_calls) -> bool:
        """Process tool calls. Returns False if the agent loop should break."""
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            print(f"[Tool Call]: {tool_name}({tool_args})")
            should_continue = True

            # --- INTERCEPT submit_patch ---
            if tool_name == "submit_patch":
                self.submit_count += 1
                if self.submit_count >= MAX_SUBMISSIONS:
                    print(f"\n[HARD STOP] Submission cap ({MAX_SUBMISSIONS}) reached. Halting.")
                    observation = "[HARD STOP] Submission limit reached. Task failed."
                    should_continue = False  # Exit agent loop after appending
                else:
                    print(f"Verifying patch (Attempt {self.submit_count}/{MAX_SUBMISSIONS})...")
                    # Trigger the actual test suite to verify
                    test_results = execute_tool("run_tests", {"targets": []})

                    if "<status>PASSED</status>" in test_results:
                        print("\n[SUCCESS] Tests passed! Patch successful.")
                        observation = "[SUCCESS] All tests passed! Please provide a final summary of what you fixed to the user, and do not call any more tools."
                    else:
                        print("\n[FAILURE] Tests failed. Feeding back to agent for reflection.")
                        observation = get_test_failure_prompt(test_results)
            else:
                # --- STANDARD TOOLS ---
                observation = execute_tool(tool_name, tool_args)

            # Append the tool's result back to the LLM exactly once
            self._append_history(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": observation,
                }
            )

            if not should_continue:
                return False

        return True

    def _compact_memory(self):
        # --- "Sawtooth" Memory Compaction ---
        # If history gets too long, compress the middle to prevent LLM amnesia and save tokens.
        if len(self.history) > COMPACTION_THRESHOLD:
            print("\n[Memory Compaction] Triggering Sawtooth compaction...")
            head = self.history[:2]  # Keep System Prompt and original User Task

            # Ensure tail starts with an assistant or user message to prevent Anthropic API errors
            # (Anthropic strictly requires tool responses to have a preceding assistant tool_use)
            tail_size = 5
            while tail_size < len(self.history) - 2:  # Don't cut into head
                if self.history[-tail_size].get("role") in ["assistant", "user"]:
                    break
                tail_size += 1

            tail = self.history[-tail_size:]
            middle = self.history[2:-tail_size] if tail_size < len(self.history) - 2 else []

            # Create a string representation of the middle history
            try:
                middle_text = json.dumps(middle, indent=2)
            except Exception:
                middle_text = str(middle)

            summary_prompt = [
                {"role": "system", "content": self.compaction_prompt},
                {
                    "role": "user",
                    "content": f"Please summarize this intermediate history:\n\n{middle_text}",
                },
            ]

            try:
                print(f"Generating summary for compacted history using {self.compaction_model}...")
                response = litellm.completion(model=self.compaction_model, messages=summary_prompt)
                summary_text = response.choices[0].message.content

                self._track_metrics(response)
            except Exception as e:
                print(f"Summarization Error: {e}")
                summary_text = (
                    "The agent explored the codebase and ran tools. (Summarization failed)"
                )

            middle_summary = {
                "role": "user",
                "content": f"[SYSTEM MEMORY COMPACTION] Intermediate steps have been summarized to save context:\n\n{summary_text}",
            }
            self.history = head + [middle_summary] + tail

            # Log the compaction event to the full trajectory for the viewer
            compaction_event = {
                "role": "system",
                "content": f"[MEMORY COMPACTION TRIGGERED]\nSummarized {len(middle)} messages.\n\nSummary result:\n{summary_text}",
            }
            self.full_history.append(compaction_event)
            append_trajectory_step(self.instance_id, compaction_event)

    def _track_metrics(self, response):
        """Extract and accumulate token counts and costs from a litellm response."""
        if hasattr(response, "usage") and response.usage:
            self.cumulative_tokens += getattr(response.usage, "total_tokens", 0)

        try:
            step_cost = litellm.completion_cost(completion_response=response)
            if step_cost:
                self.cumulative_cost += step_cost
        except Exception:
            pass  # Fails gracefully if the model is too new or cost is unknown

    def _finalize_run(self):
        duration = time.time() - self.start_time

        # Basic metrics
        metrics = {
            "status": "completed" if self.step_count < MAX_STEPS else "max_steps_reached",
            "total_steps": self.step_count,
            "total_tokens": self.cumulative_tokens,
            "cost": self.cumulative_cost,
            "duration_seconds": duration,
        }

        save_metrics(self.instance_id, metrics)


def run_agent(
    issue_description: str, model: str = DEFAULT_MODEL, instance_id: str = None
) -> List[Dict[str, Any]]:
    agent = Agent(model=model, instance_id=instance_id)
    return agent.run(issue_description)


if __name__ == "__main__":  # pragma: no cover
    # Toy testing block
    run_agent("There is a bug in the code where add(1, 2) returns 4. Fix it.")
