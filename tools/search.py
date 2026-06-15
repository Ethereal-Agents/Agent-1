from pydantic import BaseModel, Field
from tools.base import BaseTool

class CodeSearchArgs(BaseModel):
    query: str = Field(..., description="The string or regex pattern to search for across the codebase.")
    directory: str = Field(".", description="The directory to search within (default is root).")

class CodeSearchTool(BaseTool):
    name = "code_search"
    description = "Searches the codebase using ripgrep."
    args_schema = CodeSearchArgs

    def run(self, query: str, directory: str = ".", **kwargs) -> str:
        import subprocess
        import os
        from tools.utils import format_error, truncate_output

        if not os.path.isdir(directory):
            return format_error(
                reason=f"Directory '{directory}' not found.",
                attempted=f"code_search(directory='{directory}')",
                hint="Use the bash tool with 'ls' to check the directory structure."
            )

        import shutil
        rg_path = shutil.which("rg") or "rg"

        try:
            # -n forces line numbers, -H forces filename, --no-heading removes blank lines between files
            # '--' stops flag parsing so queries starting with hyphens are safe
            result = subprocess.run(
                [rg_path, "-n", "-H", "--no-heading", "--", query, directory],
                capture_output=True,
                text=True
            )
        except FileNotFoundError:
            return format_error(
                reason="The 'rg' (ripgrep) command is not found in the system PATH.",
                attempted="subprocess.run(['rg', ...])",
                hint="You must install ripgrep using the appropriate package manager for your OS and ensure it is in your PATH."
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to execute ripgrep: {str(e)}",
                attempted=f"code_search(query='{query}')",
                hint="Check if the query is a valid regex."
            )

        if result.returncode == 1 and not result.stdout:
            return f"No matches found for '{query}' in directory '{directory}'."
            
        if result.returncode > 1:
            return format_error(
                reason=f"Ripgrep failed with exit code {result.returncode}: {result.stderr}",
                attempted=f"code_search(query='{query}')",
                hint="Ensure your regex query is validly escaped."
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
            xml_blocks.append('</file>')

        final_output = "\n".join(xml_blocks)
        return truncate_output(final_output)
