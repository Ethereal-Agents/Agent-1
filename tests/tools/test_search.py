import pytest

from tools.search import CodeSearchTool


@pytest.fixture
def temp_repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    (d / "file1.py").write_text("def test_one():\n    print('hello world')\n")
    (d / "file2.py").write_text("def test_two():\n    print('goodbye world')\n")
    return str(d)


def test_code_search_found(temp_repo):
    tool = CodeSearchTool()
    result = tool.run(query="print", directory=temp_repo)

    assert "[SEARCH RESULTS for 'print']" in result
    assert "<file path=" in result
    assert "2:     print('hello world')" in result
    assert "2:     print('goodbye world')" in result


def test_code_search_not_found(temp_repo):
    tool = CodeSearchTool()
    result = tool.run(query="MISSING_TEXT_XYZ", directory=temp_repo)

    assert "No matches found for 'MISSING_TEXT_XYZ'" in result


def test_code_search_invalid_dir():
    tool = CodeSearchTool()
    result = tool.run(query="def", directory="does_not_exist_xyz123")

    assert "Ripgrep failed with exit code 2" in result
    assert "No such file or directory" in result


def test_code_search_invalid_regex(temp_repo):
    tool = CodeSearchTool()
    result = tool.run(query="[", directory=temp_repo)
    assert "Ripgrep failed with exit code 2" in result


def test_code_search_timeout():
    import subprocess
    from unittest.mock import MagicMock

    tool = CodeSearchTool()
    tool.env.run_bash = MagicMock(side_effect=subprocess.TimeoutExpired("rg", 120))
    result = tool.run(query="test", directory=".")
    assert "Ripgrep search timed out after 120 seconds." in result


def test_code_search_127():
    import subprocess
    from unittest.mock import MagicMock

    tool = CodeSearchTool()
    mock_result = subprocess.CompletedProcess(args="rg", returncode=127, stdout="", stderr="")
    tool.env.run_bash = MagicMock(return_value=mock_result)
    result = tool.run(query="test", directory=".")
    assert "The 'rg' (ripgrep) command is not found in the environment." in result
