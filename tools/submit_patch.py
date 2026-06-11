from pydantic import BaseModel, Field
from tools.base import BaseTool

class SubmitPatchArgs(BaseModel):
    reasoning: str = Field(..., description="The final reasoning and summary of the patch being submitted.")

class SubmitPatchTool(BaseTool):
    name = "submit_patch"
    description = "Submits the patch for testing/verification and ends the ReAct loop."
    args_schema = SubmitPatchArgs

    def run(self, **kwargs) -> str:
        # TODO: Implement the exit logic (this tool is usually intercepted by the loop)
        return "[MOCK] Patch submitted for verification."
