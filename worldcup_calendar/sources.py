from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import Goal, Match

WIKIPEDIA_BASE = "https://en.wikipedia.org/wiki"
DEFAULT_PAGES = [
    "2026_FIFA_World_Cup",
    *(f"2026_FIFA_World_Cup_Group_{letter}" for letter in "ABCDEFGHIJKL"),
    "2026_FIFA_World_Cup_knockout_stage",
]

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

TZ_OFFSETS = {
    "PDT": -7,
    "MDT": -6,
    "CDT": -5,
    "EDT": -4,
    "PST": -8,
    "MST": -7,
    "CST": -6,
    "EST": -5,
}

DATE_PATTERNS = [
    re.compile(r"\b(?P<day>\d{1,2}) (?P<month>[A-Z][a-z]+) (?P<year>2026)\b"),
    re.compile(r"\b(?P<month>[A-Z][a-z]+) (?P<day>\d{1,2}), (?P<year>2026)\b"),
]
TIME_RE = re.compile(
    r"\b(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>a\.m\.|p\.m\.|am|pm)?"
    r"(?:\s*(?P<abbr>PDT|MDT|CDT|EDT|PST|MST|CST|EST))?"
    r"(?:.*?UTC(?P<utc_sign>[+\-−])(?P<utc_hour>\d{1,2}))?",
    re.IGNORECASE,
)
SCORE_RE = re.compile(r"\b(?P<home>\d{1,2})\s*[–-]\s*(?P<away>\d{1,2})\b")
MATCH_ID_RE = re.compile(r"\bMatch\s+(?P<number>\d{1,3})\b", re.IGNORECASE)
TITLE_SPLIT_RE = re.compile(r"\s+(?:v|vs\.?|versus)\s+", re.IGNORECASE)
GOAL_RE = re.compile(r"(?P<player>[A-Z][^;\n\[]+?)\s+(?P<minute>\d{1,3}(?:\+\d{1,2})?'(?:\s*\([^)]*\))?)")
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)


class SourceError(RuntimeError):
    pass


def fetch_matches(source_url: str | None = None, overrides_path: Path | None = None) -> list[Match]:
    if source_url:
        matches = _fetch_single_source(source_url)
    else:
        matches = []
        errors = []
        for page in DEFAULT_PAGES:
            url = f"{WIKIPEDIA_BASE}/{quote(page)}"
            try:
                matches.extend(_fetch_wikipedia_page(url))
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        if not matches and errors:
            raise SourceError("; ".join(errors))

    matches = _dedupe(matches)
    if overrides_path:
        _apply_overrides(matches, overrides_path)
    matches.sort(key=lambda item: (item.starts_at_beijing, item.match_id))
    if not matches:
        raise SourceError("No matches were parsed from the configured source.")
    return matches


def _fetch_single_source(source_url: str) -> list[Match]:
    source_path = Path(source_url)
    if source_path.exists():
        body = source_path.read_text(encoding="utf-8")
        if source_path.suffix.lower() == ".json":
            return _parse_json_matches(json.loads(body), source_url)
        return _parse_wikipedia_html(body, source_url)

    body, content_type = _download(source_url)
    if "json" in content_type or source_url.lower().endswith(".json"):
        return _parse_json_matches(json.loads(body), source_url)
    return _parse_wikipedia_html(body, source_url)


def _fetch_wikipedia_page(url: str) -> list[Match]:
    body, _ = _download(url)
    return _parse_wikipedia_html(body, url)


def _download(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "worldcup-2026-calendar/0.1"})
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace"), response.headers.get("content-type", "")


def _parse_wikipedia_html(html: str, source_url: str) -> list[Match]:
    clean_html = SCRIPT_STYLE_RE.sub("", html)
    boxes = _candidate_boxes(clean_html)
    matches: list[Match] = []
    for index, box in enumerate(boxes, start=1):
        match = _parse_match_box(clean_html, box, source_url, index)
        if match:
            matches.append(match)
    return matches


def _candidate_boxes(html: str) -> list[tuple[int, str]]:
    boxes: list[tuple[int, str]] = []
    patterns = [
        re.compile(r"<table\b(?=[^>]*class=[\"'][^\"']*(?:footballbox|vevent)[^\"']*[\"'])[\s\S]*?</table>", re.IGNORECASE),
        re.compile(r"<div\b(?=[^>]*class=[\"'][^\"']*(?:footballbox|vevent)[^\"']*[\"'])[\s\S]*?</div>", re.IGNORECASE),
    ]
    seen: set[tuple[int, int]] = set()
    for pattern in patterns:
        for match in pattern.finditer(html):
            key = (match.start(), match.end())
            if key in seen:
                continue
            text = _html_text(match.group(0))
            if "2026" not in text or not _parse_datetime_from_text(text):
                continue
            if not (_summary_text(match.group(0)) or TITLE_SPLIT_RE.search(text)):
                continue
            seen.add(key)
            boxes.append((match.start(), match.group(0)))
    boxes.sort(key=lambda item: item[0])
    return boxes


def _parse_match_box(full_html: str, box_item: tuple[int, str], source_url: str, fallback_index: int) -> Match | None:
    start_index, box = box_item
    text = _html_text(box)
    title = _summary_text(box) or _title_from_text(text)
    if not title:
        return None

    starts_at = _structured_datetime(box) or _parse_datetime_from_text(text)
    if not starts_at:
        return None

    home, away = _split_title(title)
    if not home or not away:
        return None

    match_id = _match_id(text, fallback_index, home, away, starts_at)
    stage = _stage_name(full_html[:start_index])
    venue, city = _venue(box, text)
    home_score, away_score = _score(text)
    status = "completed" if home_score is not None and away_score is not None else "scheduled"

    return Match(
        match_id=match_id,
        stage=stage,
        home=home,
        away=away,
        starts_at_beijing=starts_at,
        venue=venue,
        city=city,
        source_url=source_url,
        status=status,
        home_score=home_score,
        away_score=away_score,
        goals=_goals(text, home, away),
        raw_title=title,
    )


def _parse_json_matches(payload: Any, source_url: str) -> list[Match]:
    if isinstance(payload, dict):
        rows = payload.get("matches") or payload.get("data") or payload.get("fixtures") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        raise SourceError("JSON source must be a list or contain matches/data/fixtures.")

    matches: list[Match] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        home = _nested(row, "home", "name") or row.get("home_team") or row.get("home") or row.get("team1")
        away = _nested(row, "away", "name") or row.get("away_team") or row.get("away") or row.get("team2")
        start_raw = row.get("datetime") or row.get("date") or row.get("kickoff") or row.get("start_time")
        starts_at = _parse_json_datetime(str(start_raw)) if start_raw else None
        if not home or not away or not starts_at:
            continue
        home_score = _as_int(_first_present(row.get("home_score"), _nested(row, "home", "score")))
        away_score = _as_int(_first_present(row.get("away_score"), _nested(row, "away", "score")))
        matches.append(
            Match(
                match_id=str(row.get("match_id") or row.get("id") or f"M{index:03d}"),
                stage=str(row.get("stage") or row.get("round") or ""),
                home=str(home),
                away=str(away),
                starts_at_beijing=starts_at,
                venue=str(row.get("venue") or ""),
                city=str(row.get("city") or ""),
                source_url=source_url,
                status=str(row.get("status") or ("completed" if home_score is not None else "scheduled")),
                home_score=home_score,
                away_score=away_score,
                goals=[
                    Goal(
                        team=str(goal.get("team") or ""),
                        player=str(goal.get("player") or ""),
                        minute=str(goal.get("minute") or ""),
                        note=str(goal.get("note") or ""),
                    )
                    for goal in row.get("goals", [])
                    if isinstance(goal, dict)
                ],
            )
        )
    return matches


def _summary_text(html: str) -> str:
    for pattern in [
        r"<[^>]+class=[\"'][^\"']*summary[^\"']*[\"'][^>]*>(?P<value>[\s\S]*?)</[^>]+>",
        r"<(?:th|caption)\b[^>]*>(?P<value>[\s\S]*?)</(?:th|caption)>",
    ]:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            value = _clean_text(_html_text(match.group("value")))
            if TITLE_SPLIT_RE.search(value):
                return value
    return ""


def _title_from_text(text: str) -> str:
    for line in text.splitlines():
        line = _clean_text(line)
        if TITLE_SPLIT_RE.search(line) and "2026" not in line and len(line) < 90:
            return line
    return ""


def _split_title(title: str) -> tuple[str, str]:
    parts = TITLE_SPLIT_RE.split(title, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    return _strip_team(parts[0]), _strip_team(parts[1])


def _strip_team(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value)
    value = re.sub(r"\s+\d+\s*[–-]\s*\d+\s*$", "", value)
    return _clean_text(value)


def _structured_datetime(html: str) -> datetime | None:
    match = re.search(
        r"<[^>]+class=[\"'][^\"']*dtstart[^\"']*[\"'][^>]*(?:title=[\"'](?P<title>[^\"']+)[\"'])?[^>]*>(?P<text>[\s\S]*?)</[^>]+>",
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = unescape(match.group("title") or _html_text(match.group("text")))
    return _parse_json_datetime(raw)


def _parse_datetime_from_text(text: str) -> datetime | None:
    date_match = None
    for pattern in DATE_PATTERNS:
        date_match = pattern.search(text)
        if date_match:
            break
    time_match = TIME_RE.search(text)
    if not date_match or not time_match:
        return None

    day = int(date_match.group("day"))
    month = MONTHS[date_match.group("month").lower()]
    year = int(date_match.group("year"))
    hour = int(time_match.group("hour"))
    minute = int(time_match.group("minute"))
    ampm = (time_match.group("ampm") or "").lower()
    if ampm.startswith("p") and hour != 12:
        hour += 12
    if ampm.startswith("a") and hour == 12:
        hour = 0

    offset_hours = _offset_hours(time_match)
    local = datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=offset_hours)))
    return local.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)


def _parse_json_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return _parse_datetime_from_text(value)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)


def _offset_hours(time_match: re.Match[str]) -> int:
    if time_match.group("utc_hour"):
        sign = time_match.group("utc_sign")
        hours = int(time_match.group("utc_hour"))
        return hours if sign == "+" else -hours
    abbr = (time_match.group("abbr") or "").upper()
    return TZ_OFFSETS.get(abbr, -4)


def _match_id(text: str, fallback_index: int, home: str, away: str, starts_at: datetime) -> str:
    match = MATCH_ID_RE.search(text)
    if match:
        return f"M{int(match.group('number')):03d}"
    home_slug = re.sub(r"[^A-Za-z0-9]+", "", home)[:12] or "home"
    away_slug = re.sub(r"[^A-Za-z0-9]+", "", away)[:12] or "away"
    return f"X{starts_at:%Y%m%d%H%M}-{home_slug}-{away_slug}-{fallback_index:03d}"


def _stage_name(html_before_box: str) -> str:
    headings = re.findall(r"<h[2-4]\b[^>]*>([\s\S]*?)</h[2-4]>", html_before_box, re.IGNORECASE)
    for heading in reversed(headings):
        value = _clean_text(_html_text(heading))
        if value and not TITLE_SPLIT_RE.search(value):
            return value
    return "2026 FIFA World Cup"


def _venue(html: str, text: str) -> tuple[str, str]:
    match = re.search(r"<[^>]+class=[\"'][^\"']*location[^\"']*[\"'][^>]*>(?P<value>[\s\S]*?)</[^>]+>", html, re.IGNORECASE)
    if match:
        return _split_location(_clean_text(_html_text(match.group("value"))))

    for line in text.splitlines():
        line = _clean_text(line)
        if "," in line and not any(skip in line.lower() for skip in ["referee", "attendance", "report"]):
            if any(word in line for word in ["Stadium", "Field", "Park", "Arena", "Estadio"]):
                return _split_location(line)
    return "", ""


def _split_location(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split(",", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return value, ""


def _score(text: str) -> tuple[int | None, int | None]:
    for line in text.splitlines():
        if any(word in line.lower() for word in ["penalties", "aggregate"]):
            continue
        match = SCORE_RE.search(line)
        if match:
            return int(match.group("home")), int(match.group("away"))
    return None, None


def _goals(text: str, home: str, away: str) -> list[Goal]:
    goals: list[Goal] = []
    for line in text.splitlines():
        clean = _clean_text(line)
        if not clean or "Report" in clean:
            continue
        for match in GOAL_RE.finditer(clean):
            player = _clean_text(match.group("player")).strip("- ")
            if len(player) < 2 or player in {home, away}:
                continue
            goals.append(Goal(team="", player=player, minute=_clean_text(match.group("minute"))))
    return goals[:20]


def _dedupe(matches: list[Match]) -> list[Match]:
    by_id: dict[str, Match] = {}
    for match in matches:
        existing = by_id.get(match.match_id)
        if not existing or (match.status == "completed" and existing.status != "completed"):
            by_id[match.match_id] = match
    return list(by_id.values())


def _apply_overrides(matches: list[Match], overrides_path: Path) -> None:
    if not overrides_path.exists():
        return
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    by_id = {match.match_id: match for match in matches}
    for match_id, values in overrides.items():
        match = by_id.get(match_id)
        if not match or not isinstance(values, dict):
            continue
        for key in ["stage", "home", "away", "venue", "city", "source_url", "status"]:
            if key in values:
                setattr(match, key, values[key])
        if "home_score" in values:
            match.home_score = _as_int(values["home_score"])
        if "away_score" in values:
            match.away_score = _as_int(values["away_score"])
        if "starts_at_beijing" in values:
            parsed = _parse_json_datetime(str(values["starts_at_beijing"]))
            if parsed:
                match.starts_at_beijing = parsed
        if "goals" in values and isinstance(values["goals"], list):
            match.goals = [
                Goal(
                    team=str(goal.get("team") or ""),
                    player=str(goal.get("player") or ""),
                    minute=str(goal.get("minute") or ""),
                    note=str(goal.get("note") or ""),
                )
                for goal in values["goals"]
                if isinstance(goal, dict)
            ]
        if match.home_score is not None and match.away_score is not None:
            match.status = "completed"


def _nested(row: dict[str, Any], *keys: str) -> Any:
    current: Any = row
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _html_text(html: str) -> str:
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</(?:tr|div|p|li|th|td|caption|h[1-6])>", "\n", html, flags=re.IGNORECASE)
    return _clean_text_multiline(unescape(TAG_RE.sub(" ", html)))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _clean_text_multiline(value: str) -> str:
    lines = [_clean_text(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)
