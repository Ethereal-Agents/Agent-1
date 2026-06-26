with open("agent/loop.py", "r") as f:
    content = f.read()

content = content.replace(
    "# litellm.set_verbose = True",
    "litellm.suppress_debug_info = True\n        litellm.set_verbose = False",
)

with open("agent/loop.py", "w") as f:
    f.write(content)
