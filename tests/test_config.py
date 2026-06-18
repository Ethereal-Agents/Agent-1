from unittest.mock import mock_open, patch

import config


def test_get_system_prompt():
    with patch("builtins.open", mock_open(read_data="mock_system_prompt")) as m:
        result = config.get_system_prompt()
        m.assert_called_once_with(config.SYSTEM_PROMPT_PATH, "r", encoding="utf-8")
        assert result == "mock_system_prompt"


def test_get_compaction_prompt():
    with patch("builtins.open", mock_open(read_data="mock_compaction_prompt")) as m:
        result = config.get_compaction_prompt()
        m.assert_called_once_with(config.COMPACTION_PROMPT_PATH, "r", encoding="utf-8")
        assert result == "mock_compaction_prompt"


def test_get_test_failure_prompt():
    with patch("builtins.open", mock_open(read_data="mock_failure {test_results}")) as m:
        result = config.get_test_failure_prompt("logs")
        m.assert_called_once_with(config.TEST_FAILURE_PROMPT_PATH, "r", encoding="utf-8")
        assert result == "mock_failure logs"
