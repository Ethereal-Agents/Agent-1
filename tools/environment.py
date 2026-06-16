import os
import subprocess
import tempfile
from abc import ABC, abstractmethod

try:
    import docker
except ImportError:
    docker = None


class ExecutionEnvironment(ABC):
    @abstractmethod
    def run_bash(self, cmd: str, timeout: int) -> subprocess.CompletedProcess:
        pass

    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        pass


class LocalEnvironment(ExecutionEnvironment):
    def run_bash(self, cmd: str, timeout: int) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

    def read_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


class DockerEnvironment(ExecutionEnvironment):
    def __init__(
        self,
        image: str = None,
        container_id: str = None,
        setup_command: str = None,
        mount_dir: str = None,
    ):
        if docker is None:
            raise ImportError("The 'docker' python package is required. Run 'uv add docker'.")
        self.client = docker.from_env()
        self._owns_container = False

        if container_id:
            self.container = self.client.containers.get(container_id)
        elif image:
            import os

            self._owns_container = True
            mount_path = mount_dir or os.getcwd()
            # Spin up a generic sandbox container and mount the codebase
            self.container = self.client.containers.run(
                image,
                command="sleep infinity",
                detach=True,
                remove=True,
                volumes={mount_path: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
            )
        else:
            raise ValueError("Must provide either image or container_id")

        if setup_command:
            result = self.run_bash(setup_command, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to run setup_command: {result.stderr}")

    def cleanup(self):
        """Stops and removes the container if this environment spun it up."""
        if self._owns_container and getattr(self, "container", None):
            self.container.stop()

    def run_bash(self, cmd: str, timeout: int) -> subprocess.CompletedProcess:
        # We enforce timeout on the host using a subprocess calling the docker cli
        # This is more reliable for timeout enforcement than the docker python SDK exec_run
        docker_cmd = ["docker", "exec", self.container.id, "/bin/bash", "-c", cmd]
        return subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout)

    def read_file(self, path: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_tar_path = os.path.join(tmpdir, "file.tar")
            # This uses the docker CLI for simplicity, as the python SDK get_archive is slightly more complex
            # docker cp container:path dest
            result = subprocess.run(
                ["docker", "cp", f"{self.container.id}:{path}", local_tar_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                if "No such container:path" in result.stderr or "Could not find" in result.stderr:
                    raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")
                raise RuntimeError(f"docker cp failed: {result.stderr}")
            # Actually, docker cp to a file directly grabs the file
            with open(local_tar_path, "r", encoding="utf-8") as f:
                return f.read()

    def write_file(self, path: str, content: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_file_path = os.path.join(tmpdir, os.path.basename(path))
            with open(local_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Make sure target dir exists in container
            target_dir = os.path.dirname(path)
            self.run_bash(f"mkdir -p {target_dir}", timeout=10)
            result = subprocess.run(
                ["docker", "cp", local_file_path, f"{self.container.id}:{path}"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker cp failed: {result.stderr}")
