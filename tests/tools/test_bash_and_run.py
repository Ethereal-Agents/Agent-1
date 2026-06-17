import pytest

from tools.bash import BashTool
from tools.run_tests import RunTestsTool


def test_bash_success():
    tool = BashTool()
    result = tool.run(command="echo 'hello from bash'")
    assert "<stdout>\nhello from bash" in result
    assert "<exit_code>0</exit_code>" in result


def test_bash_failure():
    tool = BashTool()
    result = tool.run(command="ls /this_dir_does_not_exist_xyz123")
    assert "<stderr>" in result
    assert "No such file or directory" in result
    assert "<exit_code>" in result
    assert "<exit_code>0</exit_code>" not in result


@pytest.fixture
def temp_test_file(tmp_path):
    d = tmp_path / "test_dir"
    d.mkdir()
    p = d / "test_dummy.py"
    p.write_text(
        "def test_pass():\n    assert True\n\ndef test_fail():\n    assert False, 'This test is supposed to fail'\n"
    )
    return str(d)


def test_run_tests_tool(temp_test_file):
    tool = RunTestsTool()
    result = tool.run(targets=[temp_test_file])

    # Check the structured summary
    assert "<status>FAILED</status>" in result
    assert "<total_passed>1</total_passed>" in result
    assert "<total_failed>1</total_failed>" in result

    # Check the structured failure traceback
    assert "<failure_details>" in result
    assert '<test name="test_dummy.test_fail">' in result
    assert "This test is supposed to fail" in result


def test_bash_timeout():
    tool = BashTool()
    result = tool.run(command="sleep 2", timeout=1)
    assert "Command timed out after 1" in result
    assert "ATTEMPTED: bash(command='sleep 2..." in result


def test_run_tests_missing_target():
    tool = RunTestsTool()
    result = tool.run(targets=["does_not_exist_123.py"])
    assert "<status>PASSED</status>" in result
    assert "<total_passed>0</total_passed>" in result


def test_run_tests_invalid_flag():
    tool = RunTestsTool()
    result = tool.run(targets=["--this-flag-is-invalid-and-will-break-pytest"])
    assert "[TEST EXECUTION FAILED]" in result
    assert "error: unrecognized arguments:" in result
