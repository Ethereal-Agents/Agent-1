from pydantic import BaseModel, Field

from tools.base import BaseTool


class FinishArgs(BaseModel):
    summary: str = Field(
        ...,
        description="A summary of the changes made and why the issue is resolved.",
    )


class FinishTool(BaseTool):
    name = "finish"
    description = (
        "Signals that you have completed the task. Before calling this, you should "
        "have verified your changes by running the relevant tests. Call this when "
        "you are confident the issue is resolved."
    )
    args_schema = FinishArgs

    def run(self, summary: str, **kwargs) -> str:
        import subprocess

        from tools.utils import format_error

        try:
            # Stage all files so git tracks newly created files
            subprocess.run(["git", "add", "-A"], check=True)

            initial_commit = getattr(self.env, "initial_commit", None)

            # Generate a comprehensive patch against the initial commit
            with open("fix.patch", "w", encoding="utf-8") as f:
                if initial_commit:
                    subprocess.run(["git", "diff", initial_commit], stdout=f, text=True, check=True)
                else:
                    subprocess.run(["git", "diff", "--staged"], stdout=f, text=True, check=True)

            return (
                f"[AGENT_FINISHED] Task completed successfully.\n"
                f"Summary: {summary}\n"
                f"Patch generated at fix.patch."
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to generate patch: {str(e)}",
                attempted="finish()",
                hint="Ensure you are inside a git repository.",
            )
