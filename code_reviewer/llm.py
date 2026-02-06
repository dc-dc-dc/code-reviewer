from __future__ import annotations

import json
import os
import re

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
        comments.append(
            ReviewComment(
                file=item["file"],
                line=item.get("line"),
                severity=item.get("severity", "suggestion"),
                comment=item["comment"],
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


def _call_anthropic(system: str, user: str, model: str) -> str:
    from anthropic import Anthropic

    client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


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
