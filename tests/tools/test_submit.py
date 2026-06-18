import os

from tools.finish import FinishTool


def test_finish_tool():
    tool = FinishTool()
    result = tool.run(summary="Fixed the bug by correcting the return value.")

    assert "[AGENT_FINISHED]" in result
    assert "Fixed the bug by correcting the return value." in result

    assert os.path.exists("fix.patch")
    os.remove("fix.patch")


def test_finish_tool_no_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool = FinishTool()
    result = tool.run(summary="test")
    assert "ERROR: Failed to generate patch" in result
    assert "ATTEMPTED: finish()" in result
    assert "HINT: Ensure you are inside a git repository." in result
