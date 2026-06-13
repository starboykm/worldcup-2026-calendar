from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .team_names import display_team_name


@dataclass
class Goal:
    team: str
    player: str
    minute: str
    note: str = ""
    player_zh: str = ""


@dataclass
class Match:
    match_id: str
    stage: str
    home: str
    away: str
    starts_at_beijing: datetime
    venue: str = ""
    city: str = ""
    source_url: str = ""
    status: str = "scheduled"
    home_score: int | None = None
    away_score: int | None = None
    goals: list[Goal] = field(default_factory=list)
    raw_title: str = ""

    @property
    def title(self) -> str:
        home = display_team_name(self.home)
        away = display_team_name(self.away)
        if self.home_score is not None and self.away_score is not None:
            return f"{home} {self.home_score}-{self.away_score} {away}"
        return f"{home} vs {away}"

    @property
    def location(self) -> str:
        return ", ".join(part for part in [self.venue, self.city] if part)
