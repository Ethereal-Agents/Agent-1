from unittest.mock import patch

import pytest

from agent.loop import Agent, run_agent
from config import COMPACTION_THRESHOLD, MAX_SUBMISSIONS


@pytest.fixture
def mock_config():
    with (
        patch("agent.loop.get_system_prompt", return_value="sys prompt"),
        patch("agent.loop.get_compaction_prompt", return_value="compaction prompt"),
        patch("agent.loop.COMPACTION_THRESHOLD", 15),
    ):
        yield


class MockUsage:
    total_tokens = 100


class MockMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        return {"content": self.content, "tool_calls": self.tool_calls}


class MockChoice:
    def __init__(self, message):
        self.message = message


class MockResponse:
    def __init__(self, message, usage=None):
        self.choices = [MockChoice(message)]
        self.usage = usage


class MockToolFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class MockToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = MockToolFunction(name, arguments)


class TestAgentInit:
    def test_agent_init(self, mock_config):
        agent = Agent(
            model="test_model", compaction_model="test_compaction_model", instance_id="test_id"
        )
        assert agent.model == "test_model"
        assert agent.compaction_model == "test_compaction_model"
        assert agent.instance_id == "test_id"
        assert agent.system_prompt.startswith("sys prompt")
        assert agent.compaction_prompt == "compaction prompt"
        assert agent.step_count == 0
        assert agent.submit_count == 0
        assert agent.cumulative_tokens == 0
        assert agent.cumulative_cost == 0.0


class TestAgentLLM:
    def test_track_metrics(self, mock_config):
        agent = Agent()
        resp = MockResponse(MockMessage(""), MockUsage())

        with patch("agent.loop.litellm.completion_cost", return_value=0.05):
            agent._track_metrics(resp)

        assert agent.cumulative_tokens == 100
        assert agent.cumulative_cost == 0.05

    def test_track_metrics_fallback(self, mock_config):
        agent = Agent()
        resp = MockResponse(MockMessage(""))  # No usage

        with patch("agent.loop.litellm.completion_cost", side_effect=Exception("No cost")):
            agent._track_metrics(resp)

        assert agent.cumulative_tokens == 0
        assert agent.cumulative_cost == 0.0

    def test_call_llm_success(self, mock_config):
        agent = Agent()
        agent.history = [{"role": "system", "content": "hello"}]

        msg = MockMessage("response")
        resp = MockResponse(msg, MockUsage())

        with (
            patch("agent.loop.litellm.completion", return_value=resp),
            patch("agent.loop.get_openai_tools", return_value=[]),
            patch("agent.loop.litellm.completion_cost", return_value=0.01),
        ):
            ret = agent._call_llm()
            assert ret == msg
            assert len(agent.history) == 2
            assert agent.history[1]["content"] == "response"
            assert agent.cumulative_tokens == 100
            assert agent.cumulative_cost == 0.01

    def test_call_llm_failure(self, mock_config):
        agent = Agent()
        with patch("agent.loop.litellm.completion", side_effect=Exception("API Down")):
            ret = agent._call_llm()
            assert ret is None

    def test_call_llm_sliding_window_cache_string(self, mock_config):
        agent = Agent()
        agent.history = [
            {"role": "system", "content": "1"},
            {"role": "user", "content": "2"},
            {"role": "assistant", "content": "3"},
            {"role": "tool", "content": "4"},
        ]

        msg = MockMessage("response")
        resp = MockResponse(msg, MockUsage())

        with (
            patch("agent.loop.litellm.completion", return_value=resp) as mock_completion,
            patch("agent.loop.litellm.completion_cost", return_value=0.0),
        ):
            agent._call_llm()

            called_messages = mock_completion.call_args[1]["messages"]
            assert called_messages[2]["content"][0]["cache_control"] == {"type": "ephemeral"}
            assert called_messages[2]["content"][0]["text"] == "3"

            assert agent.history[2]["content"] == "3"

    def test_call_llm_sliding_window_cache_list(self, mock_config):
        agent = Agent()
        agent.history = [
            {"role": "system", "content": "1"},
            {"role": "user", "content": "2"},
            {"role": "assistant", "content": [{"type": "text", "text": "3"}]},
            {"role": "tool", "content": "4"},
        ]

        msg = MockMessage("response")
        resp = MockResponse(msg, MockUsage())

        with (
            patch("agent.loop.litellm.completion", return_value=resp) as mock_completion,
            patch("agent.loop.litellm.completion_cost", return_value=0.0),
        ):
            agent._call_llm()

            called_messages = mock_completion.call_args[1]["messages"]
            assert called_messages[2]["content"][-1]["cache_control"] == {"type": "ephemeral"}
            assert called_messages[2]["content"][-1]["text"] == "3"

            assert "cache_control" not in agent.history[2]["content"][-1]


class TestAgentTools:
    def test_process_tools_standard(self, mock_config):
        agent = Agent()
        tc = MockToolCall("call_1", "bash", '{"command": "ls"}')

        with patch("agent.loop.execute_tool", return_value="list of files"):
            res = agent._process_tools([tc])

        assert res is True
        assert len(agent.history) == 1
        assert agent.history[0]["role"] == "tool"
        assert agent.history[0]["tool_call_id"] == "call_1"
        assert agent.history[0]["name"] == "bash"
        assert agent.history[0]["content"] == "list of files"

    def test_process_tools_invalid_json(self, mock_config):
        agent = Agent()
        tc = MockToolCall("call_1", "bash", "invalid json")

        with patch("agent.loop.execute_tool", return_value="fallback output") as mock_exec:
            res = agent._process_tools([tc])
            mock_exec.assert_called_with("bash", {})

        assert res is True
        assert len(agent.history) == 1

    def test_process_tools_submit_patch_success(self, mock_config):
        agent = Agent()
        tc = MockToolCall("call_1", "submit_patch", '{"reasoning": "done"}')

        with patch("agent.loop.execute_tool", return_value="<status>PASSED</status>") as mock_exec:
            res = agent._process_tools([tc])
            mock_exec.assert_called_with("run_tests", {"targets": []})

        assert res is True
        assert agent.submit_count == 1
        assert len(agent.history) == 1
        assert "[SUCCESS]" in agent.history[0]["content"]

    def test_process_tools_submit_patch_failure(self, mock_config):
        agent = Agent()
        tc = MockToolCall("call_1", "submit_patch", '{"reasoning": "done"}')

        with patch("agent.loop.execute_tool", return_value="<status>FAILED</status>"):
            res = agent._process_tools([tc])

        assert res is True
        assert agent.submit_count == 1
        assert len(agent.history) == 1
        assert "TESTS FAILED" in agent.history[0]["content"]

    def test_process_tools_submit_patch_max_submissions(self, mock_config):
        agent = Agent()
        agent.submit_count = MAX_SUBMISSIONS - 1
        tc = MockToolCall("call_1", "submit_patch", '{"reasoning": "done"}')

        res = agent._process_tools([tc])

        assert res is False
        assert agent.submit_count == MAX_SUBMISSIONS
        assert len(agent.history) == 1
        assert "[HARD STOP]" in agent.history[0]["content"]


class TestAgentMemory:
    def test_compact_memory_success(self, mock_config):
        agent = Agent()
        agent.compaction_prompt = "Compaction prompt"
        agent.history = [{"role": "sys", "content": "1"}, {"role": "user", "content": "2"}]
        for i in range(16):
            role = "assistant" if i % 2 == 0 else "tool"
            agent.history.append({"role": role, "content": f"obs {i}"})

        assert len(agent.history) == 18

        msg = MockMessage("Summarized memory")
        resp = MockResponse(msg, MockUsage())

        with (
            patch("agent.loop.litellm.completion", return_value=resp) as mock_completion,
            patch("agent.loop.litellm.completion_cost", return_value=0.02),
        ):
            agent._compact_memory()

        mock_completion.assert_called_once()
        assert mock_completion.call_args[1]["model"] == agent.compaction_model

        # tail size will be 6 (starts at index 12 which is assistant)
        assert len(agent.history) == 9
        assert agent.history[2]["role"] == "user"
        assert "SYSTEM MEMORY COMPACTION" in agent.history[2]["content"]
        assert "Summarized memory" in agent.history[2]["content"]
        assert agent.cumulative_tokens == 100
        assert agent.cumulative_cost == 0.02

    def test_compact_memory_failure(self, mock_config):
        agent = Agent()
        agent.history = [{"role": "sys", "content": "1"}, {"role": "user", "content": "2"}]
        for i in range(COMPACTION_THRESHOLD):
            role = "assistant" if i % 2 == 0 else "tool"
            agent.history.append({"role": role, "content": "c"})

        with patch("agent.loop.litellm.completion", side_effect=Exception("API failure")):
            agent._compact_memory()

        assert "(Summarization failed)" in agent.history[2]["content"]

    def test_compact_memory_json_fallback(self, mock_config):
        agent = Agent()
        agent.compaction_prompt = "Compaction prompt"

        class Unserializable:
            pass

        agent.history = [{"role": "sys", "content": "1"}, {"role": "user", "content": "2"}]
        for i in range(COMPACTION_THRESHOLD):
            role = "assistant" if i % 2 == 0 else "tool"
            agent.history.append({"role": role, "content": Unserializable()})

        msg = MockMessage("Summarized memory")
        resp = MockResponse(msg, MockUsage())

        with (
            patch("agent.loop.litellm.completion", return_value=resp),
            patch("agent.loop.litellm.completion_cost", return_value=0.0),
        ):
            agent._compact_memory()

        assert "Summarized memory" in agent.history[2]["content"]


class TestAgentRun:
    def test_finalize_run(self, mock_config):
        agent = Agent(instance_id="test_run_001")
        agent.step_count = 5
        agent.cumulative_tokens = 500
        agent.cumulative_cost = 0.5
        agent.start_time = 0.0

        with (
            patch("agent.loop.time.time", return_value=10.0),
            patch("agent.loop.save_trajectory") as mock_save,
        ):
            agent._finalize_run()

            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            assert args[0] == "test_run_001"
            assert args[1] == agent.history
            assert args[2]["status"] == "completed"
            assert args[2]["total_steps"] == 5
            assert args[2]["total_tokens"] == 500
            assert args[2]["cost"] == 0.5
            assert args[2]["duration_seconds"] == 10.0

    def test_run_loop_max_steps(self, mock_config):
        agent = Agent()
        msg_with_tool = MockMessage("reasoning", tool_calls=[MockToolCall("1", "bash", "{}")])

        with (
            patch.object(agent, "_call_llm", return_value=msg_with_tool),
            patch.object(agent, "_process_tools", return_value=True),
            patch.object(agent, "_compact_memory"),
            patch.object(agent, "_finalize_run"),
        ):
            with patch("agent.loop.MAX_STEPS", 2):
                agent.run("test issue")

            assert agent.step_count == 2

    def test_run_loop_no_tools(self, mock_config):
        agent = Agent()
        msg = MockMessage("I am done")

        with (
            patch.object(agent, "_call_llm", return_value=msg),
            patch.object(agent, "_finalize_run"),
        ):
            agent.run("test issue")

        assert agent.step_count == 0

    def test_run_loop_should_not_continue(self, mock_config):
        agent = Agent()
        msg_with_tool = MockMessage(
            "reasoning", tool_calls=[MockToolCall("1", "submit_patch", "{}")]
        )

        with (
            patch.object(agent, "_call_llm", return_value=msg_with_tool),
            patch.object(agent, "_process_tools", return_value=False),
            patch.object(agent, "_finalize_run"),
        ):
            agent.run("test issue")

        assert agent.step_count == 0

    def test_run_loop_llm_none(self, mock_config):
        agent = Agent()

        with (
            patch.object(agent, "_call_llm", return_value=None),
            patch.object(agent, "_finalize_run"),
        ):
            agent.run("test issue")

        assert agent.step_count == 0


def test_run_agent_wrapper(mock_config):
    with patch("agent.loop.Agent.run", return_value=[{"msg": "history"}]) as mock_run:
        res = run_agent("issue", "model_x", "id_y")
        assert res == [{"msg": "history"}]
        mock_run.assert_called_once_with("issue")
