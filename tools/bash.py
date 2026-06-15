from pydantic import BaseModel, Field

from tools.base import BaseTool


class BashArgs(BaseModel):
    command: str = Field(..., description="The bash command to execute.")

class BashTool(BaseTool):
    name = "bash"
    description = "Executes a bash command in the project environment."
    args_schema = BashArgs

    def run(self, command: str, **kwargs) -> str:
        import subprocess

        from tools.utils import format_error, truncate_output

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120  # Prevent infinite loops / interactive hangs
            )
        except subprocess.TimeoutExpired:
            return format_error(
                reason="Command timed out after 120 seconds.",
                attempted=f"bash(command='{command[:50]}...')",
                hint="Do not run interactive commands (like vim, nano, or bare python REPL) or infinite loops. If compiling, it may just take longer."
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to execute command: {str(e)}",
                attempted=f"bash(command='{command[:50]}...')",
                hint="Ensure your bash syntax is valid."
            )

        # Build the structured XML response
        xml_blocks = []
        if result.stdout:
            xml_blocks.append(f"<stdout>\n{truncate_output(result.stdout)}\n</stdout>")
        if result.stderr:
            xml_blocks.append(f"<stderr>\n{truncate_output(result.stderr)}\n</stderr>")
            
        xml_blocks.append(f"<exit_code>{result.returncode}</exit_code>")
        
        return "\n".join(xml_blocks)
