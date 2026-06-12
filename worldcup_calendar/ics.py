from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Match

BEIJING_TZID = "Asia/Shanghai"


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return [line]

    output: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > 75:
            output.append(current)
            current = " " + char
        else:
            current = candidate
    if current:
        output.append(current)
    return output


def _line(name: str, value: str) -> list[str]:
    return _fold(f"{name}:{value}")


def _description(match: Match) -> str:
    parts = [
        f"阶段: {match.stage}",
        f"状态: {'已完赛' if match.status == 'completed' else '未完赛'}",
    ]
    if match.location:
        parts.append(f"场地: {match.location}")
    if match.goals:
        parts.append("进球:")
        for goal in match.goals:
            note = f" ({goal.note})" if goal.note else ""
            parts.append(f"- {goal.team}: {goal.player} {goal.minute}{note}")
    if match.source_url:
        parts.append(f"来源: {match.source_url}")
    return "\n".join(parts)


def render_calendar(matches: list[Match]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WorldCup 2026 Beijing Calendar//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:2026 FIFA World Cup 北京时间",
        f"X-WR-TIMEZONE:{BEIJING_TZID}",
        "BEGIN:VTIMEZONE",
        f"TZID:{BEIJING_TZID}",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for match in sorted(matches, key=lambda item: (item.starts_at_beijing, item.match_id)):
        start = match.starts_at_beijing.strftime("%Y%m%dT%H%M%S")
        end = (match.starts_at_beijing + timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")
        uid = f"{match.match_id.lower()}@worldcup-2026-calendar"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"DTSTART;TZID={BEIJING_TZID}:{start}",
                f"DTEND;TZID={BEIJING_TZID}:{end}",
            ]
        )
        for folded in _line("SUMMARY", _escape(match.title)):
            lines.append(folded)
        if match.location:
            for folded in _line("LOCATION", _escape(match.location)):
                lines.append(folded)
        for folded in _line("DESCRIPTION", _escape(_description(match))):
            lines.append(folded)
        if match.source_url:
            for folded in _line("URL", _escape(match.source_url)):
                lines.append(folded)
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
