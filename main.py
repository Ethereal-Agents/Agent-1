import argparse
import os
import sys

from agent.loop import run_agent


def main():
    parser = argparse.ArgumentParser(description="Recall Agent CLI")
    parser.add_argument(
        "issue", type=str, help="The issue description or task for the agent to solve."
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="The target directory for the agent to operate in. Defaults to current directory.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="The LiteLLM model to use. Overrides the default in config.yaml.",
    )
    parser.add_argument(
        "--instance-id",
        type=str,
        default=None,
        help="The instance ID for logging metrics and trajectories.",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["local", "docker"],
        default="local",
        help="The execution environment for the agent sandbox.",
    )
    parser.add_argument(
        "--docker-image",
        type=str,
        default="python:3.11-slim",
        help="The docker image to use if --env docker is selected.",
    )
    parser.add_argument(
        "--docker-container",
        type=str,
        default=None,
        help="A pre-existing docker container ID to attach to if --env docker is selected.",
    )

    args = parser.parse_args()

    # 1. Set the working directory
    target_dir = os.path.abspath(args.dir)
    if not os.path.exists(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.")
        sys.exit(1)

    # Changing the python process directory ensures all subprocesses (bash) and file operations
    # relative to the current working directory will operate in the target directory!
    os.chdir(target_dir)
    print("🤖 Starting Recall Agent...")
    print(f"📂 Operating Directory: {target_dir}")
    print(f"🛠️  Environment: {args.env.upper()}")

    # 2. Initialize the Execution Environment
    from tools.environment import DockerEnvironment, LocalEnvironment
    from tools.registry import initialize_tools

    if args.env == "docker":
        env = DockerEnvironment(
            image=args.docker_image,
            container_id=args.docker_container,
            mount_dir=target_dir,
        )
    else:
        env = LocalEnvironment()

    initialize_tools(env)

    # 3. Start the ReAct Loop
    try:
        if args.model:
            run_agent(args.issue, model=args.model, instance_id=args.instance_id)
        else:
            # Falls back to DEFAULT_MODEL in config
            run_agent(args.issue, instance_id=args.instance_id)
    finally:
        if hasattr(env, "cleanup"):
            env.cleanup()


if __name__ == "__main__":
    main()
