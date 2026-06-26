# Hybrid Docker Sandbox & Execution Environment Plan

## 1. Overview
This document outlines the architecture for the `recall-agent`'s execution environment. Instead of hardcoding tools to execute directly on the host machine via `subprocess`, we have introduced an abstraction layer. This "Hybrid Approach" allows the agent's logic (LLM loops, prompt generation) to run natively on the host (for easy debugging and orchestration) while executing its side-effects (bash commands, file edits, testing) securely within isolated environments dictated by a configuration file.

## 2. Architecture & The Hybrid Approach

We defined an abstract `ExecutionEnvironment` class with implementations for different backends. This design is built to be completely generic and customizable, perfectly suited for autonomous agents.

### Supported Modes
1. **Local Mode (`LocalEnvironment`)**
   - Uses Python's native `subprocess` and local file I/O (`open()`, `shutil`).
   - Best for fast day-to-day testing of agent logic on trusted repositories without overhead.
2. **Docker Mode (`DockerEnvironment` - Auto-provisioned)**
   - The system spins up a fresh, generic Docker container (e.g., `python:3.11-slim`) via the Docker SDK.
   - The user's active codebase is seamlessly volume-mounted into `/workspace` inside the container.
   - The agent uses `docker exec` for commands and `docker cp` for files.
   - Best for general sandboxed experimentation on your own code.
3. **Docker-Existing Mode (`DockerEnvironment` - Pre-provisioned)**
   - The system attaches to an already running container (e.g., a SWE-bench container).
   - Functions identically to the Auto-provisioned mode, but skips the container creation and volume mounting step.
   - Strictly used for external evaluations and benchmarking against third-party containers.

## 3. Component Design

### `main.py` CLI Integration
The environment is initialized dynamically via the main entrypoint using CLI arguments:
- `--env {local,docker}`
- `--docker-image`
- `--docker-container`

The entrypoint parses these arguments, instantiates the proper environment, injects it into all tools via `initialize_tools()`, and wraps execution in a `try...finally` block to guarantee graceful `cleanup()` of any temporary Docker containers upon exit.

### `tools/environment.py`
The concrete abstraction layer powering all operations.
```python
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
```
The `initialize_tools(env)` function dynamically injects the chosen backend environment into every agent tool (e.g., `BashTool`, `EditTool`, `RunTestsTool`).

## 4. Architectural Decisions & Edge Cases Resolved

Throughout the implementation, we addressed several critical architectural challenges and edge cases:

1. **State Persistence in Docker (`docker exec`)**
   - **Decision:** Stateless execution. We do not maintain a brittle persistent pseudo-terminal (PTY). Each command is fresh. The agent will be instructed via the system prompt to use absolute paths or chained commands (e.g., `cd src && ls`).
2. **File Synchronization Strategy (`docker cp`)**
   - **Decision:** To read or edit a file, the `DockerEnvironment` pulls the file to the host's `/tmp` directory using `docker cp`, modifies it locally, and pushes it back into the container.
   - **Edge Case Resolved:** We explicitly intercept `docker cp` errors and map them to standard Python `FileNotFoundError`s. This ensures the Agent's `EditTool` produces uniform, helpful hint messages regardless of whether the backend is Local or Docker.
3. **Test Extraction Boundary Leaks (`run_tests.py`)**
   - **Edge Case Resolved:** The `RunTestsTool` originally attempted to run `sys.executable -m pytest` and check `os.path.exists()` for the generated XML file. Both of these leaked the host Mac's system paths into the container. We refactored the tool to execute the generic `python -m pytest` inside the container, generate the XML report to `/tmp/`, and extract it via `self.env.read_file()`.
4. **Timeouts inside Docker**
   - **Decision:** Strict Host-enforced Timeouts. The timeout logic (e.g., 120s) is enforced by the Python `subprocess` wrapper running on the host Mac that executes the `docker exec` CLI command. This prevents infinite hanging and guarantees deterministic execution times.
5. **Environment-Aware System Prompts**
   - **Decision:** Instead of masking generic Docker `stderr` outputs or writing brittle regex translations to trick the LLM into thinking it's not in a container, we implemented a `get_system_prompt_addition()` method. This dynamically injects a string into the LLM's system prompt (e.g. "You are running in a Docker container, file ops are proxied via docker cp"). This transparently informs the LLM exactly how to interpret any leaked abstraction errors without us having to write error-translation logic.

## 5. Tradeoffs Summary
- **Local:** Fastest, easiest to debug, but zero security against malicious LLM actions.
- **Docker:** Highly secure, generic, and reliable (via `docker cp` and absolute pathing), but incurs a minor execution latency penalty for copying files across the sandbox boundary.
