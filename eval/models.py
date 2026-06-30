"""Data models for the eval harness."""

from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    # Dataset
    dataset: str = "princeton-nlp/SWE-bench_Verified"
    split: str = "test"
    # Execution
    max_workers_grading: int = 4
    max_workers_inference: int = 2
    timeout_per_task: int = 1800
    output_dir: str = "eval_results"
    namespace: str = ""
    # Agent
    model: str = "gemini/gemma-4-31b-it"
    # Budget
    budget_warn_threshold: float = 5.0
    budget_warn_interval_pct: list = field(default_factory=lambda: [50, 80, 100])
    # Resume
    resume: bool = False


@dataclass
class TaskResult:
    instance_id: str
    model_name_or_path: str
    model_patch: str | None  # git diff output; None if agent made no changes
    exit_reason: str  # "submitted" | "max_steps" | "error" | "timeout"
    total_steps: int
    total_tokens: int
    total_cost: float
    duration_seconds: float
    trajectory_path: str  # absolute path to JSONL trajectory file


@dataclass
class GradeReport:
    run_id: str
    total: int
    resolved: int
    unresolved: int
    errored: int
    resolution_rate: float  # 0.0–1.0
    per_instance: dict  # {instance_id: "resolved" | "unresolved" | "error"}


@dataclass
class StatSummary:
    mean: float
    median: float
    p95: float
    total: float

    @classmethod
    def from_values(cls, values: list[float]) -> "StatSummary":
        import statistics

        if not values:
            return cls(0.0, 0.0, 0.0, 0.0)
        sorted_vals = sorted(values)
        idx_95 = int(len(sorted_vals) * 0.95)
        return cls(
            mean=statistics.mean(values),
            median=statistics.median(values),
            p95=sorted_vals[min(idx_95, len(sorted_vals) - 1)],
            total=sum(values),
        )


@dataclass
class EvalMetrics:
    run_id: str
    pass_at_1: float  # primary metric: % resolved
    total_instances: int
    resolved: int
    unresolved: int
    errored: int
    cost: StatSummary
    tokens: StatSummary
    turns: StatSummary
    duration: StatSummary
    exit_reason_counts: dict  # {"submitted": N, "max_steps": N, ...}


# ==============================================================================
# ML Research Bench Data Models
# ==============================================================================


@dataclass
class MLRBConfig:
    tasks_dir: str = "eval/tasks/ml_research_bench"
    docker_image: str = "python:3.11"
    model: str = "gemini/gemma-4-31b-it"
    timeout_per_task: int = 600
    output_dir: str = "eval_results"
    enable_arxiv: bool = False
    max_workers: int = 1
    resume: bool = False


@dataclass
class MLRBGradeResult:
    passed: int
    failed: int
    total: int
    test_score: float
    output_log: str


@dataclass
class MLRBTaskResult:
    task_id: str
    category: str
    difficulty: str
    model_name: str
    model_patch: str | None
    exit_reason: str
    tests_passed: int
    tests_failed: int
    tests_total: int
    test_score: float
    pass_at_1: bool
    total_steps: int
    total_tokens: int
    total_cost: float
    duration_seconds: float
    trajectory_path: str
    pytest_output: str
