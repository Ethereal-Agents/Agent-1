import shlex
import subprocess

from pydantic import BaseModel, Field

from tools.base import BaseTool
from tools.utils import format_error, truncate_output


class CodeSearchArgs(BaseModel):
    query: str = Field(
        ..., description="The string or regex pattern to search for across the codebase."
    )
    directory: str = Field(".", description="The directory to search within (default is root).")


class CodeSearchTool(BaseTool):
    name = "code_search"
    description = "Searches the codebase using ripgrep."
    args_schema = CodeSearchArgs

    def run(self, query: str, directory: str = ".", **kwargs) -> str:
        try:
            # We must escape the arguments since self.env.run_bash uses shell=True
            query_esc = shlex.quote(query)
            dir_esc = shlex.quote(directory)
            cmd_str = f"rg -n -H --no-heading -- {query_esc} {dir_esc}"

            result = self.env.run_bash(cmd_str, timeout=120)
        except subprocess.TimeoutExpired:
            return format_error(
                reason="Ripgrep search timed out after 120 seconds.",
                attempted=cmd_str,
                hint="The directory might be too large. Try narrowing your search directory.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to execute ripgrep: {str(e)}",
                attempted=f"code_search(query='{query}')",
            )

        if result.returncode == 127:
            return format_error(
                reason="The 'rg' (ripgrep) command is not found in the environment.",
                attempted=cmd_str,
                hint="You must install ripgrep in the target environment.",
            )

        if result.returncode == 1 and not result.stdout:
            return f"No matches found for '{query}' in directory '{directory}'."

        if result.returncode > 1:
            return format_error(
                reason=f"Ripgrep failed with exit code {result.returncode}: {result.stderr}",
                attempted=f"code_search(query='{query}')",
                hint="Ensure your regex query is validly escaped.",
            )

        # Parse the output into XML blocks
        lines = result.stdout.splitlines()
        file_map = {}

        for line in lines:
            # Expected format: filename:line_num:matched_text
            parts = line.split(":", 2)
            if len(parts) >= 3:
                filename = parts[0]
                line_num = parts[1]
                match_text = parts[2]

                if filename not in file_map:
                    file_map[filename] = []
                file_map[filename].append(f"{line_num}: {match_text}")

        # Construct XML
        xml_blocks = [f"[SEARCH RESULTS for '{query}']"]
        for filename, matches in file_map.items():
            xml_blocks.append(f'<file path="{filename}">')
            xml_blocks.extend(matches)
            xml_blocks.append("</file>")

        final_output = "\n".join(xml_blocks)
        return truncate_output(final_output)
