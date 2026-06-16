import argparse
import os
import sys

from agent.loop import run_agent


def main():
    parser = argparse.ArgumentParser(description="Recall Agent CLI")
    parser.add_argument("issue", type=str, help="The issue description or task for the agent to solve.")
    parser.add_argument("--dir", type=str, default=".", help="The target directory for the agent to operate in. Defaults to current directory.")
    parser.add_argument("--model", type=str, default=None, help="The LiteLLM model to use. Overrides the default in config.yaml.")
    parser.add_argument("--instance-id", type=str, default=None, help="The instance ID for logging metrics and trajectories.")

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

    # 2. Start the ReAct Loop
    if args.model:
        run_agent(args.issue, model=args.model, instance_id=args.instance_id)
    else:
        # Falls back to DEFAULT_MODEL in config
        run_agent(args.issue, instance_id=args.instance_id)

if __name__ == "__main__":
    main()
