import os

import pytest

from tools.file_ops import EditTool, InsertTool, ReadFileTool


@pytest.fixture
def temp_file(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "dummy.txt"
    p.write_text("line1\n    line2\nline3\nline4\nline5\n")
    return str(p)

def test_read_file_full(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=None, end_line=None)
    assert f"[FILE: {temp_file} | Showing lines 1-5 of 5]" in result
    assert "1: line1" in result
    assert "5: line5" in result

def test_read_file_empty(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    tool = ReadFileTool()
    result = tool.run(path=str(p))
    assert "[FILE IS EMPTY]" in result

def test_read_file_slice(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=2, end_line=3)
    assert "Showing lines 2-3 of 5]" in result
    assert "1: line1" not in result
    assert "2:     line2" in result
    assert "3: line3" in result
    assert "4: line4" not in result

def test_read_file_out_of_bounds(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=-10, end_line=999)
    assert "Showing lines 1-5 of 5]" in result

def test_read_file_invalid_range(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=4, end_line=2)
    assert "ERROR: start_line (4) cannot be greater than end_line (2)" in result

def test_read_file_not_found():
    tool = ReadFileTool()
    result = tool.run(path="does_not_exist_123.txt", start_line=None, end_line=None)
    assert "ERROR: File 'does_not_exist_123.txt' not found or is not a file." in result

def test_read_file_permission_error(temp_file):
    os.chmod(temp_file, 0o000)
    try:
        tool = ReadFileTool()
        result = tool.run(path=temp_file)
        assert "ERROR: Failed to read file:" in result
    finally:
        os.chmod(temp_file, 0o644)

def test_edit_file_success(temp_file):
    tool = EditTool()
    old_str = "    line2\nline3\n"
    new_str = "    NEW_LINE_2\nNEW_LINE_3\n"
    result = tool.run(path=temp_file, old_str=old_str, new_str=new_str)
    assert "[SUCCESS] Edited" in result
    with open(temp_file, "r") as f:
        content = f.read()
    assert "NEW_LINE_2" in content
    assert "line2" not in content

def test_edit_file_not_found():
    tool = EditTool()
    result = tool.run(path="fake.txt", old_str="x", new_str="y")
    assert "ERROR: File 'fake.txt' not found." in result

def test_edit_file_permission_error(temp_file):
    os.chmod(temp_file, 0o000)
    try:
        tool = EditTool()
        result = tool.run(path=temp_file, old_str="x", new_str="y")
        assert "ERROR: Failed to read file:" in result
    finally:
        os.chmod(temp_file, 0o644)

def test_edit_file_old_str_not_found(temp_file):
    tool = EditTool()
    result = tool.run(path=temp_file, old_str="not_in_file", new_str="y")
    assert "ERROR: old_str was not found" in result

def test_edit_file_multiple_matches(tmp_path):
    p = tmp_path / "dup.txt"
    p.write_text("a\nmatch\nb\nmatch\nc")
    tool = EditTool()
    result = tool.run(path=str(p), old_str="match\n", new_str="new\n")
    assert "ERROR: old_str matches 2 locations" in result

def test_edit_file_python_syntax_warning(tmp_path):
    p = tmp_path / "test.py"
    p.write_text("def foo():\n    pass\n")
    tool = EditTool()
    result = tool.run(path=str(p), old_str="    pass\n", new_str="    1 = 2\n")
    assert "[SUCCESS]" in result
    assert "SYNTAX WARNING" in result

def test_edit_file_python_syntax_ok(tmp_path):
    p = tmp_path / "test.py"
    p.write_text("def foo():\n    pass\n")
    tool = EditTool()
    result = tool.run(path=str(p), old_str="    pass\n", new_str="    return True\n")
    assert "[SUCCESS]" in result
    assert "SYNTAX WARNING" not in result

def test_edit_file_mismatch_hints(temp_file):
    tool = EditTool()
    result = tool.run(path=temp_file, old_str="   line3\n", new_str="y\n")
    assert "EXACT whitespace doesn't match" in result
    
    result2 = tool.run(path=temp_file, old_str="line3\nline99\n", new_str="y\n")
    assert "The first line" in result2

def test_edit_write_error(temp_file, monkeypatch):
    tool = EditTool()
    def mock_write(*args, **kwargs):
        raise IOError("Mock error")
    monkeypatch.setattr(tool.env, "write_file", mock_write)
    result = tool.run(path=temp_file, old_str="line1\n", new_str="new_line1\n")
    assert "ERROR: Failed to write changes: Mock error" in result

def test_insert_file_success(temp_file):
    tool = InsertTool()
    result = tool.run(path=temp_file, line=2, new_str="inserted\n")
    assert "[SUCCESS]" in result
    with open(temp_file, "r") as f:
        lines = f.readlines()
    assert lines[2] == "inserted\n"
    
def test_insert_beginning(temp_file):
    tool = InsertTool()
    result = tool.run(path=temp_file, line=0, new_str="top\n")
    assert "[SUCCESS]" in result
    with open(temp_file, "r") as f:
        assert f.readline() == "top\n"

def test_insert_out_of_bounds(temp_file):
    tool = InsertTool()
    result = tool.run(path=temp_file, line=99, new_str="x\n")
    assert "ERROR: Invalid line number" in result

def test_insert_not_found():
    tool = InsertTool()
    result = tool.run(path="fake.txt", line=1, new_str="x")
    assert "ERROR: File 'fake.txt' not found" in result

def test_insert_permission_error(temp_file):
    os.chmod(temp_file, 0o000)
    try:
        tool = InsertTool()
        result = tool.run(path=temp_file, line=1, new_str="x")
        assert "ERROR: Failed to read file:" in result
    finally:
        os.chmod(temp_file, 0o644)

def test_insert_write_error(temp_file, monkeypatch):
    tool = InsertTool()
    def mock_write(*args, **kwargs):
        raise IOError("Mock error")
    monkeypatch.setattr(tool.env, "write_file", mock_write)
    result = tool.run(path=temp_file, line=1, new_str="x\n")
    assert "ERROR: Failed to write changes: Mock error" in result

def test_insert_syntax_warning(tmp_path):
    p = tmp_path / "test.py"
    p.write_text("def foo():\n    pass\n")
    tool = InsertTool()
    result = tool.run(path=str(p), line=2, new_str="    1=2\n")
    assert "SYNTAX WARNING" in result
