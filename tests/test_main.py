import pytest
import sys
from unittest.mock import patch, mock_open
import main


def test_main_with_issue_string():
    with patch("sys.argv", ["main.py", "Fix the bug"]):
        with patch("main.run_agent") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.chdir"):
                    main.main()
                    mock_run.assert_called_once_with("Fix the bug", instance_id=None)


def test_main_with_issue_file(tmp_path):
    issue_file = tmp_path / "issue.txt"
    issue_file.write_text("Fix the file bug", encoding="utf-8")

    with patch("sys.argv", ["main.py", "--issue-file", str(issue_file)]):
        with patch("main.run_agent") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.chdir"):
                    main.main()
                    mock_run.assert_called_once_with("Fix the file bug", instance_id=None)


def test_main_missing_both(capsys):
    with patch("sys.argv", ["main.py"]):
        with pytest.raises(SystemExit) as exc:
            main.main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "You must provide either an issue string or an --issue-file" in captured.err


def test_main_issue_file_read_error(capsys):
    with patch("sys.argv", ["main.py", "--issue-file", "/nonexistent/file.txt"]):
        with pytest.raises(SystemExit) as exc:
            main.main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error reading issue file:" in captured.out


def test_main_directory_not_exists(capsys):
    with patch("sys.argv", ["main.py", "Fix the bug", "--dir", "/invalid/dir"]):
        with patch("os.path.exists", return_value=False):
            with pytest.raises(SystemExit) as exc:
                main.main()
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "Error: Directory" in captured.out
            assert "does not exist." in captured.out


def test_main_with_model():
    with patch("sys.argv", ["main.py", "Fix the bug", "--model", "gpt-4"]):
        with patch("main.run_agent") as mock_run:
            with patch("os.path.exists", return_value=True):
                with patch("os.chdir"):
                    main.main()
                    mock_run.assert_called_once_with("Fix the bug", model="gpt-4", instance_id=None)
