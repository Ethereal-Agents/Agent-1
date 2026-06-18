from tools.environment import LocalEnvironment
from tools.registry import TOOLS, execute_tool, get_openai_tools, initialize_tools
from tools.utils import format_error, truncate_output


def test_get_openai_tools():
    tools = get_openai_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Verify structure
    assert "type" in tools[0]
    assert tools[0]["type"] == "function"
    assert "function" in tools[0]
    assert "name" in tools[0]["function"]


def test_execute_tool_success():
    # Test a simple tool execution like bash
    result = execute_tool("bash", {"command": "echo 'registry test'"})
    assert "registry test" in result


def test_execute_tool_not_found():
    result = execute_tool("nonexistent_tool_xyz", {})
    assert "Tool 'nonexistent_tool_xyz' not found." in result


def test_truncate_output():
    short_text = "abc"
    assert truncate_output(short_text, max_len=100) == short_text

    long_text = "A" * 200
    truncated = truncate_output(long_text, max_len=100)
    assert len(truncated) == 100
    assert "OUTPUT TRUNCATED" in truncated


def test_format_error():
    err = format_error("Test reason", "Test attempt", "Test hint")
    assert "ERROR: Test reason" in err
    assert "ATTEMPTED: Test attempt" in err
    assert "HINT: Test hint" in err


def test_initialize_tools():
    env = LocalEnvironment()
    initialize_tools(env)
    for tool in TOOLS:
        assert tool.env is env


def test_execute_tool_invalid_args():
    # command should be a string, passing an int should throw Pydantic ValidationError
    # which is caught by the generic except Exception in execute_tool
    result = execute_tool("bash", {"command": 123})
    assert "ERROR: Failed to execute 'bash'" in result


def test_get_env_system_prompt():
    from tools.registry import get_env_system_prompt

    env = LocalEnvironment()
    initialize_tools(env)
    prompt = get_env_system_prompt()
    assert "ENVIRONMENT CONTEXT" in prompt
