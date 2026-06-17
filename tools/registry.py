from typing import Any, Dict, List

from tools.base import BaseTool
from tools.bash import BashTool
from tools.environment import ExecutionEnvironment
from tools.file_ops import EditTool, ReadFileTool
from tools.run_tests import RunTestsTool
from tools.search import CodeSearchTool
from tools.submit_patch import SubmitPatchTool

# Instantiate all tools
TOOLS: List[BaseTool] = [
    ReadFileTool(),
    EditTool(),
    BashTool(),
    CodeSearchTool(),
    RunTestsTool(),
    SubmitPatchTool(),
]

# Map tool name to tool instance for fast execution
TOOL_MAP: Dict[str, BaseTool] = {tool.name: tool for tool in TOOLS}


def get_openai_tools() -> List[Dict[str, Any]]:
    """Returns the list of tools formatted for the LiteLLM/OpenAI API."""
    return [tool.to_openai_tool() for tool in TOOLS]


def initialize_tools(env: ExecutionEnvironment):
    """Injects the given environment into all registered tools."""
    for tool in TOOLS:
        tool.env = env


def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Executes a tool by name with the given dictionary of arguments."""
    tool = TOOL_MAP.get(name)
    if not tool:
        return f"ERROR: Tool '{name}' not found."
    try:
        # Pydantic parses and validates the arguments dict
        validated_args = tool.args_schema(**arguments)
        # Execute the tool
        return tool.run(**validated_args.model_dump())
    except Exception as e:
        return f"ERROR: Failed to execute '{name}'. Reason: {str(e)}"


def get_env_system_prompt() -> str:
    """Returns the system prompt addition from the active environment, if any."""
    if TOOLS and hasattr(TOOLS[0], "env") and TOOLS[0].env:
        return TOOLS[0].env.get_system_prompt_addition()
    return ""
