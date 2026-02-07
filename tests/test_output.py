import json

from code_reviewer.output import ReviewComment, format_json, format_plain


def _make_comment(**overrides):
    defaults = {
        "file": "src/main.py",
        "line": 10,
        "severity": "warning",
        "comment": "Unused variable.",
    }
    defaults.update(overrides)
    return ReviewComment(**defaults)


class TestFormatPlain:
    def test_empty_list(self):
        assert format_plain([]) == "No issues found."

    def test_single_comment(self):
        result = format_plain([_make_comment()])
        assert "[warning]" in result
        assert "src/main.py:10" in result
        assert "Unused variable." in result

    def test_comment_without_line(self):
        result = format_plain([_make_comment(line=None)])
        assert "src/main.py" in result
        assert ":None" not in result

    def test_severity_symbols(self):
        for severity in ("error", "warning", "suggestion"):
            result = format_plain([_make_comment(severity=severity)])
            assert f"[{severity}]" in result

    def test_multiple_comments(self):
        comments = [
            _make_comment(severity="error", comment="Bug found."),
            _make_comment(severity="suggestion", comment="Consider refactoring."),
        ]
        result = format_plain(comments)
        assert "Bug found." in result
        assert "Consider refactoring." in result


class TestFormatJson:
    def test_empty_list(self):
        assert json.loads(format_json([])) == []

    def test_single_comment(self):
        result = json.loads(format_json([_make_comment()]))
        assert len(result) == 1
        assert result[0]["file"] == "src/main.py"
        assert result[0]["line"] == 10
        assert result[0]["severity"] == "warning"
        assert result[0]["comment"] == "Unused variable."

    def test_preserves_null_line(self):
        result = json.loads(format_json([_make_comment(line=None)]))
        assert result[0]["line"] is None
