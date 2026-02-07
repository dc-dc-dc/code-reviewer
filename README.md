# code-reviewer

AI-powered code review from git diffs. Pipe a diff in, get structured review comments out.

Supports Anthropic (Claude), OpenAI, and local OpenAI-compatible endpoints (Ollama, vLLM, LM Studio).

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

## Development

```bash
uv sync
uv run pytest
```
