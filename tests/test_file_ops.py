import pytest

from tools.file_ops import EditTool, ReadFileTool


@pytest.fixture
def temp_file(tmp_path):
    """Creates a temporary 5-line text file for testing."""
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "dummy.txt"
    p.write_text("line1\nline2\nline3\nline4\nline5\n")
    return str(p)

def test_read_file_full(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=None, end_line=None)
    
    assert f"[FILE: {temp_file} | Showing lines 1-5 of 5]" in result
    assert "1: line1" in result
    assert "5: line5" in result

def test_read_file_slice(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=2, end_line=3)
    
    assert "Showing lines 2-3 of 5]" in result
    assert "1: line1" not in result
    assert "2: line2" in result
    assert "3: line3" in result
    assert "4: line4" not in result

def test_read_file_out_of_bounds(temp_file):
    tool = ReadFileTool()
    # Passing negative start and massive end should be safely clamped to 1-5
    result = tool.run(path=temp_file, start_line=-10, end_line=999)
    
    assert "Showing lines 1-5 of 5]" in result
    assert "1: line1" in result
    assert "5: line5" in result

def test_read_file_invalid_range(temp_file):
    tool = ReadFileTool()
    result = tool.run(path=temp_file, start_line=4, end_line=2)
    
    # Should trigger the standard error format
    assert "ERROR: start_line (4) cannot be greater than end_line (2)" in result
    assert "ATTEMPTED: read_file(start_line=4, end_line=2)" in result
    assert "HINT:" in result

def test_read_file_not_found():
    tool = ReadFileTool()
    fake_path = "does_not_exist_123.txt"
    result = tool.run(path=fake_path, start_line=None, end_line=None)
    
    assert f"ERROR: File '{fake_path}' not found or is not a file." in result
    assert f"ATTEMPTED: read_file(path='{fake_path}')" in result
    assert "HINT:" in result

def test_edit_file_success(temp_file):
    tool = EditTool()
    old_str = "line2\nline3\n"
    new_str = "NEW_LINE_2\nNEW_LINE_3\n"
    
    result = tool.run(path=temp_file, start_line=2, end_line=3, old_str=old_str, new_str=new_str)
    
    assert "[SUCCESS] Edited" in result
    
    # Read the file to verify it actually changed
    with open(temp_file, "r") as f:
        content = f.read()
    assert "NEW_LINE_2" in content
    assert "line2" not in content

def test_edit_file_mismatch(temp_file):
    tool = EditTool()
    # Notice we omitted the 'e' in 'line2'
    wrong_old_str = "lin2\nline3\n"
    new_str = "NEW_LINE_2\nNEW_LINE_3\n"
    
    result = tool.run(path=temp_file, start_line=2, end_line=3, old_str=wrong_old_str, new_str=new_str)
    
    assert "ERROR: The old_str provided did not perfectly match the file contents." in result
    assert "HINT: Your old_str must match EXACTLY" in result
    assert "line2\nline3" in result  # The hint should contain the actual text

def test_edit_file_invalid_range(temp_file):
    tool = EditTool()
    result = tool.run(path=temp_file, start_line=4, end_line=2, old_str="x", new_str="y")
    
    assert "ERROR: Invalid line range: 4-2." in result
    assert "HINT: Use read_file to check the exact line numbers" in result

def test_edit_file_not_found():
    tool = EditTool()
    result = tool.run(path="fake.txt", start_line=1, end_line=2, old_str="x", new_str="y")
    
    assert "ERROR: File 'fake.txt' not found." in result

def test_edit_file_expansion(temp_file):
    tool = EditTool()
    old_str = "line2\nline3\n"
    new_str = "NEW_LINE_2\nNEW_LINE_2.5\nNEW_LINE_2.75\nNEW_LINE_3\n"
    
    # Replacing 2 lines with 4 lines
    result = tool.run(path=temp_file, start_line=2, end_line=3, old_str=old_str, new_str=new_str)
    
    assert "[SUCCESS] Edited" in result
    
    with open(temp_file, "r") as f:
        lines = f.readlines()
        
    # File should now be 7 lines long
    assert len(lines) == 7
    assert "NEW_LINE_2.5\n" in lines
    assert lines[0] == "line1\n"
    assert lines[-1] == "line5\n"

def test_edit_file_append(temp_file):
    tool = EditTool()
    old_str = ""
    new_str = "line6\nline7\n"
    
    # Appending to the very bottom: start_line is 6, end_line is 6
    result = tool.run(path=temp_file, start_line=6, end_line=6, old_str=old_str, new_str=new_str)
    
    assert "[SUCCESS] Edited" in result
    
    with open(temp_file, "r") as f:
        lines = f.readlines()
        
    # File should now be 7 lines long
    assert len(lines) == 7
    assert lines[-2] == "line6\n"
    assert lines[-1] == "line7\n"

