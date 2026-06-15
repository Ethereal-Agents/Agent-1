import os
import pytest
from tools.submit import SubmitTool

def test_submit_tool(tmp_path, monkeypatch):
    # Change to temp dir to avoid git issues, though it might fail if not in a git repo.
    # We will test the failure case since setting up a full git repo in a test is slow.
    monkeypatch.chdir(tmp_path)
    tool = SubmitTool()
    result = tool.run(summary="Tested submit")
    
    # It should fail elegantly because tmp_path is not a git repo
    assert "ERROR: Failed to generate patch" in result
    assert "HINT: Ensure you are inside a git repository." in result
