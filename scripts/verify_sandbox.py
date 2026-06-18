from tools.environment import DockerEnvironment
from tools.registry import execute_tool, initialize_tools


def main():
    print("1. Spinning up Docker Sandbox for dummy_target...")
    # Spin up container, mount dummy_target, and install pytest natively inside the Linux container!
    env = DockerEnvironment(
        image="python:3.11-slim",
        mount_dir="/Users/ayushdubey/Source/dummy_target",
        setup_command="pip install pytest",
    )

    print("   Container running. Injecting environment into tools...")
    initialize_tools(env)

    print("\n2. Executing Bash Tool (listing workspace)...")
    bash_result = execute_tool("bash", {"command": "ls -la /workspace"})
    print("Agent Bash Output:")
    print(bash_result.strip())

    print("\n3. Executing RunTests Tool (running pytest against test_math.py)...")
    test_result = execute_tool("run_tests", {"targets": ["/workspace/test_math.py"]})
    print("Agent Test Output (XML Parsed Summary):")
    print(test_result.strip())

    print("\n4. Cleaning up...")
    env.cleanup()
    print("Done!")


if __name__ == "__main__":
    main()
