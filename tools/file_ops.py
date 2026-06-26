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

    def run(
        self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs
    ) -> str:
        try:
            content = self.env.read_file(path)
            lines = content.splitlines(keepends=True) if content else []
        except FileNotFoundError:
            return format_error(
                reason=f"File '{path}' not found or is not a file.",
                attempted=f"read_file(path='{path}')",
                hint="File not found. Use the bash tool with 'ls' or 'find' to verify the exact path.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to read file: {str(e)}",
                attempted=f"read_file(path='{path}')",
            )

        total_lines = len(lines)
        if total_lines == 0:
            return f"[FILE: {path} | Showing lines 0-0 of 0]\n[FILE IS EMPTY]"

        # 1-indexed conversions
        start = start_line if start_line is not None else 1
        end = end_line if end_line is not None else total_lines

        # Boundary safety checks
        start = max(1, start)
        end = min(total_lines, end)

        if start > end:
            return format_error(
                reason=f"start_line ({start}) cannot be greater than end_line ({end}).",
                attempted=f"read_file(path='{path}', start_line={start}, end_line={end})",
                hint="Check the total lines of the file and ensure start_line <= end_line.",
            )

        # Slicing is 0-indexed in python
        sliced_lines = lines[start - 1 : end]

        # Format with 1-indexed line numbers
        formatted_lines = []
        for idx, line in enumerate(sliced_lines):
            line_num = start + idx
            stripped_line = line.rstrip("\n")
            formatted_lines.append(f"{line_num}: {stripped_line}")

        header = f"[FILE: {path} | Showing lines {start}-{end} of {total_lines}]"

        result = header + "\n" + "\n".join(formatted_lines)

        # Truncate if the file segment was too large
        return truncate_output(result)


# ---------------------------------------------------------------------------
#  Edit tool — str_replace design
# ---------------------------------------------------------------------------


class EditFileArgs(BaseModel):
    path: str = Field(..., description="The absolute path to the file to edit.")
    old_str: str = Field(
        ...,
        description=(
            "The EXACT text to find and replace, including all whitespace and indentation. "
            "This must match a UNIQUE substring in the file. "
            "Include enough surrounding lines to make the match unambiguous."
        ),
    )
    new_str: str = Field(
        ...,
        description=(
            "The replacement text. Must use the SAME indentation style as the original code. "
            "This completely replaces old_str."
        ),
    )


class EditTool(BaseTool):
    name = "edit"
    description = (
        "Edits a file by finding an exact match of `old_str` and replacing it with `new_str`. "
        "The match must be UNIQUE within the file (exactly one occurrence). "
        "Both old_str and new_str must include correct indentation — "
        "the replacement is performed character-for-character."
    )
    args_schema = EditFileArgs

    # Number of context lines to show around the edit in the response
    CONTEXT_LINES = 4

    def run(self, path: str, old_str: str, new_str: str, **kwargs) -> str:
        # --- Read file --------------------------------------------------------
        try:
            content = self.env.read_file(path)
        except FileNotFoundError:
            return format_error(
                reason=f"File '{path}' not found.",
                attempted=f"edit(path='{path}')",
                hint="Use the bash tool with 'ls' or 'find' to verify the exact path.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to read file: {str(e)}",
                attempted=f"edit(path='{path}')",
            )

        # --- Locate old_str ---------------------------------------------------
        occurrences = _count_occurrences(content, old_str)

        if occurrences == 0:
            # Try to give a helpful hint
            hint = self._mismatch_hint(content, old_str)
            return format_error(
                reason="old_str was not found in the file.",
                attempted=f"edit(path='{path}')",
                hint=hint,
            )

        if occurrences > 1:
            return format_error(
                reason=f"old_str matches {occurrences} locations in the file. It must be unique.",
                attempted=f"edit(path='{path}')",
                hint=(
                    "Include more surrounding context lines in old_str to make it unique, "
                    "or use read_file to inspect the file and find the exact unique block."
                ),
            )

        # --- Perform replacement ---------------------------------------------
        new_content = content.replace(old_str, new_str, 1)

        # --- Validate Python syntax (if applicable) --------------------------
        syntax_warning = ""
        if path.endswith(".py"):
            syntax_warning = self._check_python_syntax(new_content, path)

        # --- Write back -------------------------------------------------------
        try:
            self.env.write_file(path, new_content)
        except Exception as e:
            return format_error(
                reason=f"Failed to write changes: {str(e)}",
                attempted=f"edit(path='{path}')",
            )

        # --- Build informative response ---------------------------------------
        response = self._build_response(path, content, new_content, old_str, new_str)

        if syntax_warning:
            response += f"\n\n⚠️  SYNTAX WARNING:\n{syntax_warning}"

        return response

    def _build_response(
        self, path: str, old_content: str, new_content: str, old_str: str, new_str: str
    ) -> str:
        """Build a response showing the edit with surrounding context."""
        new_lines = new_content.splitlines(keepends=True)

        # Find where the replacement starts in the new content
        replace_start = new_content.index(new_str)
        # Count lines before the replacement
        prefix = new_content[:replace_start]
        start_line = prefix.count("\n") + 1
        end_line = start_line + new_str.count("\n")

        # Show context around the edit
        ctx_start = max(0, start_line - 1 - self.CONTEXT_LINES)
        ctx_end = min(len(new_lines), end_line + self.CONTEXT_LINES)
        context_block = []
        for i in range(ctx_start, ctx_end):
            line_num = i + 1
            line_text = new_lines[i].rstrip("\n")
            context_block.append(f"{line_num}: {line_text}")

        context_str = "\n".join(context_block)

        lines_removed = old_str.count("\n") + (0 if old_str.endswith("\n") else 1)
        lines_added = new_str.count("\n") + (0 if new_str.endswith("\n") else 1)

        return (
            f"[SUCCESS] Edited {path}. ({lines_removed} lines removed, {lines_added} lines added)\n"
            f"\nResult (with context):\n{context_str}"
        )

    def _check_python_syntax(self, content: str, path: str) -> str:
        """Try to compile the Python file; return warning string if syntax is invalid."""
        try:
            compile(content, path, "exec")
            return ""
        except SyntaxError as e:
            return (
                f"Python syntax error after edit — {e.msg} (line {e.lineno}).\n"
                f"Your edit likely introduced a bug. Please fix it."
            )

    def _mismatch_hint(self, content: str, old_str: str) -> str:
        """Generate a helpful hint when old_str isn't found."""
        # Check if it's a whitespace/indentation issue
        stripped_old = old_str.strip()
        if stripped_old and stripped_old in content:
            return (
                "The text was found when ignoring leading/trailing whitespace, "
                "but the EXACT whitespace doesn't match. "
                "Use read_file to see the exact indentation of the target code, "
                "then copy it precisely into old_str."
            )
        # Check if first line exists
        first_line = old_str.split("\n")[0].strip()
        if first_line and first_line in content:
            return (
                f"The first line ('{first_line[:60]}...') exists in the file but the full "
                "old_str block doesn't match. The code may have already been modified, "
                "or your old_str has extra/missing lines. Use read_file to re-inspect."
            )
        return (
            "The text does not appear in the file at all. "
            "Use read_file to inspect the current file content and copy the exact text."
        )


# ---------------------------------------------------------------------------
#  Create / Insert tool — for new files or pure insertions
# ---------------------------------------------------------------------------


class InsertFileArgs(BaseModel):
    path: str = Field(..., description="The absolute path to the file.")
    line: int = Field(
        ...,
        description=(
            "The line number AFTER which to insert new_str (1-indexed). "
            "Use 0 to insert at the beginning of the file."
        ),
    )
    new_str: str = Field(..., description="The text to insert. Must include correct indentation.")


class InsertTool(BaseTool):
    name = "insert"
    description = (
        "Inserts new text after a specific line number. "
        "Use this for adding new code without replacing existing code. "
        "Use line=0 to insert at the beginning of the file."
    )
    args_schema = InsertFileArgs

    def run(self, path: str, line: int, new_str: str, **kwargs) -> str:
        try:
            content = self.env.read_file(path)
            lines = content.splitlines(keepends=True) if content else []
        except FileNotFoundError:
            return format_error(
                reason=f"File '{path}' not found.",
                attempted=f"insert(path='{path}')",
                hint="Use the bash tool with 'ls' or 'find' to verify the exact path.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to read file: {str(e)}",
                attempted=f"insert(path='{path}')",
            )

        total_lines = len(lines)
        if line < 0 or line > total_lines:
            return format_error(
                reason=f"Invalid line number: {line}. File has {total_lines} lines (use 0..{total_lines}).",
                attempted=f"insert(path='{path}', line={line})",
                hint="Use read_file to check line numbers.",
            )

        # Ensure new_str ends with newline
        insert_text = new_str if new_str.endswith("\n") else new_str + "\n"
        new_lines = insert_text.splitlines(keepends=True)

        lines[line:line] = new_lines

        try:
            self.env.write_file(path, "".join(lines))
        except Exception as e:
            return format_error(
                reason=f"Failed to write changes: {str(e)}",
                attempted=f"insert(path='{path}')",
            )

        # Show context
        ctx_start = max(0, line - 2)
        ctx_end = min(len(lines), line + len(new_lines) + 2)
        context_block = []
        for i in range(ctx_start, ctx_end):
            line_num = i + 1
            line_text = lines[i].rstrip("\n")
            marker = "+" if line < i <= line + len(new_lines) else " "
            context_block.append(f"{marker} {line_num}: {line_text}")

        context_str = "\n".join(context_block)

        # Syntax check for Python files
        syntax_warning = ""
        if path.endswith(".py"):
            new_content = "".join(lines)
            try:
                compile(new_content, path, "exec")
            except SyntaxError as e:
                syntax_warning = (
                    f"\n\n⚠️  SYNTAX WARNING: {e.msg} (line {e.lineno}). "
                    f"Your insertion likely introduced a bug. Please fix it."
                )

        return (
            f"[SUCCESS] Inserted {len(new_lines)} lines after line {line} in {path}.\n"
            f"\nResult:\n{context_str}"
            f"{syntax_warning}"
        )


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _count_occurrences(content: str, substring: str) -> int:
    """Count non-overlapping occurrences of substring in content."""
    count = 0
    start = 0
    while True:
        idx = content.find(substring, start)
        if idx == -1:
            break
        count += 1
        start = idx + len(substring)
    return count
