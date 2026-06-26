with open("agent/loop.py", "r") as f:
    content = f.read()

import_logging = "import logging\n"
if "import logging" not in content:
    content = content.replace("import litellm\n", "import litellm\nimport logging\n")

silence_code = """
        litellm.suppress_debug_info = True
        litellm.set_verbose = False
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
        logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)
"""

content = content.replace(
    "litellm.suppress_debug_info = True\n        litellm.set_verbose = False", silence_code
)

with open("agent/loop.py", "w") as f:
    f.write(content)
