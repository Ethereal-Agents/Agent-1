from typing import Any, Dict, Type

from pydantic import BaseModel

from tools.environment import ExecutionEnvironment, LocalEnvironment


class BaseTool:
    """Abstract base class for all agent tools."""

    name: str
    description: str
    args_schema: Type[BaseModel]

    def __init__(self, env: ExecutionEnvironment = None):
        self.env = env or LocalEnvironment()

    def run(self, **kwargs) -> str:
        """Executes the tool logic and returns an observation string."""
        raise NotImplementedError

    def to_openai_tool(self) -> Dict[str, Any]:
        """Converts the tool definition to the LiteLLM/OpenAI schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }
