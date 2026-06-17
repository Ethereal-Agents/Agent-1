from tools.registry import execute_tool, get_openai_tools
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
