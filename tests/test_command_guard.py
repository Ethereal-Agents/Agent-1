from unittest.mock import MagicMock

import pytest

from tools.command_guard import DestructiveCommandGuard


@pytest.fixture
def mock_env():
    env = MagicMock()
    return env


@pytest.fixture
def guard(mock_env):
    return DestructiveCommandGuard(env=mock_env)


def create_mock_result(returncode, stdout=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


def test_rm_tracked_file_blocked(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)
    result = guard.check("rm foo.py")
    assert result.blocked is True
    assert "git restore foo.py" in result.message
    mock_env.run_bash.assert_called_once_with(
        "git ls-files --error-unmatch foo.py 2>/dev/null", timeout=5
    )


def test_rm_untracked_file_allowed(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(1)
    result = guard.check("rm scratch.tmp")
    assert result.blocked is False
    assert result.message == ""


def test_rm_rf_tracked_file_blocked(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)
    result = guard.check("rm -rf src/")
    assert result.blocked is True


def test_git_reset_hard_blocked(guard):
    result = guard.check("git reset --hard")
    assert result.blocked is True
    assert "git stash" in result.message


def test_git_reset_hard_head_blocked(guard):
    result = guard.check("git reset --hard HEAD")
    assert result.blocked is True
    assert "git stash" in result.message


def test_git_checkout_dot_blocked(guard):
    result = guard.check("git checkout .")
    assert result.blocked is True
    assert "specific file" in result.message


def test_git_restore_dot_blocked(guard):
    result = guard.check("git restore .")
    assert result.blocked is True


def test_git_restore_specific_file_allowed(guard):
    result = guard.check("git restore foo.py")
    assert result.blocked is False


def test_git_clean_fd_blocked(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0, "untracked.txt\n")
    result = guard.check("git clean -fd")
    assert result.blocked is True
    assert "stash --include-untracked" in result.message


def test_git_clean_fd_allowed(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0, "")
    result = guard.check("git clean -fd")
    assert result.blocked is False


def test_shell_overwrite_blocked(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)
    result = guard.check('echo "" > foo.py')
    assert result.blocked is True
    assert "provided file editing tools" in result.message


def test_safe_commands_allowed(guard, mock_env):
    assert guard.check("ls -la").blocked is False
    assert guard.check("git status").blocked is False
    assert guard.check("python test.py").blocked is False


def test_escalation_2nd_attempt(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)
    guard.check("rm foo.py")
    result = guard.check("rm foo.py")
    assert result.blocked is True
    assert result.message.startswith("WARNING: You have already attempted")


def test_escalation_3rd_attempt(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)
    guard.check("rm foo.py")
    guard.check("rm foo.py")
    result = guard.check("rm foo.py")
    assert result.blocked is True
    assert result.message.startswith("FATAL: This command has been blocked 3 times")


def test_different_targets_track_separately(guard, mock_env):
    mock_env.run_bash.return_value = create_mock_result(0)

    # First attempt for foo.py
    result1 = guard.check("rm foo.py")
    assert not result1.message.startswith("WARNING")

    # First attempt for bar.py
    result2 = guard.check("rm bar.py")
    assert not result2.message.startswith("WARNING")


def test_no_env_blocks_conservatively():
    guard_no_env = DestructiveCommandGuard(env=None)
    result = guard_no_env.check("rm foo.py")
    assert result.blocked is True


def test_git_tracked_no_target(guard):
    import re

    match = re.match(r"rm(.*)", "rm")
    assert guard._should_block("rm", match, "git_tracked") is True


def test_git_tracked_exception(guard, mock_env):
    mock_env.run_bash.side_effect = Exception("git failed")
    result = guard.check("rm foo.py")
    assert result.blocked is True


def test_has_untracked_exception(guard, mock_env):
    mock_env.run_bash.side_effect = Exception("git failed")
    result = guard.check("git clean -fd")
    assert result.blocked is True


def test_unknown_context_check(guard):
    import re

    match = re.match(r"(rm)", "rm")
    assert guard._should_block("rm", match, "unknown_check") is True
