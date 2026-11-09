"""Your reach to each crash path of "Will the bet pay off?" (spec section 10), next to the world index's.

A path's channels (signals.yaml, or yours in my/bet.yaml) reach the look-through rows the way a conflict scan's
channels do (scan.reach): each row counts once, at the strength of the strongest channel of each effect that reaches
it. The past episodes in signals.yaml are replayed on today's portfolio and on the world index (exposure.replay).
Shares and returns only, never amounts."""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .. import scan
from ..exposure import replay
from ..files import ThemeMap
from .ledger import Ledger

SIDES = ("you", "world")


def channel_label(channel: dict, themes: ThemeMap) -> str:
    """The theme's label; 'AI build-out, core members' for ai_buildout:core."""
    tid, _, tier = channel["id"].partition(":")
    theme = themes.themes.get(tid)
    label = theme.label if theme else tid
    return f"{label}, {tier} members" if tier else label


def crash_paths(led: Ledger, themes: ThemeMap, look: dict[str, list], weights: dict[str, float],
                series: dict[str, pd.Series], cash: set[str], benchmark: str) -> dict:
    """For each path: each channel's share of your portfolio and of the world index; the share each effect (hurt,
    help, mixed) reaches in all, and that share weighted by strength; the holdings it reaches; and its past episodes
    replayed on both.

    look holds each side's look-through rows: [holding, share of the whole, theme member or None, country]."""
    windows = led.signals.get("replays") or []
    bench = series.get(benchmark, pd.Series(dtype=float))
    replayed = replay(weights, series, cash, bench, [(w["label"], str(w["start"]), str(w["end"])) for w in windows])
    replays = {w["id"]: {"id": w["id"], **r} for w, r in zip(windows, replayed)}
    out = {}
    for pid, path in led.signals["paths"].items():
        channels = led.signals["channels"].get(pid) or []
        reached = {side: [(origin, share, scan.reach(member, country, channels, themes))
                          for origin, share, member, country in look[side]] for side in SIDES}
        by_holding = defaultdict(list)
        for origin, share, r in reached["you"]:
            by_holding[origin].append((share, r))
        holdings = []
        for symbol, rows in by_holding.items():
            # Measured against the part of the holding that could be looked through, as a scan does.
            covered = sum(share for share, _ in rows)
            tally = scan._tally(rows)
            if covered and any(tally.values()):
                holdings.append({"symbol": symbol, "weight": round(weights.get(symbol, covered), 6),
                                 **{k: round(v / covered, 6) for k, v in tally.items()}})
        out[pid] = {
            "id": pid, "label": path["label"], "kind": path["kind"],
            "channels": [{**c, "label": channel_label(c, themes),
                          **{side: round(sum(share * scan._membership(member, country, c, themes)
                                             for _, share, member, country in look[side]), 6) for side in SIDES}}
                         for c in channels],
            **{side: {k: round(v, 6) for k, v in scan._tally([(share, r) for _, share, r in reached[side]]).items()}
               for side in SIDES},
            "holdings": sorted(holdings, key=lambda h: -h["weight"]),
            "replays": [replays[w["id"]] for w in windows if pid in (w.get("paths") or [])],
        }
    return out
