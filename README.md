# code-reviewer

AI-powered code review from git diffs. Pipe a diff in, get structured review comments out.

Supports Anthropic (Claude), OpenAI, and local OpenAI-compatible endpoints (Ollama, vLLM, LM Studio).


[![Test](https://github.com/dc-dc-dc/code-reviewer/actions/workflows/test.yml/badge.svg)](https://github.com/dc-dc-dc/code-reviewer/actions/workflows/test.yml)

## Install

```bash
uv tool install .
```

## Usage

```bash
# Review staged changes (uses local Ollama by default)
git diff --staged | code-reviewer

# Add context about the change
git diff | code-reviewer --context "refactoring auth module"

# Use a guidelines file
git diff | code-reviewer --guidelines ./review-rules.md

# JSON output
git diff HEAD~1 | code-reviewer --json

# Combine flags
git diff --staged | code-reviewer -c "adding caching" -g ./rules.md --json
```

## Configuration

All configuration is done through environment variables.

| Variable | Description | Default |
|---|---|---|
| `CODE_REVIEWER_PROVIDER` | `local`, `openai`, or `anthropic` | `local` |
| `CODE_REVIEWER_MODEL` | Model name | `llama3` (local), `gpt-4o` (openai), `claude-sonnet-4-5-20250929` (anthropic) |
| `CODE_REVIEWER_BASE_URL` | API base URL for local/openai providers | `http://localhost:11434/v1` |
| `ANTHROPIC_API_KEY` | API key for Anthropic | — |
| `OPENAI_API_KEY` | API key for OpenAI | — |

### Examples

```bash
# Use Anthropic
export CODE_REVIEWER_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Use OpenAI
export CODE_REVIEWER_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Use a local model via Ollama
export CODE_REVIEWER_PROVIDER=local
export CODE_REVIEWER_MODEL=codellama
```

## CLI Flags

| Flag | Short | Description |
|---|---|---|
| `--context` | `-c` | Free-text description of the change |
| `--guidelines` | `-g` | Path to a file containing review guidelines/rules |
| `--json` | | Output review comments as JSON |

## GitHub Actions

Add automated code review to your PRs with inline comments. Add `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) as a repository secret, then create `.github/workflows/code-review.yml`:

```yaml
name: Code Review

on:
  pull_request:
    branches: [main]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v5

      - name: Install code-reviewer
        run: uv tool install https://github.com/dc-dc-dc/code-reviewer/releases/download/v0.1/code_reviewer-0.1.0-py3-none-any.whl

      - name: Review
        env:
          CODE_REVIEWER_PROVIDER: anthropic
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GH_TOKEN: ${{ github.token }}
        run: |
          COMMENTS=$(git diff origin/main...HEAD | code-reviewer --json)

          # Skip if no comments
          if [ "$(echo "$COMMENTS" | jq length)" -eq 0 ]; then
            echo "No review comments."
            exit 0
          fi

          # Format all comments into the review body
          BODY=$(echo "$COMMENTS" | jq -r '.[] |
            "### " + (.severity // "suggestion") + "\n" +
            "`" + .file + (if .line then ":" + (.line | tostring) else "" end) + "`\n\n" +
            .comment + "\n"')

          # Post as a PR review comment
          gh api \
            "repos/${{ github.repository }}/pulls/${{ github.event.pull_request.number }}/reviews" \
            -f event="COMMENT" \
            -f body="$BODY"
```

See [examples/github-actions.yml](examples/github-actions.yml) for the full workflow file.

## Development

```bash
pkg install
pkg test
pkg build
```
