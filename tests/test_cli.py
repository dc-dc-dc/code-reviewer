import io
import json
import sys
from unittest.mock import patch

import pytest

from code_reviewer.cli import main, parse_args
from code_reviewer.output import ReviewComment


class FakeStdin(io.StringIO):
    """StringIO subclass that overrides isatty to return False."""

    def isatty(self):
        return False


class TestParseArgs:
    def test_defaults(self):
        args = parse_args([])
        assert args.context is None
        assert args.guidelines is None
        assert args.json_output is False

    def test_context_short(self):
        args = parse_args(["-c", "refactoring auth"])
        assert args.context == "refactoring auth"

    def test_context_long(self):
        args = parse_args(["--context", "adding caching"])
        assert args.context == "adding caching"

    def test_guidelines(self):
        args = parse_args(["-g", "rules.md"])
        assert args.guidelines == "rules.md"

    def test_json_flag(self):
        args = parse_args(["--json"])
        assert args.json_output is True

    def test_all_flags(self):
        args = parse_args(["-c", "test", "-g", "rules.md", "--json"])
        assert args.context == "test"
        assert args.guidelines == "rules.md"
        assert args.json_output is True


class TestMain:
    def test_tty_stdin_exits(self, capsys):
        with patch.object(sys.stdin, "isatty", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                main([])
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No diff provided" in captured.err

    def test_empty_stdin_exits(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", FakeStdin(""))
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Empty diff" in captured.err

    def test_plain_output(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", FakeStdin("+ new line"))

        comments = [
            ReviewComment(file="a.py", line=1, severity="warning", comment="issue here"),
        ]

        with patch("code_reviewer.cli.review", return_value=comments):
            main(["-c", "test change"])

        captured = capsys.readouterr()
        assert "[warning]" in captured.out
        assert "a.py:1" in captured.out

    def test_json_output(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", FakeStdin("+ new line"))

        comments = [
            ReviewComment(file="b.py", line=5, severity="error", comment="bug"),
        ]

        with patch("code_reviewer.cli.review", return_value=comments):
            main(["--json"])

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["file"] == "b.py"

    def test_guidelines_file(self, monkeypatch, capsys, tmp_path):
        guidelines_file = tmp_path / "rules.md"
        guidelines_file.write_text("Always check error handling.")

        monkeypatch.setattr("sys.stdin", FakeStdin("+ code"))

        with patch("code_reviewer.cli.review", return_value=[]) as mock_review:
            main(["-g", str(guidelines_file)])

        _, kwargs = mock_review.call_args
        assert kwargs["guidelines"] == "Always check error handling."
