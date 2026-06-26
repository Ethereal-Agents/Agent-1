from tools.environment import ExecutionEnvironment, LocalEnvironment


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


def test_execution_environment_abstract_methods():
    class DummyEnvironment(ExecutionEnvironment):
        def run_bash(self, cmd, timeout):
            return super().run_bash(cmd, timeout)

        def read_file(self, path):
            return super().read_file(path)

        def write_file(self, path, content):
            return super().write_file(path, content)

        def get_system_prompt_addition(self):
            return super().get_system_prompt_addition()

    env = DummyEnvironment()
    env.run_bash("echo 'hello'", 5)
    env.read_file("test.txt")
    env.write_file("test.txt", "content")
    env.get_system_prompt_addition()


def test_local_env_prompt():
    env = LocalEnvironment()
    assert "ENVIRONMENT CONTEXT" in env.get_system_prompt_addition()


def test_docker_import_error():
    import sys
    from importlib import reload

    import tools.environment

    # Temporarily hide docker to trigger ImportError
    original_docker = sys.modules.get("docker")
    sys.modules["docker"] = None

    try:
        reload(tools.environment)
        assert tools.environment.docker is None
    finally:
        if original_docker is not None:
            sys.modules["docker"] = original_docker
        else:
            del sys.modules["docker"]
        reload(tools.environment)
