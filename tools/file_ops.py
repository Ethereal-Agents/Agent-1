import os
from typing import Optional
from pydantic import BaseModel, Field

from tools.base import BaseTool
from tools.utils import format_error, truncate_output

class ReadFileArgs(BaseModel):
    path: str = Field(..., description="The relative path to the file to read.")
    start_line: Optional[int] = Field(None, description="The starting line number (1-indexed).")
    end_line: Optional[int] = Field(None, description="The ending line number (1-indexed).")

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Reads a file from the repository."
    args_schema = ReadFileArgs

    def run(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> str:
        if not os.path.isfile(path):
            return format_error(
                reason=f"File '{path}' not found or is not a file.",
                attempted=f"read_file(path='{path}')",
                hint="Use the bash tool with 'ls' to check the directory contents and verify the file path."
            )
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return format_error(
                reason=f"Failed to read file: {str(e)}",
                attempted=f"read_file(path='{path}')",
                hint="Ensure you have permissions to read this file and that it is text-encoded."
            )
            
        total_lines = len(lines)
        
        # 1-indexed conversions
        start = start_line if start_line is not None else 1
        end = end_line if end_line is not None else total_lines
        
        # Boundary safety checks
        start = max(1, start)
        end = min(total_lines, end)
        
        if start > end:
            return format_error(
                reason=f"start_line ({start}) cannot be greater than end_line ({end}).",
                attempted=f"read_file(start_line={start}, end_line={end})",
                hint="Check the total lines of the file and ensure start_line <= end_line."
            )
            
        # Slicing is 0-indexed in python
        sliced_lines = lines[start-1:end]
        
        # Format with 1-indexed line numbers
        formatted_lines = []
        for idx, line in enumerate(sliced_lines):
            line_num = start + idx
            stripped_line = line.rstrip('\n')
            formatted_lines.append(f"{line_num}: {stripped_line}")
            
        header = f"[FILE: {path} | Showing lines {start}-{end} of {total_lines}]"
        
        result = header + "\n" + "\n".join(formatted_lines)
        
        # Truncate if the file segment was too large
        return truncate_output(result)

class EditArgs(BaseModel):
    path: str = Field(..., description="The relative path to the file to edit.")
    start_line: int = Field(..., description="The starting line number of the block to replace (1-indexed).")
    end_line: int = Field(..., description="The ending line number of the block to replace (1-indexed).")
    old_str: str = Field(..., description="The exact text to be replaced perfectly matching the file.")
    new_str: str = Field(..., description="The new text to replace old_str with.")

class EditTool(BaseTool):
    name = "edit"
    description = "Edits a file by replacing old_str with new_str."
    args_schema = EditArgs

    def run(self, path: str, start_line: int, end_line: int, old_str: str, new_str: str, **kwargs) -> str:
        if not os.path.isfile(path):
            return format_error(
                reason=f"File '{path}' not found.",
                attempted=f"edit(path='{path}')",
                hint="Use the read_file or code_search tool to find the correct file path."
            )
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            return format_error(
                reason=f"Failed to read file: {str(e)}",
                attempted=f"edit(path='{path}')",
                hint="Ensure you have permissions."
            )
            
        total_lines = len(lines)
        if start_line < 1 or end_line > total_lines or start_line > end_line:
            return format_error(
                reason=f"Invalid line range: {start_line}-{end_line}. File has {total_lines} lines.",
                attempted=f"edit(start_line={start_line}, end_line={end_line})",
                hint="Use read_file to check the exact line numbers you want to edit."
            )
            
        # Extract the exact block of text
        block_lines = lines[start_line-1:end_line]
        actual_str = "".join(block_lines)
        
        # We allow a small leniency for trailing newlines which are famously hard for LLMs to predict perfectly
        if old_str.rstrip() != actual_str.rstrip():
            return format_error(
                reason="The old_str provided did not perfectly match the file contents.",
                attempted=f"edit(old_str='{old_str[:100]}...')",
                hint=f"Your old_str must match EXACTLY, including whitespace. The actual text in that range is:\n{actual_str}\nPlease use read_file to view the exact lines."
            )
            
        # Perform replacement
        new_lines = new_str.splitlines(keepends=True)
        # Handle the case where the LLM forgets the trailing newline on the replacement block
        if not new_str.endswith('\n') and actual_str.endswith('\n'):
            new_lines[-1] = new_lines[-1] + '\n'
            
        lines[start_line-1:end_line] = new_lines
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception as e:
            return format_error(
                reason=f"Failed to write changes: {str(e)}",
                attempted="File save",
                hint="Check directory permissions."
            )
            
        return f"[SUCCESS] Edited {path}.\nApplied diff:\n- {old_str.strip()[:100]}...\n+ {new_str.strip()[:100]}..."
