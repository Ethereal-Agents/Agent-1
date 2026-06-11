from pydantic import BaseModel, Field
from tools.base import BaseTool

class CodeSearchArgs(BaseModel):
    query: str = Field(..., description="The string or regex pattern to search for across the codebase.")
    directory: str = Field(".", description="The directory to search within (default is root).")

class CodeSearchTool(BaseTool):
    name = "code_search"
    description = "Searches the codebase using ripgrep."
    args_schema = CodeSearchArgs

    def run(self, **kwargs) -> str:
        # TODO: Implement ripgrep wrapper logic
        return "[MOCK] Code search executed."
