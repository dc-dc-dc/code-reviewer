import json
import os
import re
import time

from anthropic import Anthropic

from code_reviewer.output import ReviewComment
from code_reviewer.prompt import build_system_prompt, build_user_prompt

DEFAULT_MODELS = {
    "local": "llama3",
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-5-20250929",
}

DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


def _get_provider() -> str:
    return os.environ.get("CODE_REVIEWER_PROVIDER", "local")


def _get_model(provider: str) -> str:
    return os.environ.get("CODE_REVIEWER_MODEL", DEFAULT_MODELS.get(provider, ""))


def _parse_comments(text: str) -> list[ReviewComment]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []

    raw = json.loads(match.group())
    comments: list[ReviewComment] = []
    for item in raw:
        comment_text = (
            item.get("comment")
            or item.get("message")
            or item.get("description")
            or item.get("text")
            or ""
        )
        if not comment_text:
            continue
        comments.append(
            ReviewComment(
                file=item.get("file", "unknown"),
                line=item.get("line"),
                severity=item.get("severity", "suggestion"),
                comment=comment_text,
            )
        )
    return comments


def _call_openai(
    system: str, user: str, model: str, base_url: str | None = None, api_key: str | None = None
) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


BATCH_POLL_INTERVAL = 10
BATCH_MAX_WAIT = 600


def _call_anthropic(system: str, user: str, model: str) -> str:
    client = Anthropic()
    batch = client.messages.batches.create(
        requests=[
            {
                "custom_id": "review",
                "params": {
                    "model": model,
                    "max_tokens": 4096,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            }
        ]
    )

    elapsed = 0
    while elapsed < BATCH_MAX_WAIT:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        time.sleep(BATCH_POLL_INTERVAL)
        elapsed += BATCH_POLL_INTERVAL
    else:
        raise TimeoutError(f"Batch {batch.id} did not complete within {BATCH_MAX_WAIT}s")

    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            return result.result.message.content[0].text
        raise RuntimeError(f"Batch request failed: {result.result.type}")

    raise RuntimeError(f"Batch {batch.id} returned no results")


def review(
    diff: str,
    context: str | None = None,
    guidelines: str | None = None,
) -> list[ReviewComment]:
    provider = _get_provider()
    model = _get_model(provider)
    system = build_system_prompt(guidelines)
    user = build_user_prompt(diff, context)

    if provider == "anthropic":
        raw = _call_anthropic(system, user, model)
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("CODE_REVIEWER_BASE_URL")
        raw = _call_openai(system, user, model, base_url=base_url, api_key=api_key)
    else:  # local
        base_url = os.environ.get("CODE_REVIEWER_BASE_URL", DEFAULT_LOCAL_BASE_URL)
        raw = _call_openai(system, user, model, base_url=base_url, api_key="not-needed")

    return _parse_comments(raw)
