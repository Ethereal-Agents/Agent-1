import re
from dataclasses import dataclass


@dataclass
class InterceptionResult:
    """Returned by the guard for every command check."""
    blocked: bool
    message: str


class DestructiveCommandGuard:
    """
    Stateless-from-agent's-perspective guard that intercepts destructive
    commands, blocks them, and returns nudges with safer alternatives.

    Tracks repeat attempts per (pattern, target) to escalate nudge severity.
    """

    RULES = [
        # (name, pattern, context_check, nudge)
        (
            "rm_tracked",
            r"\brm\s+(?:-[rfvI]+\s+)*(.+)",
            "git_tracked",
            "ERROR: `{command}` targets the Git-tracked file `{target}`.\n"
            "HINT: To discard recent edits, use `git restore {target}`. "
            "To permanently remove from the repo, use `git rm {target}`.",
        ),
        (
            "git_reset_hard",
            r"\bgit\s+reset\s+--hard",
            "always",
            "ERROR: `git reset --hard` will permanently destroy all uncommitted work.\n"
            "HINT: Use `git stash` to safely set aside changes. "
            "If you must reset, run `git stash` first.",
        ),
        (
            "git_checkout_wildcard",
            r"\bgit\s+(?:checkout|restore)\s+(?:--\s+)?[.*]",
            "always",
            "ERROR: This command will discard ALL unstaged changes in the directory.\n"
            "HINT: To revert a specific file, use `git restore <specific_file>`. "
            "To stash everything safely, use `git stash`.",
        ),
        (
            "git_clean",
            r"\bgit\s+clean\s+-[fdxX]+",
            "has_untracked",
            "ERROR: `git clean` will permanently delete all untracked files.\n"
            "HINT: You may lose newly created files. "
            "Use `git stash --include-untracked` to safely store them.",
        ),
        (
            "shell_overwrite",
            r"(?:echo\s+.*|cat\s+/dev/null)\s*>\s*(\S+)",
            "git_tracked",
            "ERROR: You are attempting to overwrite or truncate `{target}` via shell redirection.\n"
            "HINT: Use the provided file editing tools to modify file contents safely.",
        ),
    ]

    ESCALATION_PREFIX_2 = (
        "WARNING: You have already attempted this destructive action. "
        "STOP retrying and use the suggested alternative.\n\n"
    )
    ESCALATION_PREFIX_3 = (
        "FATAL: This command has been blocked {count} times. "
        "You MUST use a different approach. Continuing to retry will waste your remaining steps.\n\n"
    )

    def __init__(self, env=None):
        self._env = env
        self._attempt_counts: dict[str, int] = {}  # "rule_name:target" -> count

    def check(self, command: str) -> InterceptionResult:
        """Check a command before execution. Returns blocked=True with a nudge if dangerous."""
        for name, pattern, context_check, nudge_template in self.RULES:
            match = re.search(pattern, command)
            if not match:
                continue

            if not self._should_block(command, match, context_check):
                continue

            target = match.group(1).strip().strip("'\"") if match.lastindex else ""
            counter_key = f"{name}:{target}"
            self._attempt_counts[counter_key] = self._attempt_counts.get(counter_key, 0) + 1
            count = self._attempt_counts[counter_key]

            nudge = nudge_template.format(command=command.strip(), target=target)

            if count == 2:
                nudge = self.ESCALATION_PREFIX_2 + nudge
            elif count >= 3:
                nudge = self.ESCALATION_PREFIX_3.format(count=count) + nudge

            return InterceptionResult(blocked=True, message=nudge)

        return InterceptionResult(blocked=False, message="")

    def _should_block(self, command: str, match: re.Match, context_check: str) -> bool:
        """Run context-aware check. Returns True if the command should be blocked."""
        if context_check == "always":
            return True

        if self._env is None:
            return True  # no env available — block conservatively

        if context_check == "git_tracked":
            target = match.group(1).strip().strip("'\"") if match.lastindex else ""
            if not target:
                return True
            try:
                result = self._env.run_bash(
                    f"git ls-files --error-unmatch {target} 2>/dev/null", timeout=5
                )
                return result.returncode == 0  # tracked → block
            except Exception:
                return True

        if context_check == "has_untracked":
            try:
                result = self._env.run_bash(
                    "git ls-files --others --exclude-standard | head -1", timeout=5
                )
                return bool(result.stdout.strip())
            except Exception:
                return True

        return True
