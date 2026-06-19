from eval.dataset import filter_by_instance_ids, format_task_prompt
from eval.models import StatSummary


def test_format_task_prompt():
    instance = {
        "repo": "test/repo",
        "problem_statement": "This is a bug.",
        "hints_text": "Look at file.py",
    }
    prompt = format_task_prompt(instance)
    assert "Repository: test/repo" in prompt
    assert "## Issue\nThis is a bug." in prompt
    assert "## Hints\nLook at file.py" in prompt


def test_format_task_prompt_no_hints():
    instance = {"repo": "test/repo", "problem_statement": "This is a bug.", "hints_text": ""}
    prompt = format_task_prompt(instance)
    assert "Repository: test/repo" in prompt
    assert "## Issue\nThis is a bug." in prompt
    assert "## Hints" not in prompt


def test_filter_by_instance_ids():
    instances = [{"instance_id": "a"}, {"instance_id": "b"}, {"instance_id": "c"}]
    filtered = filter_by_instance_ids(instances, ["a", "c", "d"])
    ids = [i["instance_id"] for i in filtered]
    assert "a" in ids
    assert "c" in ids
    assert "b" not in ids
    assert len(filtered) == 2


def test_stat_summary():
    s = StatSummary.from_values([1.0, 2.0, 3.0, 4.0, 5.0])
    assert s.mean == 3.0
    assert s.median == 3.0
    assert s.p95 == 5.0
    assert s.total == 15.0


def test_stat_summary_empty():
    s = StatSummary.from_values([])
    assert s.mean == 0.0
    assert s.median == 0.0
    assert s.p95 == 0.0
    assert s.total == 0.0
