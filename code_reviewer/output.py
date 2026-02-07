from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass
class ReviewComment:
    file: str
    line: int | None
    severity: str  # error, warning, suggestion
    comment: str


SEVERITY_SYMBOLS = {
    "error": "\u2718",
    "warning": "\u26a0",
    "suggestion": "\u25cb",
}


def format_plain(comments: list[ReviewComment]) -> str:
    if not comments:
        return "No issues found."

    lines: list[str] = []
    for c in comments:
        symbol = SEVERITY_SYMBOLS.get(c.severity, "?")
        location = c.file
        if c.line is not None:
            location += f":{c.line}"
        lines.append(f"  {symbol} [{c.severity}] {location}")
        lines.append(f"    {c.comment}")
        lines.append("")

    return "\n".join(lines).rstrip("\n")


def format_json(comments: list[ReviewComment]) -> str:
    return json.dumps([asdict(c) for c in comments], indent=2)
