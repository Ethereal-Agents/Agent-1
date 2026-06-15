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

    assert "ERROR: Directory 'does_not_exist_xyz123' not found." in result
