#!/usr/bin/env python3
"""Generate Mimi's Podcast: researched Japanese script and podcast audio."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
EDITORIAL_PATH = ROOT / "prompts" / "editorial.md"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def episode_date(value: str | None, timezone: str) -> str:
    if value:
        return date.fromisoformat(value).isoformat()
    return (
        date.today().isoformat()
        if not timezone
        else datetime.now(ZoneInfo(timezone)).date().isoformat()
    )


def require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Set it in your shell; do not paste it into chat."
        )


def output_dir(day: str) -> Path:
    path = ROOT / "output" / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def research_prompt(config: dict[str, Any], day: str) -> str:
    return f"""
Research the daily briefing for {config['show_name']} dated {day}, using
{config['timezone']} as the editorial cutoff. You MUST search the live web.

Return an English-language research dossier with a section for every topic:
1. U.S. national news
2. Virginia Beach news
3. Kyoto news (search Japanese-language sources too)
4. Professional sumo
5. Los Angeles Dodgers
6. Mature women's health: evidence-based detox/cleanse and menopause coverage
7. {config['book_review_scope']}

For each section:
- Select at most three consequential, genuinely current items.
- Give exact event and publication dates.
- Separate confirmed fact, source claim, and inference.
- Explain why each item matters and what happens next.
- Include source citations supplied by web search.
- If there is no meaningful fresh development, say so instead of padding.

Source standards:
- Prefer primary and official sources, then reputable local or wire reporting.
- Sumo: prioritize sumo.or.jp and official tournament information.
- Dodgers: prioritize MLB/Dodgers official schedule, score, roster, and injury data.
- Health: prioritize FDA, NIH, CDC, womenshealth.gov, menopause.org, ACOG,
  peer-reviewed journals, and major academic medical centers. Do not validate
  detox marketing claims without clinical evidence.
- Books: distinguish independent reviews from publisher marketing.

End with a compact fact-check table listing names, dates, scores, records,
rankings, medical claims, and book publication details that the script writer
must preserve exactly.
""".strip()


def script_prompt(
    config: dict[str, Any], day: str, research: str, editorial: str
) -> str:
    return f"""
Write the complete spoken script for the show below.

SHOW CONFIGURATION
- Japanese title: {config['show_name']}
- English title: {config['show_name_english']}
- Tagline: {config['tagline']}
- Episode date: {day}
- Target runtime: {config['target_minutes']} minutes
- National news means: {config['national_news_country']}
- Book scope: {config['book_review_scope']}

EDITORIAL SPECIFICATION
{editorial}

VERIFIED RESEARCH DOSSIER
{research}

OUTPUT RULES
- Output only the words the host should speak.
- Write entirely in natural spoken Japanese.
- Do not output headings, bullets, citations, URLs, markdown, or stage directions.
- Start with the show name and exact date.
- Preserve all verified names, dates, scores, standings, medical distinctions,
  and book details exactly.
- If the research dossier lacks a verified item, omit it; never fill gaps from memory.
""".strip()


def serialize_response(response: Any) -> str:
    if hasattr(response, "model_dump_json"):
        return response.model_dump_json(indent=2)
    return json.dumps(response, ensure_ascii=False, indent=2, default=str)


def extract_sources(value: Any) -> list[dict[str, str]]:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    found: dict[str, dict[str, str]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "url_citation" and node.get("url"):
                url = str(node["url"])
                found[url] = {
                    "title": str(node.get("title") or url),
                    "url": url,
                }
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return list(found.values())


def generate_script(config: dict[str, Any], day: str) -> Path:
    require_api_key()
    from openai import OpenAI

    client = OpenAI()
    out = output_dir(day)

    research_response = client.responses.create(
        model=config["research_model"],
        reasoning={"effort": "medium"},
        tools=[
            {
                "type": "web_search",
                "user_location": config["web_search_location"],
            }
        ],
        tool_choice="required",
        input=research_prompt(config, day),
    )
    research = research_response.output_text.strip()
    (out / "research.md").write_text(research + "\n", encoding="utf-8")
    (out / "research-response.json").write_text(
        serialize_response(research_response) + "\n", encoding="utf-8"
    )
    (out / "sources.json").write_text(
        json.dumps(
            extract_sources(research_response),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    editorial = EDITORIAL_PATH.read_text(encoding="utf-8")
    script_response = client.responses.create(
        model=config["script_model"],
        reasoning={"effort": "medium"},
        input=script_prompt(config, day, research, editorial),
    )
    script_path = out / "script.txt"
    script_path.write_text(script_response.output_text.strip() + "\n", encoding="utf-8")
    (out / "script-response.json").write_text(
        serialize_response(script_response) + "\n", encoding="utf-8"
    )
    return script_path


def clean_spoken_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, limit: int = 3800) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(paragraph) > limit:
            split_at = max(
                paragraph.rfind(mark, 0, limit)
                for mark in ("。", "！", "？", "\n")
            )
            if split_at < limit // 2:
                split_at = limit
            else:
                split_at += 1
            chunks.append(paragraph[:split_at].strip())
            paragraph = paragraph[split_at:].strip()
        current = paragraph

    if current:
        chunks.append(current)
    return chunks


def synthesize_audio(config: dict[str, Any], script_path: Path) -> Path:
    require_api_key()
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")

    from openai import OpenAI

    client = OpenAI()
    text = clean_spoken_text(script_path.read_text(encoding="utf-8"))
    chunks = chunk_text(text)
    out = script_path.parent
    parts_dir = out / "audio-parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    part_paths: list[Path] = []

    for index, chunk in enumerate(chunks, start=1):
        part_path = parts_dir / f"part-{index:02d}.{config['audio_format']}"
        with client.audio.speech.with_streaming_response.create(
            model=config["speech_model"],
            voice=config["voice"],
            input=chunk,
            instructions=config["tts_instructions"],
            response_format=config["audio_format"],
        ) as response:
            response.stream_to_file(part_path)
        part_paths.append(part_path)

    final_path = out / f"episode.{config['audio_format']}"
    if len(part_paths) == 1:
        shutil.copyfile(part_paths[0], final_path)
        return final_path

    if not shutil.which("ffmpeg"):
        print(
            f"ffmpeg was not found; leaving {len(part_paths)} audio parts in {parts_dir}",
            file=sys.stderr,
        )
        return parts_dir

    concat_file = parts_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.name}'\n" for path in part_paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file.name,
            "-c",
            "copy",
            str(final_path),
        ],
        cwd=parts_dir,
        check=True,
    )
    concat_file.unlink(missing_ok=True)
    return final_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("script", "run"):
        command = subparsers.add_parser(name)
        command.add_argument("--date", help="Episode date in YYYY-MM-DD format")

    audio = subparsers.add_parser("audio")
    audio.add_argument("--script", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()

    if args.command == "audio":
        result = synthesize_audio(config, args.script.resolve())
        print(result)
        return

    day = episode_date(args.date, config["timezone"])
    script = generate_script(config, day)
    print(script)
    if args.command == "run":
        print(synthesize_audio(config, script))


if __name__ == "__main__":
    main()
