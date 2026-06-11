from pydantic import BaseModel, Field
from tools.base import BaseTool

class BashArgs(BaseModel):
    command: str = Field(..., description="The bash command to execute.")

class BashTool(BaseTool):
    name = "bash"
    description = "Executes a bash command in the project environment."
    args_schema = BashArgs

    def run(self, **kwargs) -> str:
        # TODO: Implement sandbox execution logic
        return "[MOCK] Bash command executed."
