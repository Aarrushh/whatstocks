"""whatstocks check | prepare | finish | scan | bet. The /setup, /morning, /scan and /bet skills run these."""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

from .files import Problems
from .paths import UserDir

# Typographic characters the ledger's words use, as plain ASCII.
_PLAIN = str.maketrans({"−": "-", "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"',
                        "”": '"', "…": "...", "÷": "/", "×": "x", "→": "->", "≥": ">=",
                        "≤": "<=", "≈": "~", " ": " ", " ": " "})


def _say(text: str) -> None:
    # Plain ASCII, so a Windows console in any code page can print it: dashes and quotes made plain, accents dropped,
    # and anything else as '?'.
    plain = unicodedata.normalize("NFKD", text.translate(_PLAIN))
    print("".join(c for c in plain if not unicodedata.combining(c)).encode("ascii", "replace").decode("ascii"))


def _check(user: UserDir) -> None:
    from .bet import fetch as bet_fetch
    from .bet import ledger as bet_ledger
    from .morning import load

    book, _ = load(user)
    ledger = bet_ledger.load(user, views={v.id for v in book.views}, themes=book.themes)  # check it all first
    open_views = sum(1 for v in book.views if not v.outcome)
    _say(f"OK: {len(book.holdings)} holdings, {open_views} open views, {len(book.decisions)} decisions, "
         f"{len(book.themes.themes)} themes.")
    untagged = [h.symbol for h in book.holdings if h.kind == "stock" and not book.themes.weights(h.symbol)]
    if untagged:
        _say(f"In no theme yet: {', '.join(untagged)}")
    _say(ledger.summary())
    fetched = bet_fetch.points(user, ledger)
    if fetched:
        gaps = bet_fetch.merge(ledger, fetched)
        _say(f"Fetched: {len(fetched)} figures in the cache. Each takes the place of the ledger's figure for the same "
             f"period; yours stay.")
        if gaps:
            _say(f"Fetched figures more than {bet_fetch.DIFFERENCE:.0%} from the ledger's or yours ({len(gaps)}):")
            for gap in gaps:
                _say(f"  - {gap}")


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


def _scan_prepare(user: UserDir, conflict: str, offline: bool) -> None:
    from .scan import prepare

    result = prepare(user, conflict, offline=offline)
    for note in result["notes"]:
        _say(f"note: {note}")
    payload = result["payload"]
    _say(f"Wrote {result['path']} ({len(payload['news'])} news items, {len(payload['regions'])} regions).")
    _say(f"Next: write {result['path'].with_name(result['slug'] + '.json')} from it, "
         f"then run 'whatstocks scan finish {result['slug']}'.")


def _scan_finish(user: UserDir, slug: str, allow_advice: bool) -> None:
    from .scan import finish

    result = finish(user, slug, allow_advice=allow_advice)
    you, world = result["result"]["totals"]["you"], result["result"]["totals"]["world"]
    _say(f"Scan '{slug}': channels it would hurt reach {you['hurt_share']:.1%} of your portfolio "
         f"(world index {world['hurt_share']:.1%}); channels it would help reach {you['help_share']:.1%} "
         f"(world index {world['help_share']:.1%}).")
    _say(f"Dashboard (Scenarios page): {result['page'].resolve()}")


def _bet(user: UserDir) -> None:
    from .bet.signals import moves
    from .morning import rebuild_bet

    result = rebuild_bet(user)
    _say("Worked out again from the ledger, your bet.yaml and the cached prices and figures (nothing fetched), "
         "at your default settings.")
    for line in moves(result["before"], result["after"]):
        _say(line)
    _say(f"Dashboard (The bet page): {result['page'].resolve()}")


def _and(words: list[str]) -> str:
    return " and ".join(words) if len(words) < 3 else ", ".join(words[:-1]) + " and " + words[-1]


def _feeds(f: dict) -> str:
    n = len(f["indicators"])
    parts = (["the two curves"] if f["curves"] else []) + ([f"{n} indicator{'s' if n != 1 else ''}"] if n else []) + (
        [f"the {_and(f['panels'])}"] if f["panels"] else [])
    return "feeds " + ", ".join(parts) if parts else "feeds nothing on the page yet"


def _bet_due(user: UserDir) -> None:
    from .morning import bet_due

    found = bet_due(user)
    due, gaps = found["due"], found["gaps"]
    fetches = {"FRED": "'whatstocks prepare' fetches it from FRED: wait for FRED to publish it",
               "Yahoo": "'whatstocks prepare' fetches it from Yahoo",
               "EDGAR": "'whatstocks prepare' fetches it from EDGAR" if found["sec_contact"] else
                        "EDGAR could fetch it once sec_contact is set in settings.yaml; meanwhile it comes from you"}
    _say(f"Due: {len(due)} of {found['series']} series have a newer figure due, what moves the curves first.")
    for n, row in enumerate(due, 1):
        _say(f"{n:>3}. {row['label']} [{row['id']}], {row['cadence']}; {_feeds(row['feeds'])}")
        for d in row["due"]:
            _say(f"       {d['label']}: newest {d['period']}; the next was expected by {d['expected']}")
        if row["fetcher"]:
            _say(f"       ({fetches[row['fetcher']]})")
    _say(f"Open gaps in the ledger: {len(gaps)}, in the same order.")
    for n, g in enumerate(gaps, 1):
        where = ", ".join(str(x) for x in (g["label"] or g["series"], g["name"]) if x)
        _say(f"{n:>3}. {where + ': ' if where else ''}{g['what']}")
    _say("Add figures with /bet in Claude Code, or in bet.yaml in your folder; then run 'whatstocks check' and "
         "'whatstocks bet'.")


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
    scan = commands.add_parser("scan", help="map where a conflict would reach your portfolio")
    scan_commands = scan.add_subparsers(dest="scan_command", required=True)
    scan_prep = scan_commands.add_parser("prepare", help="search the news for a conflict and write the scan payload")
    scan_prep.add_argument("conflict", help='the conflict in a few words, for example "China blockade of Taiwan"')
    scan_prep.add_argument("--offline", action="store_true", help="reuse the news an earlier scan prepare saved")
    scan_fin = scan_commands.add_parser("finish", help="check the scan file, compute the scan and rebuild the page")
    scan_fin.add_argument("slug", help="the scan name that 'scan prepare' printed")
    scan_fin.add_argument("--allow-advice", action="store_true", help="let advice-like wording through, with a banner")
    bet = commands.add_parser("bet", help="work 'Will the bet pay off?' out again from your bet.yaml and rebuild the "
                                          "page (nothing is fetched)")
    bet_commands = bet.add_subparsers(dest="bet_command")
    bet_commands.add_parser("due", help="list the ledger's figures that are due, and its open gaps, for /bet")
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
        elif args.command == "finish":
            _finish(user, args.no_brief, args.allow_advice)
        elif args.command == "bet":
            if args.bet_command == "due":
                _bet_due(user)
            else:
                _bet(user)
        elif args.scan_command == "prepare":
            _scan_prepare(user, args.conflict, args.offline)
        else:
            _scan_finish(user, args.slug, args.allow_advice)
    except Problems as e:
        _say("Fix these first:")
        for problem in e.problems:
            _say(f"  - {problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
