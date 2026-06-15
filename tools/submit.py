from pydantic import BaseModel, Field
from tools.base import BaseTool

class SubmitArgs(BaseModel):
    summary: str = Field(..., description="A brief summary of the changes made to solve the issue.")

class SubmitTool(BaseTool):
    name = "submit"
    description = "Submits your final solution. Call this ONLY when you are completely done with the task."
    args_schema = SubmitArgs

    def run(self, summary: str, **kwargs) -> str:
        import subprocess
        import os
        from tools.utils import format_error

        try:
            # Generate the patch of all current changes
            with open("fix.patch", "w", encoding="utf-8") as f:
                subprocess.run(["git", "diff"], stdout=f, text=True, check=True)
                
            # Also append staged changes if any
            with open("fix.patch", "a", encoding="utf-8") as f:
                subprocess.run(["git", "diff", "--staged"], stdout=f, text=True, check=True)
                
            return f"[AGENT_FINISHED] Solution submitted successfully.\nSummary: {summary}\nPatch generated at fix.patch."
        except Exception as e:
            return format_error(
                reason=f"Failed to generate patch: {str(e)}",
                attempted="submit()",
                hint="Ensure you are inside a git repository."
            )
