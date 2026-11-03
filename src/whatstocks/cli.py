"""whatstocks check | prepare | finish. The /setup and /morning skills run these."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .files import Problems
from .paths import UserDir


def _say(text: str) -> None:
    # Plain ASCII, so a Windows console in any code page can print it.
    print(text.encode("ascii", "replace").decode("ascii"))


def _check(user: UserDir) -> None:
    from .morning import load

    book, _ = load(user)
    open_views = sum(1 for v in book.views if not v.outcome)
    _say(f"OK: {len(book.holdings)} holdings, {open_views} open views, {len(book.decisions)} decisions, "
         f"{len(book.themes.themes)} themes.")
    untagged = [h.symbol for h in book.holdings if h.kind == "stock" and not book.themes.weights(h.symbol)]
    if untagged:
        _say(f"In no theme yet: {', '.join(untagged)}")


def _prepare(user: UserDir, offline: bool) -> None:
    from .morning import prepare

    result = prepare(user, offline=offline)
    for note in result["exposure"]["notes"] + result["news"].get("notes", []):
        _say(f"note: {note}")
    _say(f"Wrote {user.out / 'payload.json'} ({len(result['payload']['news'])} news items, "
         f"{len(result['payload']['views'])} open views).")
    _say("Next: write brief.json from payload.json, then run 'whatstocks finish'.")


def _finish(user: UserDir, no_brief: bool, allow_advice: bool) -> None:
    from .morning import finish

    path = finish(user, no_brief=no_brief, allow_advice=allow_advice)
    _say(f"Dashboard: {path.resolve()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whatstocks", description="A morning dashboard for your views and your exposure.")
    parser.add_argument("--dir", default="my", help="your folder (default: my)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="check your files and stop")
    prep = commands.add_parser("prepare", help="refresh data and write payload.json for the AI")
    prep.add_argument("--offline", action="store_true", help="use cached prices, holdings files and news only")
    fin = commands.add_parser("finish", help="check brief.json and build the dashboard")
    fin.add_argument("--no-brief", action="store_true", help="build the page without a brief")
    fin.add_argument("--allow-advice", action="store_true", help="let advice-like wording through, with a banner")
    args = parser.parse_args(argv)

    user = UserDir(Path(args.dir))
    if not user.path.is_dir():
        _say(f"No folder '{args.dir}'. Run /setup, or pass --dir demo to try the demo.")
        return 2
    try:
        if args.command == "check":
            _check(user)
        elif args.command == "prepare":
            _prepare(user, args.offline)
        else:
            _finish(user, args.no_brief, args.allow_advice)
    except Problems as e:
        _say("Fix these first:")
        for problem in e.problems:
            _say(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
