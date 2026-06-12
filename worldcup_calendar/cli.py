from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .ics import render_calendar
from .models import Match
from .sources import fetch_matches
from .team_names import display_team_name

DEFAULT_OUTPUT = Path("docs/worldcup-2026.ics")
DEFAULT_JSON = Path("docs/matches.json")
DEFAULT_OVERRIDES = Path("data/overrides.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and serve a 2026 World Cup ICS calendar.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser("update", help="Fetch latest data and generate ICS.")
    update.add_argument("--source-url", help="Optional HTML or JSON source URL.")
    update.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="ICS output path.")
    update.add_argument("--json-output", type=Path, default=DEFAULT_JSON, help="JSON output path.")
    update.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES, help="Manual override JSON path.")

    serve = subparsers.add_parser("serve", help="Serve the generated ICS and expose an update endpoint.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--source-url")
    serve.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    serve.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    serve.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)

    args = parser.parse_args()
    if args.command == "update":
        matches = generate(args.source_url, args.output, args.json_output, args.overrides)
        print(f"Wrote {len(matches)} matches to {args.output}")
    elif args.command == "serve":
        serve_calendar(args.host, args.port, args.source_url, args.output, args.json_output, args.overrides)


def generate(
    source_url: str | None,
    output: Path = DEFAULT_OUTPUT,
    json_output: Path = DEFAULT_JSON,
    overrides: Path = DEFAULT_OVERRIDES,
) -> list[Match]:
    matches = fetch_matches(source_url=source_url, overrides_path=overrides)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_calendar(matches), encoding="utf-8", newline="")
    json_output.write_text(json.dumps([_match_dict(match) for match in matches], ensure_ascii=False, indent=2), encoding="utf-8")
    return matches


def serve_calendar(
    host: str,
    port: int,
    source_url: str | None,
    output: Path,
    json_output: Path,
    overrides: Path,
) -> None:
    try:
        generate(source_url, output, json_output, overrides)
    except Exception as exc:
        print(f"Initial update failed: {exc}")

    update_token = os.environ.get("UPDATE_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/health"}:
                self._send_text("ok\n", "text/plain")
            elif parsed.path == "/worldcup-2026.ics":
                self._send_file(output, "text/calendar; charset=utf-8")
            elif parsed.path == "/matches.json":
                self._send_file(json_output, "application/json; charset=utf-8")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/update":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            query = parse_qs(parsed.query)
            token = query.get("token", [""])[0]
            if update_token and token != update_token:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            try:
                matches = generate(source_url, output, json_output, overrides)
            except Exception as exc:
                self.send_error(HTTPStatus.BAD_GATEWAY, str(exc))
                return
            self._send_json({"status": "updated", "matches": len(matches)})

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _send_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "public, max-age=300")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_text(self, text: str, content_type: str) -> None:
            data = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, object]) -> None:
            self._send_text(json.dumps(payload, ensure_ascii=False) + "\n", "application/json; charset=utf-8")

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Serving http://{host}:{port}/worldcup-2026.ics")
    server.serve_forever()


def _match_dict(match: Match) -> dict[str, object]:
    data = asdict(match)
    data["starts_at_beijing"] = match.starts_at_beijing.isoformat()
    data["home_display"] = display_team_name(match.home)
    data["away_display"] = display_team_name(match.away)
    data["title_display"] = match.title
    return data
