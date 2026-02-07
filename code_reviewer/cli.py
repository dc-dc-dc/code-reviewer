import argparse
import sys

from code_reviewer.llm import review
from code_reviewer.output import format_json, format_plain


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="code-reviewer",
        description="AI-powered code review from a git diff.",
    )
    parser.add_argument(
        "-c", "--context",
        help="Free-text description of the change (e.g. 'refactoring auth module').",
    )
    parser.add_argument(
        "-g", "--guidelines",
        help="Path to a file containing review guidelines/rules.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output review comments as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if sys.stdin.isatty():
        print("Error: No diff provided. Pipe a git diff into this command.", file=sys.stderr)
        print("  Example: git diff | code-reviewer", file=sys.stderr)
        sys.exit(1)

    diff = sys.stdin.read().strip()
    if not diff:
        print("Error: Empty diff.", file=sys.stderr)
        sys.exit(1)

    guidelines = None
    if args.guidelines:
        with open(args.guidelines) as f:
            guidelines = f.read()

    comments = review(diff, context=args.context, guidelines=guidelines)

    if args.json_output:
        print(format_json(comments))
    else:
        print(format_plain(comments))
