from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .models import Goal, Match
from .team_names import PLAYER_TRANSLATIONS, player_chinese_name

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
PLAYER_TRANSLATION_CACHE: dict[str, str] = {}
GROUP_STAGE_RE = re.compile(r"^Group (?P<group>[A-L])$")
WINNER_GROUP_RE = re.compile(r"^Winner Group (?P<group>[A-L])$")
RUNNER_UP_GROUP_RE = re.compile(r"^Runner-up Group (?P<group>[A-L])$")
THIRD_GROUP_RE = re.compile(r"^3rd Group (?P<groups>[A-L](?:/[A-L])*)$")


class SourceError(RuntimeError):
    pass


def fetch_matches(
    source_url: str | None = None,
    overrides_path: Path | None = None,
    previous_matches_path: Path | None = None,
) -> list[Match]:
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

    previous_ids = _load_previous_match_ids(previous_matches_path)
    _normalize_match_ids(matches, previous_ids)
    matches = _dedupe(matches)
    if overrides_path:
        _apply_overrides(matches, overrides_path)
    _resolve_knockout_placeholders(matches)
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
    errors: list[str] = []

    for proxy in [None, *_local_proxy_candidates()]:
        try:
            if proxy:
                opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
                response = opener.open(request, timeout=30)
            else:
                response = urlopen(request, timeout=30)
            with response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace"), response.headers.get("content-type", "")
        except Exception as exc:
            label = proxy or "direct"
            errors.append(f"{label}: {exc}")
    raise SourceError("; ".join(errors))


def _local_proxy_candidates() -> list[str]:
    return [
        "http://127.0.0.1:7070",
        "http://127.0.0.1:7890",
        "http://127.0.0.1:7897",
        "http://127.0.0.1:10809",
        "http://127.0.0.1:8080",
    ]


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
    marker = re.compile(r"<div\b(?=[^>]*class=[\"'][^\"']*(?:footballbox|vevent)[^\"']*[\"'])", re.IGNORECASE)
    for match in marker.finditer(html):
        start = match.start()
        fragment = _balanced_div(html, start)
        if not fragment:
            continue
        text = _html_text(fragment)
        if "2026" not in text or not _parse_datetime_from_text(text):
            continue
        if not (_summary_text(fragment) or TITLE_SPLIT_RE.search(text)):
            continue
        boxes.append((start, fragment))
    boxes.sort(key=lambda item: item[0])
    return boxes


def _balanced_div(html: str, start: int) -> str:
    tag_re = re.compile(r"</?div\b[^>]*>", re.IGNORECASE)
    depth = 0
    for match in tag_re.finditer(html, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start : match.end()]
        else:
            depth += 1
    return ""


def _parse_match_box(full_html: str, box_item: tuple[int, str], source_url: str, fallback_index: int) -> Match | None:
    start_index, box = box_item
    text = _html_text(box)
    title = _summary_text(box) or _title_from_text(text)
    if not title:
        return None

    venue, city = _venue(box, text)
    starts_at = _structured_datetime(box) or _parse_datetime_from_text(text, default_offset_hours=_offset_for_location(venue, city))
    if not starts_at:
        return None

    home, away = _split_title(title)
    if not home or not away:
        return None

    match_id = _match_id(text, fallback_index, home, away, starts_at, box)
    stage = _stage_name(full_html[:start_index])
    home_score, away_score = _score(box, text)
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
        goals=_goals(text, home, away, box),
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
                        player_zh=str(goal.get("player_zh") or ""),
                    )
                    for goal in row.get("goals", [])
                    if isinstance(goal, dict)
                ],
            )
        )
    return matches


def _summary_text(html: str) -> str:
    home = _class_text(html, "fhome")
    away = _class_text(html, "faway")
    if home and away:
        return f"{home} v {away}"

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
    if "T" not in raw and not TIME_RE.search(raw):
        return None
    return _parse_json_datetime(raw)


def _parse_datetime_from_text(text: str, default_offset_hours: int = -4) -> datetime | None:
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

    offset_hours = _offset_hours(time_match, default_offset_hours)
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


def _offset_hours(time_match: re.Match[str], default_offset_hours: int = -4) -> int:
    if time_match.group("utc_hour"):
        sign = time_match.group("utc_sign")
        hours = int(time_match.group("utc_hour"))
        return hours if sign == "+" else -hours
    abbr = (time_match.group("abbr") or "").upper()
    return TZ_OFFSETS.get(abbr, default_offset_hours)


def _offset_for_location(venue: str, city: str) -> int:
    value = f"{venue} {city}".lower()
    pacific = [
        "bc place",
        "vancouver",
        "lumen field",
        "seattle",
        "levi's stadium",
        "santa clara",
        "sofi stadium",
        "inglewood",
    ]
    mountain = [
        "empower field",
        "denver",
    ]
    central = [
        "nrg stadium",
        "houston",
        "at&t stadium",
        "arlington",
        "arrowhead stadium",
        "kansas city",
    ]
    mexico_central = [
        "estadio azteca",
        "mexico city",
        "estadio akron",
        "zapopan",
        "estadio bbva",
        "guadalupe",
    ]
    eastern = [
        "bmo field",
        "toronto",
        "metlife stadium",
        "east rutherford",
        "gillette stadium",
        "foxborough",
        "lincoln financial field",
        "philadelphia",
        "mercedes-benz stadium",
        "atlanta",
        "hard rock stadium",
        "miami gardens",
    ]
    if any(item in value for item in pacific):
        return -7
    if any(item in value for item in mountain):
        return -6
    if any(item in value for item in central):
        return -5
    if any(item in value for item in mexico_central):
        return -6
    if any(item in value for item in eastern):
        return -4
    return -4


def _match_id(text: str, fallback_index: int, home: str, away: str, starts_at: datetime, html: str = "") -> str:
    score_text = _html_text(_class_html(html, "fscore")) if html else ""
    match = MATCH_ID_RE.search(score_text) or MATCH_ID_RE.search(text)
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
    match = re.search(r"<span\b(?=[^>]*itemprop=[\"']name address[\"'])[^>]*>(?P<value>[\s\S]*?)</span>", html, re.IGNORECASE)
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


def _score(html: str, text: str) -> tuple[int | None, int | None]:
    score_text = _clean_text(_html_text(_class_html(html, "fscore")))
    match = SCORE_RE.search(score_text)
    if match:
        return int(match.group("home")), int(match.group("away"))

    for line in text.splitlines():
        if any(word in line.lower() for word in ["penalties", "aggregate", "utc", "june", "july"]):
            continue
        match = SCORE_RE.search(line)
        if match:
            return int(match.group("home")), int(match.group("away"))
    return None, None


def _goals(text: str, home: str, away: str, html: str | None = None) -> list[Goal]:
    goals: list[Goal] = []
    if html:
        for team, class_name in [(home, "fhgoal"), (away, "fagoal")]:
            cell = _class_html(html, class_name)
            for player, minute, player_zh, note in _goal_pairs_from_html(cell):
                goals.append(Goal(team=team, player=player, minute=minute, note=note, player_zh=player_zh))
        if goals:
            return goals[:20]

    for line in text.splitlines():
        clean = _clean_text(line)
        if not clean or "Report" in clean:
            continue
        for match in GOAL_RE.finditer(clean):
            player = _clean_text(match.group("player")).strip("- ")
            if len(player) < 2 or player in {home, away}:
                continue
            goals.append(
                Goal(
                    team="",
                    player=player,
                    minute=_clean_text(match.group("minute")),
                    player_zh=player_chinese_name(player),
                )
            )
    return goals[:20]


def _class_text(html: str, class_name: str) -> str:
    value = _class_html(html, class_name)
    if not value:
        return ""
    text = _html_text(value)
    text = re.sub(r"\bMatch\s+\d+\b", "", text, flags=re.IGNORECASE)
    text = SCORE_RE.sub("", text)
    return _clean_text(text)


def _class_html(html: str, class_name: str) -> str:
    match = re.search(
        rf"<(?P<tag>td|th|div)\b(?=[^>]*class=[\"'][^\"']*\b{re.escape(class_name)}\b[^\"']*[\"'])[^>]*>(?P<value>[\s\S]*?)</(?P=tag)>",
        html,
        re.IGNORECASE,
    )
    return match.group("value") if match else ""


def _goal_pairs_from_html(html: str) -> list[tuple[str, str, str, str]]:
    goals: list[tuple[str, str, str, str]] = []
    if not html:
        return goals

    items = re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", html, re.IGNORECASE) or [html]
    for item in items:
        player, href = _player_from_goal_item(item)
        minutes = _goal_minutes(item)
        if player and minutes:
            player_zh = _player_translation(player, href)
            note = _goal_note(item)
            for minute in minutes:
                goals.append((
                    player,
                    minute,
                    player_zh,
                    note,
                ))
    return goals


def _goal_minutes(html: str) -> list[str]:
    minutes: list[str] = []
    for minute_html in re.findall(r"<span>(?P<minute>\d{1,3}(?:\+\d{1,2})?'[\s\S]*?)</span>", html, re.IGNORECASE):
        minute = _clean_text(_html_text(minute_html))
        minute = minute.replace("( o.g. )", "(o.g.)")
        if minute:
            minutes.append(minute)
    return minutes


def _player_from_goal_item(html: str) -> tuple[str, str]:
    link_match = re.search(r"<a\b(?P<attrs>[^>]*)>(?P<text>[\s\S]*?)</a>", html, re.IGNORECASE)
    if not link_match:
        return "", ""
    attrs = link_match.group("attrs")
    title = _attr(attrs, "title")
    href = _attr(attrs, "href")
    raw_name = title or _html_text(link_match.group("text"))
    return _clean_player_name(unescape(raw_name)), unescape(href)


def _goal_note(html: str) -> str:
    note_translations = {
        "Own goal": "乌龙球",
        "Penalty scored": "点球",
    }
    notes = []
    for title in re.findall(r"<span\b[^>]*title=[\"'](?P<title>[^\"']+)[\"']", html, re.IGNORECASE):
        note = _clean_text(unescape(title))
        if note and note.lower() != "goal":
            notes.append(note_translations.get(note, note))
    return ", ".join(dict.fromkeys(notes))


def _player_translation(player: str, href: str) -> str:
    if player in PLAYER_TRANSLATION_CACHE:
        return PLAYER_TRANSLATION_CACHE[player]
    if player in PLAYER_TRANSLATIONS:
        PLAYER_TRANSLATION_CACHE[player] = PLAYER_TRANSLATIONS[player]
        return PLAYER_TRANSLATIONS[player]
    normalized_translation = player_chinese_name(player)
    if normalized_translation:
        PLAYER_TRANSLATION_CACHE[player] = normalized_translation
        return normalized_translation
    if not href.startswith("/wiki/"):
        PLAYER_TRANSLATION_CACHE[player] = ""
        return ""

    page_title = unquote(href.removeprefix("/wiki/").split("#", 1)[0]).replace("_", " ")
    api_url = (
        "https://en.wikipedia.org/w/api.php?action=query&prop=langlinks"
        f"&titles={quote(page_title, safe='')}&lllang=zh&format=json"
    )
    try:
        payload = json.loads(_download(api_url)[0])
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            for link in page.get("langlinks", []):
                translated = _clean_player_name(str(link.get("*") or ""))
                if translated:
                    PLAYER_TRANSLATION_CACHE[player] = translated
                    return translated
    except Exception:
        pass

    PLAYER_TRANSLATION_CACHE[player] = ""
    return ""


def _clean_player_name(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value)
    return _clean_text(value)


def _attr(attrs: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}=[\"'](?P<value>[^\"']*)[\"']", attrs, re.IGNORECASE)
    return match.group("value") if match else ""


def _dedupe(matches: list[Match]) -> list[Match]:
    by_id: dict[str, Match] = {}
    for match in matches:
        existing = by_id.get(match.match_id)
        if not existing or _is_better_match_record(match, existing):
            by_id[match.match_id] = match
    return list(by_id.values())


def _is_better_match_record(candidate: Match, existing: Match) -> bool:
    if candidate.status == "completed" and existing.status != "completed":
        return True
    if candidate.status != existing.status:
        return False
    if len(candidate.goals) > len(existing.goals):
        return True
    return _is_specific_source(candidate.source_url) and not _is_specific_source(existing.source_url)


def _is_specific_source(source_url: str) -> bool:
    return bool(source_url) and not source_url.rstrip("/").endswith("/2026_FIFA_World_Cup")


def _is_main_worldcup_source(source_url: str) -> bool:
    return bool(source_url) and source_url.rstrip("/").endswith("/2026_FIFA_World_Cup")


def _main_source_fallback_id(match: Match) -> str:
    if not _is_main_worldcup_source(match.source_url):
        return ""
    fallback_number = _x_fallback_number(match.match_id)
    return f"M{fallback_number:03d}" if fallback_number else ""


def _x_fallback_number(match_id: str) -> int | None:
    match = re.search(r"-(?P<number>\d{3})$", match_id)
    if not match:
        return None
    number = int(match.group("number"))
    return number if 1 <= number <= 104 else None


def _load_previous_match_ids(path: Path | None) -> dict[str, dict[tuple[str, ...], str]]:
    empty: dict[str, dict[tuple[str, ...], str]] = {"exact": {}, "teams": {}, "slot": {}}
    if not path or not path.exists():
        return empty
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return empty
    if not isinstance(rows, list):
        return empty

    exact: dict[tuple[str, ...], str] = {}
    teams_seen: dict[tuple[str, ...], set[str]] = {}
    slot_seen: dict[tuple[str, ...], set[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("match_id") or "")
        start = str(row.get("starts_at_beijing") or "")
        home = str(row.get("home") or "")
        away = str(row.get("away") or "")
        stage = str(row.get("stage") or "")
        venue = str(row.get("venue") or "")
        city = str(row.get("city") or "")
        if not match_id or not start or not home or not away:
            continue
        exact[(start, home, away)] = match_id
        teams_seen.setdefault((home, away), set()).add(match_id)
        slot_seen.setdefault((start, stage, venue, city), set()).add(match_id)

    teams = {key: next(iter(ids)) for key, ids in teams_seen.items() if len(ids) == 1}
    slot = {key: next(iter(ids)) for key, ids in slot_seen.items() if len(ids) == 1}
    return {"exact": exact, "teams": teams, "slot": slot}


def _historical_match_id(match: Match, previous_ids: dict[str, dict[tuple[str, ...], str]]) -> str:
    start = match.starts_at_beijing.isoformat()
    return (
        previous_ids["exact"].get((start, match.home, match.away))
        or previous_ids["teams"].get((match.home, match.away))
        or previous_ids["slot"].get((start, match.stage, match.venue, match.city))
        or ""
    )


def _normalize_match_ids(matches: list[Match], previous_ids: dict[str, dict[tuple[str, ...], str]] | None = None) -> None:
    previous_ids = previous_ids or {"exact": {}, "teams": {}, "slot": {}}
    for match in matches:
        if not match.match_id.startswith("X"):
            continue
        historical_id = _historical_match_id(match, previous_ids)
        if historical_id:
            match.match_id = historical_id

    canonical_by_signature = {
        _match_signature(match): match.match_id
        for match in matches
        if not match.match_id.startswith("X")
    }
    team_ids: dict[tuple[str, str], set[str]] = {}
    for match in matches:
        if match.match_id.startswith("X") or not _is_completed(match):
            continue
        team_ids.setdefault(_team_signature(match), set()).add(match.match_id)
    canonical_by_teams = {
        teams: next(iter(ids))
        for teams, ids in team_ids.items()
        if len(ids) == 1
    }
    unique_signatures: list[tuple[object, ...]] = []
    seen_signatures: set[tuple[object, ...]] = set()
    for match in sorted(matches, key=lambda item: (item.starts_at_beijing, item.home, item.away, item.match_id)):
        signature = _match_signature(match)
        if signature not in seen_signatures:
            unique_signatures.append(signature)
            seen_signatures.add(signature)
    ordinal_by_signature = {
        signature: f"M{index:03d}"
        for index, signature in enumerate(unique_signatures, start=1)
    }
    ordinal_by_teams: dict[tuple[str, str], str] = {}
    for signature in unique_signatures:
        for match in matches:
            if _match_signature(match) == signature and _is_concrete_team_pair(match):
                ordinal_by_teams.setdefault(_team_signature(match), ordinal_by_signature[signature])
                break

    for match in matches:
        if not match.match_id.startswith("X"):
            continue
        signature = _match_signature(match)
        match.match_id = (
            canonical_by_signature.get(signature)
            or (canonical_by_teams.get(_team_signature(match)) if _is_completed(match) else None)
            or ordinal_by_teams.get(_team_signature(match))
            or _main_source_fallback_id(match)
            or ordinal_by_signature[signature]
        )


def _match_signature(match: Match) -> tuple[object, ...]:
    return (match.starts_at_beijing, match.home, match.away)


def _team_signature(match: Match) -> tuple[str, str]:
    return (match.home, match.away)


def _is_concrete_team_pair(match: Match) -> bool:
    placeholders = ("Winner", "Loser", "Runner-up", "3rd ")
    return not match.home.startswith(placeholders) and not match.away.startswith(placeholders)


def _is_completed(match: Match) -> bool:
    return match.home_score is not None and match.away_score is not None


def _resolve_knockout_placeholders(matches: list[Match]) -> None:
    rankings, third_entries = _completed_group_rankings(matches)
    if not rankings:
        return
    qualified_thirds = _definite_qualified_third_groups(third_entries, expected_groups=len(rankings))

    for match in matches:
        if _group_letter(match.stage):
            continue
        match.home = _resolve_placeholder_team(match.home, rankings, qualified_thirds)
        match.away = _resolve_placeholder_team(match.away, rankings, qualified_thirds)


def _resolve_placeholder_team(
    value: str,
    rankings: dict[str, dict[int, str]],
    qualified_thirds: set[str],
) -> str:
    winner = WINNER_GROUP_RE.match(value)
    if winner:
        return rankings.get(winner.group("group"), {}).get(1) or value

    runner_up = RUNNER_UP_GROUP_RE.match(value)
    if runner_up:
        return rankings.get(runner_up.group("group"), {}).get(2) or value

    third = THIRD_GROUP_RE.match(value)
    if third:
        groups = third.group("groups").split("/")
        possible_groups = [
            group
            for group in groups
            if group in qualified_thirds and rankings.get(group, {}).get(3)
        ]
        if len(possible_groups) == 1:
            return rankings[possible_groups[0]][3]
    return value


def _completed_group_rankings(matches: list[Match]) -> tuple[dict[str, dict[int, str]], list[tuple[str, str, tuple[int, int, int]]]]:
    group_matches: dict[str, list[Match]] = {}
    for match in matches:
        group = _group_letter(match.stage)
        if group:
            group_matches.setdefault(group, []).append(match)

    rankings: dict[str, dict[int, str]] = {}
    third_entries: list[tuple[str, str, tuple[int, int, int]]] = []
    for group, rows in group_matches.items():
        if len(rows) < 6 or any(match.home_score is None or match.away_score is None for match in rows):
            continue
        ranked = _rank_completed_group(rows)
        if not ranked:
            continue
        rankings[group] = {position: team for position, team, _ in ranked if position <= 3}
        third = next((entry for entry in ranked if entry[0] == 3), None)
        if third:
            _, team, sort_key = third
            third_entries.append((group, team, sort_key))
    return rankings, third_entries


def _rank_completed_group(matches: list[Match]) -> list[tuple[int, str, tuple[int, int, int]]]:
    stats: dict[str, dict[str, int]] = {}
    for match in matches:
        if match.home_score is None or match.away_score is None:
            return []
        for team in [match.home, match.away]:
            stats.setdefault(team, {"points": 0, "gf": 0, "ga": 0})
        stats[match.home]["gf"] += match.home_score
        stats[match.home]["ga"] += match.away_score
        stats[match.away]["gf"] += match.away_score
        stats[match.away]["ga"] += match.home_score
        if match.home_score > match.away_score:
            stats[match.home]["points"] += 3
        elif match.home_score < match.away_score:
            stats[match.away]["points"] += 3
        else:
            stats[match.home]["points"] += 1
            stats[match.away]["points"] += 1

    rows = [
        (team, (values["points"], values["gf"] - values["ga"], values["gf"]))
        for team, values in stats.items()
    ]
    rows.sort(key=lambda item: item[1], reverse=True)

    ranked: list[tuple[int, str, tuple[int, int, int]]] = []
    for index, (team, sort_key) in enumerate(rows, start=1):
        previous_key = rows[index - 2][1] if index > 1 else None
        next_key = rows[index][1] if index < len(rows) else None
        if sort_key in {previous_key, next_key}:
            continue
        ranked.append((index, team, sort_key))
    return ranked


def _definite_qualified_third_groups(third_entries: list[tuple[str, str, tuple[int, int, int]]], expected_groups: int) -> set[str]:
    if expected_groups < 12 or len(third_entries) < 12:
        return set()
    third_entries.sort(key=lambda item: item[2], reverse=True)
    cutoff_key = third_entries[7][2]
    next_key = third_entries[8][2] if len(third_entries) > 8 else None
    return {
        group
        for group, _, sort_key in third_entries[:8]
        if sort_key != cutoff_key or next_key != cutoff_key
    }


def _group_letter(stage: str) -> str:
    match = GROUP_STAGE_RE.match(stage)
    return match.group("group") if match else ""


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
                    player_zh=str(goal.get("player_zh") or ""),
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
