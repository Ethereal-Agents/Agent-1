#!/usr/bin/env bash
# Convenience script for common eval workflows.
# Run from the Agent-1 project root.
#
# Usage:
#   ./scripts/run_eval.sh                          # quick 10-instance dev eval
#   ./scripts/run_eval.sh --tier 50                # 50-instance mid-scale eval
#   ./scripts/run_eval.sh --inference-only         # run agent only, skip grading
#   ./scripts/run_eval.sh --grade-only \           # grade existing predictions
#     --predictions eval_results/dev-001/predictions.jsonl --run-id dev-001

set -euo pipefail

cd "$(dirname "$0")/.."

RUN_ID="dev-$(date +%Y%m%d_%H%M%S)"

echo "Starting eval run: $RUN_ID"
uv run python -m eval.run_eval \
  --tier 10 \
  --run-id "$RUN_ID" \
  "$@"
