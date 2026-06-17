from tools.environment import LocalEnvironment


def test_local_environment_bash():
    env = LocalEnvironment()
    result = env.run_bash("echo 'hello'", timeout=5)
    assert result.returncode == 0
    assert "hello" in result.stdout.strip()


def test_local_environment_file_ops(tmp_path):
    env = LocalEnvironment()
    test_file = tmp_path / "test.txt"
    env.write_file(str(test_file), "test content")
    assert test_file.exists()
    content = env.read_file(str(test_file))
    assert content == "test content"


# NOTE: DockerEnvironment is tested end-to-end via scripts/verify_sandbox.py
# We intentionally omit Docker tests from the core pytest suite so that
# the unit tests run in <1 second and do not require Docker to be installed/running.
