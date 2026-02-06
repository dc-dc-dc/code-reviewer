from code_reviewer.prompt import build_system_prompt, build_user_prompt


class TestBuildSystemPrompt:
    def test_without_guidelines(self):
        result = build_system_prompt()
        assert "code reviewer" in result
        assert "JSON array" in result

    def test_with_guidelines(self):
        result = build_system_prompt("Always check for SQL injection.")
        assert "Additional review guidelines:" in result
        assert "Always check for SQL injection." in result


class TestBuildUserPrompt:
    def test_diff_only(self):
        result = build_user_prompt("+ added line")
        assert "```diff" in result
        assert "+ added line" in result

    def test_with_context(self):
        result = build_user_prompt("+ added line", context="refactoring auth")
        assert "Context: refactoring auth" in result
        assert "```diff" in result

    def test_without_context(self):
        result = build_user_prompt("+ added line")
        assert "Context:" not in result
