import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

import litellm

from config import (
    COMPACTION_MODEL,
    COMPACTION_TOKEN_FRACTION,
    DEFAULT_MODEL,
    FALLBACK_COMPACTION_LIMIT,
    MAX_STEPS,
    _config,
    get_compaction_prompt,
    get_system_prompt,
)
from memory.trajectory import append_trajectory_step, dump_run_config, save_metrics
from tools.registry import ToolName, execute_tool, get_env_system_prompt, get_openai_tools


def _extract_reasoning(message: Any) -> Any:
    """Extract reasoning/content robustly from a LiteLLM message."""
    reasoning = getattr(message, "content", None)
    if not reasoning and getattr(message, "reasoning_content", None):
        reasoning = message.reasoning_content
    elif (
        not reasoning
        and getattr(message, "provider_specific_fields", None)
        and isinstance(message.provider_specific_fields, dict)
    ):
        reasoning = message.provider_specific_fields.get("reasoning")
    return reasoning


class Agent:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        compaction_model: str = COMPACTION_MODEL,
        instance_id: str = None,
    ):
        if not instance_id:
            instance_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # litellm.log_raw_request_response = True
        # litellm.set_verbose = True

        self.model = model
        self.compaction_model = compaction_model
        self.instance_id = instance_id
        self.system_prompt = get_system_prompt()

        env_prompt = get_env_system_prompt()
        if env_prompt:
            self.system_prompt += f"\n\n{env_prompt}"

        self.compaction_prompt = get_compaction_prompt()
        self.history: List[Dict[str, Any]] = []

        model_info = litellm.model_cost.get(self.model, {})
        max_input = model_info.get("max_input_tokens") or model_info.get("max_tokens")
        if max_input:
            self.compaction_threshold = int(max_input * COMPACTION_TOKEN_FRACTION)
        else:
            self.compaction_threshold = FALLBACK_COMPACTION_LIMIT
        self.full_history: List[Dict[str, Any]] = []

        self.step_count = 0
        self.cumulative_tokens = 0
        self.cumulative_cost = 0.0
        self.start_time = 0.0
        self.has_run_tests = False
        self.finish_nudged = False
        self.baseline_failures: set = set()

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

        # Capture pre-existing test failures before the agent starts
        self.baseline_failures = self._capture_test_baseline()

        # Build baseline context for the agent
        baseline_msg = ""
        if self.baseline_failures:
            failure_list = "\n".join(f"  - {f}" for f in sorted(self.baseline_failures))
            baseline_msg = (
                f"\n\n**Pre-existing test failures (NOT your responsibility):**\n"
                f"{failure_list}\n"
                f"These tests were already failing before you started. Ignore them."
            )

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
                        "text": f"Please fix the following issue:\n\n{issue_description}{baseline_msg}",
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

            reasoning = _extract_reasoning(message)

            # Print reasoning if available
            if reasoning:
                print(f"\n[Reasoning]: {reasoning.strip()}")

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
            print("Raw LLM API Response:")
            print(response)
        except Exception as e:
            print(f"API Error: {e}")
            return None

        self._track_metrics(response)

        message = response.choices[0].message

        dumped = message.model_dump(exclude_none=True)

        # Ensure reasoning is preserved in the history's content field
        reasoning = _extract_reasoning(message)

        if reasoning and "content" not in dumped:
            dumped["content"] = reasoning

        # Append assistant's response exactly as provided by the API
        self._append_history(dumped)
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

            if tool_name == ToolName.FINISH:
                # Soft guardrail: nudge once if agent never ran tests
                if not self.has_run_tests and not self.finish_nudged:
                    self.finish_nudged = True
                    observation = (
                        "[NOTE] You are finishing without having run any tests this session. "
                        "If you are confident your changes are correct, call finish again. "
                        "Otherwise, consider running the relevant tests first."
                    )
                    print("[Soft Nudge] Agent finishing without test verification.")
                else:
                    # Accept the finish
                    observation = execute_tool(ToolName.FINISH, tool_args)
                    self._append_history(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": observation,
                        }
                    )
                    print(f"\n[FINISHED] {tool_args.get('summary', 'Agent finished.')}")
                    return False
            else:
                # Standard tool execution
                observation = execute_tool(tool_name, tool_args)
                # Track if agent has voluntarily run tests
                if tool_name == ToolName.RUN_TESTS:
                    self.has_run_tests = True

            self._append_history(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": observation,
                }
            )

        return True

    def _capture_test_baseline(self) -> set:
        """Run tests once before the agent starts to identify pre-existing failures."""
        import re

        print("[Baseline] Capturing pre-existing test failures...")
        try:
            result = execute_tool(ToolName.RUN_TESTS, {"targets": []})
            failures = set(re.findall(r'<test name="([^"]+)">', result))
            if failures:
                print(f"[Baseline] {len(failures)} pre-existing test failure(s) detected.")
            else:
                print("[Baseline] All tests passing. Clean slate.")
            return failures
        except Exception as e:
            print(f"[Baseline] Failed to capture baseline: {e}")
            return set()

    def _compact_memory(self):
        # --- "Sawtooth" Memory Compaction ---
        # If history gets too long or exceeds token limit, compress the middle to prevent LLM amnesia and save tokens.
        try:
            current_tokens = litellm.token_counter(model=self.model, messages=self.history)
        except Exception:
            current_tokens = 0

        if current_tokens > self.compaction_threshold:
            print(
                f"\n[Memory Compaction] Triggering Sawtooth compaction... "
                f"(Steps: {len(self.history)}, Tokens: {current_tokens}, Threshold: {self.compaction_threshold})"
            )
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
