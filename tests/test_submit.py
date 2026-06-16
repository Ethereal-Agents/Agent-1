import os

from tools.submit import SubmitTool


def test_submit_tool():
    tool = SubmitTool()
    result = tool.run(summary="Finished everything perfectly.")

    assert "[AGENT_FINISHED]" in result
    assert "Finished everything perfectly." in result

    assert os.path.exists("fix.patch")
    os.remove("fix.patch")


def test_submit_tool_no_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool = SubmitTool()
    result = tool.run(summary="test")
    assert "ERROR: Failed to generate patch" in result
    assert "ATTEMPTED: submit()" in result
    assert "HINT: Ensure you are inside a git repository." in result
