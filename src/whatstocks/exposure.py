"""Exposure numbers (SPEC 7.2 to 7.4). All computed here in code; none by the AI."""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

from .files import Book, ThemeMap
from .funds import Piece, fund_keys

WEEKS = 104
MIN_WEEKS = 52
WORST_WEEKS = 10
TOP_NAMES = 15
SELL_OFFS = [
    ("Covid crash", "2020-02-19", "2020-03-23"),
    ("2022 rate shock", "2021-11-19", "2022-10-13"),
    ("Oct 2026 AI sell-off", "2026-10-06", "2026-10-23"),
]


def _num(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def member_index(themes: ThemeMap) -> dict:
    """Every way a theme member can appear (its symbol, its aliases, their fund keys) -> the member."""
    index = {}
    for theme in themes.themes.values():
        for member in theme.core + theme.partial:
            for line in themes.lines(member):
                index[line] = member
                for key in fund_keys(line):
                    index[key] = member
    return index


def theme_shares(pieces: list[Piece], themes: ThemeMap, index: dict | None = None) -> dict[str, dict]:
    """Share of value in each theme (core counts 1.0, partial 0.5), with the names counted."""
    index = index if index is not None else member_index(themes)
    total = sum(p.value for p in pieces) or 1.0
    shares = {tid: 0.0 for tid in themes.themes}
    names = {tid: defaultdict(float) for tid in themes.themes}
    for p in pieces:
        member = index.get(p.line)
        if member is None:
            continue
        for tid, w in themes.weights(member).items():
            shares[tid] += p.value * w / total
            names[tid][member] += p.value / total
    return {
        tid: {"share": shares[tid], "names": sorted(([m, v] for m, v in names[tid].items()), key=lambda x: -x[1])}
        for tid in themes.themes
    }


def split(pieces: list[Piece], attr: str, top: int = 8) -> list[list]:
    total = sum(p.value for p in pieces) or 1.0
    sums = defaultdict(float)
    for p in pieces:
        sums[getattr(p, attr) or "Unknown"] += p.value / total
    ranked = sorted(sums.items(), key=lambda kv: -kv[1])
    rest = sum(v for _, v in ranked[top:])
    return [[k, v] for k, v in ranked[:top]] + ([["Other", rest]] if rest > 0 else [])


def weekly(series: pd.Series) -> pd.Series:
    s = series.dropna().copy()
    s.index = pd.DatetimeIndex(s.index)
    return s.resample("W-FRI").last().pct_change().dropna()


def portfolio_weekly(weights: dict[str, float], series: dict[str, pd.Series], cash: set[str]) -> tuple[pd.Series, float]:
    """Weekly returns of today's holdings at today's weights, replayed backward, and the share covered.

    Holdings with under MIN_WEEKS of history are left out. Cash counts as a zero return."""
    rets = {}
    for symbol in weights:
        if symbol in cash or symbol not in series or series[symbol].empty:
            continue
        r = weekly(series[symbol]).iloc[-WEEKS:]
        if len(r) >= MIN_WEEKS:
            rets[symbol] = r
    covered = sum(weights[s] for s in rets) + sum(w for s, w in weights.items() if s in cash)
    if not rets or not covered:
        return pd.Series(dtype=float), covered
    frame = pd.DataFrame(rets).iloc[-WEEKS:].fillna(0.0)
    return sum(frame[s] * weights[s] for s in rets) / covered, covered


def beta(y: pd.Series, x: pd.Series) -> float | None:
    both = pd.concat([y, x], axis=1, join="inner").dropna().iloc[-WEEKS:]
    if len(both) < MIN_WEEKS:
        return None
    var = both.iloc[:, 1].var()
    return _num(both.iloc[:, 0].cov(both.iloc[:, 1]) / var) if var else None


def worst_weeks(proxy: pd.Series, port: pd.Series, bench: pd.Series) -> dict | None:
    """Mean returns in the proxy's WORST_WEEKS worst weeks of the last WEEKS."""
    p = proxy.iloc[-WEEKS:]
    if len(p) < MIN_WEEKS:
        return None
    worst = p.nsmallest(WORST_WEEKS).index
    return {
        "proxy": _num(p[worst].mean()),
        "you": _num(port.reindex(worst).mean()) if len(port) else None,
        "world": _num(bench.reindex(worst).mean()) if len(bench) else None,
    }


def window_return(series: pd.Series, start: str, end: str) -> float | None:
    s = series.dropna()
    if s.empty:
        return None
    s.index = pd.DatetimeIndex(s.index)
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    if s.index[0] > t0 or s.index[-1] < t1:
        return None
    return float(s[s.index <= t1].iloc[-1] / s[s.index <= t0].iloc[-1] - 1)


def sell_offs(weights: dict[str, float], series: dict[str, pd.Series], cash: set[str], bench: pd.Series) -> list[dict]:
    """Today's holdings replayed over named past sell-offs, with the share of value that had prices then."""
    out = []
    for name, start, end in SELL_OFFS:
        total, covered = 0.0, 0.0
        for symbol, w in weights.items():
            r = 0.0 if symbol in cash else window_return(series.get(symbol, pd.Series(dtype=float)), start, end)
            if r is not None:
                total += w * r
                covered += w
        out.append({
            "name": name, "start": start, "end": end,
            "you": total / covered if covered else None,
            "world": window_return(bench, start, end),
            "coverage": covered,
        })
    return out


def build(book: Book, weights: dict[str, float], series: dict[str, pd.Series], pieces: list[Piece], bench_pieces: list[Piece]) -> dict:
    themes = book.themes
    index = member_index(themes)
    you, world = theme_shares(pieces, themes, index), theme_shares(bench_pieces, themes, index)
    cash = {h.symbol for h in book.holdings if h.kind == "cash"}
    port, coverage = portfolio_weekly(weights, series, cash)
    bench_series = series.get(book.settings.benchmark, pd.Series(dtype=float))
    bench = weekly(bench_series) if len(bench_series) else pd.Series(dtype=float)
    rows = {}
    for tid, theme in themes.themes.items():
        proxy_series = series.get(theme.proxy, pd.Series(dtype=float))
        proxy = weekly(proxy_series) if len(proxy_series) else pd.Series(dtype=float)
        rows[tid] = {
            "label": theme.label,
            "proxy": theme.proxy,
            "you": you[tid]["share"],
            "world": world[tid]["share"],
            "names_you": you[tid]["names"][:TOP_NAMES],
            "names_world": world[tid]["names"][:TOP_NAMES],
            "beta_you": beta(port, proxy) if len(port) else None,
            "beta_world": beta(bench, proxy) if len(bench) else None,
            "worst_weeks": worst_weeks(proxy, port, bench),
        }
    return {
        "weights": weights,
        "themes": rows,
        "beta_coverage": coverage,
        "sell_offs": sell_offs(weights, series, cash, bench_series),
        "regions": {"you": split(pieces, "country"), "world": split(bench_pieces, "country")},
        "currencies": {"you": split(pieces, "currency")},
        "unresolved": sum(p.value for p in pieces if p.kind == "unresolved") / (sum(p.value for p in pieces) or 1.0),
    }
