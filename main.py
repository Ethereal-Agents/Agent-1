import argparse
import os
import sys

from agent.loop import run_agent


def main():
    parser = argparse.ArgumentParser(description="Recall Agent CLI")
    parser.add_argument(
        "issue",
        type=str,
        nargs="?",
        default=None,
        help="The issue description or task for the agent to solve.",
    )
    parser.add_argument(
        "--issue-file",
        type=str,
        default=None,
        help="Path to a text file containing the issue description.",
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

    args = parser.parse_args()

    if args.issue_file:
        try:
            with open(args.issue_file, "r", encoding="utf-8") as f:
                issue_text = f.read()
        except Exception as e:
            print(f"Error reading issue file: {e}")
            sys.exit(1)
    elif args.issue:
        issue_text = args.issue
    else:
        parser.error("You must provide either an issue string or an --issue-file.")

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

    # 2. Start the ReAct Loop
    if args.model:
        run_agent(issue_text, model=args.model, instance_id=args.instance_id)
    else:
        # Falls back to DEFAULT_MODEL in config
        run_agent(issue_text, instance_id=args.instance_id)


if __name__ == "__main__":
    main()
