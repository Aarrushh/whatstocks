"""Price moves for the dashboard: each holding, the portfolio and the world index. Computed in code only (P2).

Every series is in the home currency. The portfolio line replays today's holdings at today's weights, so it
shows how the current mix would have moved, not the user's actual past returns."""
from __future__ import annotations

import datetime as dt

import pandas as pd

PERIODS = (("1D", 1), ("1W", 7), ("1M", 30), ("3M", 91), ("YTD", 0), ("1Y", 365))
LINE_DAYS = 365
SPARK_DAYS = 90
HEAT_WEEKS = 12


def _clean(series: pd.Series, today: dt.date | None = None) -> pd.Series:
    s = series.dropna().astype(float)
    s.index = pd.DatetimeIndex(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s[s.index <= pd.Timestamp(today)] if today else s


def _returns(s: pd.Series | pd.DataFrame):
    """Simple returns without pandas' fill rules (they changed between versions)."""
    return (s / s.shift(1) - 1).iloc[1:]


def change(series: pd.Series, today: dt.date, period: str) -> float | None:
    """The move over a period, up to the last close on or before today."""
    s = _clean(series, today)
    if len(s) < 2:
        return None
    if period == "1D":
        base = s.iloc[-2]
    else:
        if period == "YTD":
            cut = pd.Timestamp(today.year, 1, 1) - pd.Timedelta(days=1)
        else:
            cut = s.index[-1] - pd.Timedelta(days=dict(PERIODS)[period])
        before = s[s.index <= cut]
        if before.empty:
            return None
        base = before.iloc[-1]
    return float(s.iloc[-1] / base - 1) if base else None


def changes(series: pd.Series, today: dt.date) -> dict[str, float | None]:
    return {name: change(series, today, name) for name, _ in PERIODS}


def daily_returns(weights: dict[str, float], series: dict[str, pd.Series], cash: set[str], today: dt.date) -> tuple[pd.Series, float]:
    """Daily returns of today's holdings at today's weights, and the share of the portfolio they cover.

    Prices are carried forward over each market's holidays. Cash, and days before a holding has prices,
    count as a zero return."""
    prices = {s: _clean(series[s], today) for s in weights if s not in cash and s in series and len(series[s])}
    prices = {s: p for s, p in prices.items() if len(p)}
    covered = sum(weights[s] for s in prices) + sum(w for s, w in weights.items() if s in cash)
    if not prices or not covered:
        return pd.Series(dtype=float), covered
    frame = pd.DataFrame(prices).sort_index().ffill()
    rets = _returns(frame).fillna(0.0)
    return (rets * pd.Series({s: weights[s] for s in prices})).sum(axis=1) / covered, covered


def index_line(returns: pd.Series, today: dt.date, days: int = LINE_DAYS) -> list[list]:
    """Returns compounded into an index that starts at 100, as [[date, value], ...].

    The window is cut the way `change` cuts a period (from the last close, not from today), so the line ends
    where the period figure says even on a morning before today's close exists."""
    r = returns[returns.index <= pd.Timestamp(today)]
    if r.empty:
        return []
    start = pd.Series([1.0], index=pd.DatetimeIndex([r.index[0] - pd.Timedelta(days=1)]))
    return rebased(pd.concat([start, (1 + r).cumprod()]), today, days)


def rebased(series: pd.Series, today: dt.date, days: int, weekly: bool = False) -> list[list]:
    """A price series over the last `days`, rebased to 100.

    It starts from the last close on or before the window opens, the same base `change` uses, so a line ends
    where its period figure says. A weekly line keeps each week's last close on its real date (never a Friday
    still to come) and ends on the latest close."""
    s = _clean(series, today)
    if len(s) < 2:
        return []
    before = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    s = s[s.index >= (before.index[-1] if len(before) else s.index[0])]
    if weekly:
        s = pd.concat([s.iloc[:1], s.groupby(s.index.to_period("W-FRI")).tail(1)])
        s = s[~s.index.duplicated()]
    if len(s) < 2 or not s.iloc[0]:
        return []
    return [[d.date().isoformat(), round(float(v / s.iloc[0] * 100), 3)] for d, v in s.items()]


def theme_weeks(proxy: pd.Series, world: pd.Series, today: dt.date, weeks: int = HEAT_WEEKS) -> list[list]:
    """The theme proxy's weekly return minus the world index's, for the last `weeks` weeks: [[week end, gap], ...]."""
    def weekly(s):
        return _returns(_clean(s, today).resample("W-FRI").last().dropna())

    both = pd.concat([weekly(proxy), weekly(world)], axis=1, join="inner").dropna().iloc[-weeks:]
    return [[d.date().isoformat(), round(float(a - b), 5)] for d, (a, b) in both.iterrows()]


def _gaps(you: dict, avg: dict) -> dict[str, float | None]:
    return {p: (you[p] - avg[p]) if you.get(p) is not None and avg.get(p) is not None else None for p, _ in PERIODS}


def compare(book, series: dict[str, pd.Series], today: dt.date) -> list[dict]:
    """Each extra index from settings (for example the Nasdaq-100): its period moves and its line."""
    out = []
    for name, symbol in (getattr(book.settings, "compare", None) or {}).items():
        s = _clean(series.get(symbol, pd.Series(dtype=float)), today)
        out.append({"name": name, "symbol": symbol,
                    "returns": changes(s, today) if len(s) > 1 else {},
                    "line": index_line(_returns(s), today) if len(s) > 1 else []})
    return out


def sector_rows(weights: dict[str, float], series: dict[str, pd.Series], sectors: dict[str, str],
                today: dt.date) -> list[dict]:
    """Your stocks grouped by sector: how your stocks in that sector moved, at today's weights inside the sector,
    against the sector fund (the sector average). Largest sector first."""
    from .sectors import SECTORS

    groups: dict[str, dict[str, float]] = {}
    for symbol, sector in sectors.items():
        if symbol in weights and symbol in series and len(series[symbol]):
            groups.setdefault(sector, {})[symbol] = weights[symbol]
    rows = []
    for sector, members in groups.items():
        label, fund = SECTORS.get(sector, (sector, None))
        rets, _ = daily_returns(members, series, set(), today)
        # A level series that starts at 1 the day before the first return, so the first day's move counts too.
        level = pd.concat([pd.Series([1.0], index=[rets.index[0] - pd.Timedelta(days=1)]), (1 + rets).cumprod()]) \
            if len(rets) else pd.Series(dtype=float)
        you = changes(level, today) if len(level) > 1 else {}
        proxy = _clean(series.get(fund, pd.Series(dtype=float)), today) if fund else pd.Series(dtype=float)
        avg = changes(proxy, today) if len(proxy) > 1 else {}
        rows.append({
            "id": sector, "label": label, "fund": fund if len(proxy) > 1 else None,
            "weight": sum(members.values()),
            "holdings": sorted(members, key=lambda s: -members[s]),
            "you": you, "average": avg, "gap": _gaps(you, avg),
            "lines": {"you": index_line(rets, today) if len(rets) else [],
                      "average": index_line(_returns(proxy), today) if len(proxy) > 1 else []},
        })
    return sorted(rows, key=lambda r: -r["weight"])


def build(book, weights: dict[str, float], series: dict[str, pd.Series], today: dt.date,
          sectors: dict[str, str] | None = None) -> dict:
    """Everything the dashboard draws from prices."""
    cash = {h.symbol for h in book.holdings if h.kind == "cash"}
    empty = pd.Series(dtype=float)
    bench = _clean(series.get(book.settings.benchmark, empty), today)
    port, covered = daily_returns(weights, series, cash, today)
    world = _returns(bench) if len(bench) > 1 else empty
    stocks = {h.symbol for h in book.holdings if h.kind == "stock"}
    held = [s for s in weights if s not in cash and s in series and len(series[s])]
    proxies = sorted({t.proxy for t in book.themes.themes.values()} & set(series))
    return {
        "returns": {
            "holdings": {s: changes(series[s], today) for s in held},
            "portfolio": changes((1 + port).cumprod(), today) if len(port) else {},
            "world": changes(bench, today) if len(bench) else {},
        },
        "coverage": covered,
        "lines": {"portfolio": index_line(port, today), "world": index_line(world, today)},
        "holding_lines": {s: rebased(series[s], today, LINE_DAYS, weekly=True) for s in held},
        "world_weekly": rebased(bench, today, LINE_DAYS, weekly=True) if len(bench) > 1 else [],
        "spark": {s: [v for _, v in rebased(series[s], today, SPARK_DAYS)] for s in held},
        "proxies": {p: changes(series[p], today) for p in proxies},
        "theme_weeks": {
            tid: theme_weeks(series[t.proxy], bench, today)
            for tid, t in book.themes.themes.items() if t.proxy in series and len(bench) > 1
        },
        "compare": compare(book, series, today),
        "sectors": sector_rows(weights, series, {s: v for s, v in (sectors or {}).items() if s in stocks}, today),
    }
