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


class MockEnv:
    def __init__(self, commit):
        self.initial_commit = commit


def test_finish_tool_initial_commit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.system("git init")
    os.system("git config user.email 'test@example.com'")
    os.system("git config user.name 'Test User'")
    os.system("echo 'a' > a.txt && git add a.txt && git commit -m 'initial'")
    initial_commit = os.popen("git rev-parse HEAD").read().strip()
    os.system("echo 'b' > b.txt && git add b.txt && git commit -m 'second'")

    tool = FinishTool()
    tool.env = MockEnv(initial_commit)
    result = tool.run(summary="Fixed it!")

    assert "[AGENT_FINISHED]" in result
    with open("fix.patch", "r", encoding="utf-8") as f:
        patch_content = f.read()
    assert "b.txt" in patch_content
