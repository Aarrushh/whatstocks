"""Where things live. Shipped files sit at the repo root; each user's files sit in one folder (my/ by default)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEMES_FILE = ROOT / "themes" / "themes.yaml"
FUNDS_FILE = ROOT / "sources" / "funds.yaml"
FEEDS_FILE = ROOT / "sources" / "feeds.yaml"
BET_DIR = ROOT / "sources" / "bet"  # the shipped ledger of "Will the bet pay off?"


@dataclass(frozen=True)
class UserDir:
    path: Path

    @property
    def settings(self) -> Path:
        return self.path / "settings.yaml"

    @property
    def holdings(self) -> Path:
        return self.path / "holdings.csv"

    @property
    def views(self) -> Path:
        return self.path / "views.yaml"

    @property
    def decisions(self) -> Path:
        return self.path / "decisions.yaml"

    @property
    def themes(self) -> Path:
        return self.path / "themes.yaml"

    @property
    def bet(self) -> Path:
        return self.path / "bet.yaml"

    @property
    def cache(self) -> Path:
        return self.path / "cache"

    @property
    def out(self) -> Path:
        return self.path / "out"
