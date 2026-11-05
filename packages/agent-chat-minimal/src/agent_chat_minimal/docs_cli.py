"""Offline documentation CLI; JSON stdout is suitable for coding agents."""

import argparse
import json
import sys

from . import docs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Browse and search the installed library guides (offline)")
    parser.add_argument("--json", action="store_true", help="Emit versioned JSON on stdout, including errors")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("list", help="List guides with summaries")
    show = commands.add_parser("show", help="Read a guide as Markdown")
    show.add_argument("guide")
    search = commands.add_parser("search", help="Case-insensitive literal line search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    for command in commands.choices.values():
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    command = args.command or "show"
    try:
        if command == "list":
            result = {"guides": docs.catalog()}
            text = "\n".join(f"{entry['name']}: {entry['summary']}" for entry in result["guides"])
        elif command == "search":
            result = {"query": args.query, "matches": docs.search(args.query, limit=args.limit)}
            text = "\n".join(f"{match['guide']}:{match['line']}: {match['excerpt']}" for match in result["matches"])
            text = text or "No matches."
        else:
            guide = getattr(args, "guide", "agent-onboarding")
            text = docs.get(guide)
            result = {"guide": guide.removesuffix(".md").lower(), "markdown": text}
    except (KeyError, ValueError) as exc:
        if args.json:
            print(json.dumps({"contract_version": 1, "ok": False, "error": str(exc)}))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"contract_version": 1, "ok": True, **result}, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
