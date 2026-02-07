import json
import os
from unittest.mock import MagicMock, patch

import pytest

from code_reviewer.llm import (
    BATCH_POLL_INTERVAL,
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_MODELS,
    _call_anthropic,
    _get_model,
    _get_provider,
    _parse_comments,
    review,
)
from code_reviewer.output import ReviewComment


class TestGetProvider:
    def test_defaults_to_local(self, monkeypatch):
        monkeypatch.delenv("CODE_REVIEWER_PROVIDER", raising=False)
        assert _get_provider() == "local"

    def test_reads_env(self, monkeypatch):
        monkeypatch.setenv("CODE_REVIEWER_PROVIDER", "anthropic")
        assert _get_provider() == "anthropic"


class TestGetModel:
    def test_default_models(self, monkeypatch):
        monkeypatch.delenv("CODE_REVIEWER_MODEL", raising=False)
        for provider, expected in DEFAULT_MODELS.items():
            assert _get_model(provider) == expected

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CODE_REVIEWER_MODEL", "my-model")
        assert _get_model("local") == "my-model"


class TestParseComments:
    def test_valid_json(self):
        raw = json.dumps([
            {"file": "a.py", "line": 1, "severity": "error", "comment": "bug"},
        ])
        result = _parse_comments(raw)
        assert len(result) == 1
        assert result[0] == ReviewComment(file="a.py", line=1, severity="error", comment="bug")

    def test_empty_array(self):
        assert _parse_comments("[]") == []

    def test_no_json_found(self):
        assert _parse_comments("no json here") == []

    def test_json_with_surrounding_text(self):
        raw = 'Here are my findings:\n[{"file": "b.py", "line": null, "comment": "ok"}]\nDone.'
        result = _parse_comments(raw)
        assert len(result) == 1
        assert result[0].file == "b.py"
        assert result[0].line is None
        assert result[0].severity == "suggestion"

    def test_missing_line_defaults_to_none(self):
        raw = json.dumps([{"file": "c.py", "comment": "test"}])
        result = _parse_comments(raw)
        assert result[0].line is None

    def test_fallback_key_message(self):
        raw = json.dumps([{"file": "d.py", "message": "use message key"}])
        result = _parse_comments(raw)
        assert result[0].comment == "use message key"

    def test_fallback_key_description(self):
        raw = json.dumps([{"file": "d.py", "description": "use desc key"}])
        result = _parse_comments(raw)
        assert result[0].comment == "use desc key"

    def test_fallback_key_text(self):
        raw = json.dumps([{"file": "d.py", "text": "use text key"}])
        result = _parse_comments(raw)
        assert result[0].comment == "use text key"

    def test_skips_item_with_no_comment(self):
        raw = json.dumps([{"file": "d.py", "line": 1}])
        result = _parse_comments(raw)
        assert result == []

    def test_missing_file_defaults_to_unknown(self):
        raw = json.dumps([{"comment": "orphan comment"}])
        result = _parse_comments(raw)
        assert result[0].file == "unknown"


class TestCallAnthropic:
    def _make_mock_client(self, processing_calls_before_done=0, result_type="succeeded", result_text="[]"):
        client = MagicMock()

        batch_pending = MagicMock()
        batch_pending.processing_status = "in_progress"
        batch_pending.id = "batch_123"

        batch_done = MagicMock()
        batch_done.processing_status = "ended"
        batch_done.id = "batch_123"

        client.messages.batches.create.return_value = batch_pending

        retrieve_returns = [batch_pending] * processing_calls_before_done + [batch_done]
        client.messages.batches.retrieve.side_effect = retrieve_returns

        result_item = MagicMock()
        result_item.custom_id = "review"
        result_item.result.type = result_type
        if result_type == "succeeded":
            result_item.result.message.content = [MagicMock(text=result_text)]
        client.messages.batches.results.return_value = [result_item]

        return client

    @patch("code_reviewer.llm.time.sleep")
    def test_batch_success(self, mock_sleep):
        client = self._make_mock_client(
            processing_calls_before_done=1,
            result_text='[{"file": "a.py", "line": 1, "severity": "error", "comment": "bug"}]',
        )

        with patch("code_reviewer.llm.Anthropic", return_value=client):
            result = _call_anthropic("system", "user", "model")

        assert "bug" in result
        client.messages.batches.create.assert_called_once()
        assert client.messages.batches.retrieve.call_count == 2
        mock_sleep.assert_called_once_with(BATCH_POLL_INTERVAL)

    @patch("code_reviewer.llm.time.sleep")
    def test_batch_immediate_completion(self, mock_sleep):
        client = self._make_mock_client(processing_calls_before_done=0, result_text="[]")

        with patch("code_reviewer.llm.Anthropic", return_value=client):
            result = _call_anthropic("system", "user", "model")

        assert result == "[]"
        mock_sleep.assert_not_called()

    @patch("code_reviewer.llm.time.sleep")
    def test_batch_timeout(self, mock_sleep):
        client = MagicMock()
        batch = MagicMock()
        batch.id = "batch_123"
        batch.processing_status = "in_progress"
        client.messages.batches.create.return_value = batch
        client.messages.batches.retrieve.return_value = batch

        with patch("code_reviewer.llm.Anthropic", return_value=client):
            with pytest.raises(TimeoutError):
                _call_anthropic("system", "user", "model")

    @patch("code_reviewer.llm.time.sleep")
    def test_batch_errored_result(self, mock_sleep):
        client = self._make_mock_client(result_type="errored")

        with patch("code_reviewer.llm.Anthropic", return_value=client):
            with pytest.raises(RuntimeError, match="errored"):
                _call_anthropic("system", "user", "model")

    @patch("code_reviewer.llm.time.sleep")
    def test_batch_no_results(self, mock_sleep):
        client = MagicMock()
        batch = MagicMock()
        batch.id = "batch_123"
        batch.processing_status = "ended"
        client.messages.batches.create.return_value = batch
        client.messages.batches.retrieve.return_value = batch
        client.messages.batches.results.return_value = []

        with patch("code_reviewer.llm.Anthropic", return_value=client):
            with pytest.raises(RuntimeError, match="no results"):
                _call_anthropic("system", "user", "model")


class TestReview:
    def test_local_provider(self, monkeypatch):
        monkeypatch.delenv("CODE_REVIEWER_PROVIDER", raising=False)
        monkeypatch.delenv("CODE_REVIEWER_BASE_URL", raising=False)
        monkeypatch.delenv("CODE_REVIEWER_MODEL", raising=False)

        response_json = json.dumps([
            {"file": "x.py", "line": 5, "severity": "warning", "comment": "issue"},
        ])

        with patch("code_reviewer.llm._call_openai", return_value=response_json) as mock_call:
            result = review("diff content", context="test context")
            mock_call.assert_called_once()
            args, kwargs = mock_call.call_args
            assert kwargs["base_url"] == DEFAULT_LOCAL_BASE_URL
            assert kwargs["api_key"] == "not-needed"

        assert len(result) == 1
        assert result[0].file == "x.py"

    def test_openai_provider(self, monkeypatch):
        monkeypatch.setenv("CODE_REVIEWER_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("CODE_REVIEWER_BASE_URL", raising=False)

        response_json = json.dumps([])

        with patch("code_reviewer.llm._call_openai", return_value=response_json) as mock_call:
            result = review("diff")
            mock_call.assert_called_once()
            _, kwargs = mock_call.call_args
            assert kwargs["api_key"] == "sk-test"
            assert kwargs["base_url"] is None

        assert result == []

    def test_anthropic_provider(self, monkeypatch):
        monkeypatch.setenv("CODE_REVIEWER_PROVIDER", "anthropic")

        response_json = json.dumps([
            {"file": "a.py", "line": 1, "severity": "error", "comment": "bad"},
        ])

        with patch("code_reviewer.llm._call_anthropic", return_value=response_json) as mock_call:
            result = review("diff", guidelines="be strict")
            mock_call.assert_called_once()

        assert len(result) == 1

    def test_with_guidelines(self, monkeypatch):
        monkeypatch.delenv("CODE_REVIEWER_PROVIDER", raising=False)

        response_json = json.dumps([])

        with patch("code_reviewer.llm._call_openai", return_value=response_json) as mock_call:
            review("diff", guidelines="check for XSS")
            args = mock_call.call_args[0]
            system_prompt = args[0]
            assert "check for XSS" in system_prompt
