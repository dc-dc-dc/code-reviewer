import json
import os
from unittest.mock import MagicMock, patch

import pytest

from code_reviewer.llm import (
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_MODELS,
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
