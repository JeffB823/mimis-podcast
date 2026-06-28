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
- Books: cover new Japanese-language novels; distinguish independent reviews from publisher marketing.

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
- Primary listener: Japanese-speaking women in their 50s who want a calm,
  intelligent morning companion that helps them feel informed and steadier.

EDITORIAL SPECIFICATION
{editorial}

VERIFIED RESEARCH DOSSIER
{research}

OUTPUT RULES
- Output only the words the two hosts should speak.
- Write entirely in natural spoken Japanese.
- Do not output headings, bullets, citations, URLs, markdown, or stage directions.
- Format every spoken turn on its own line beginning exactly with either
  ミミ： or 健司：.
- Start with ミミ saying the show name and exact date.
- Start with a short emotional morning check-in before the headline preview.
- Use ミミ as Host 1: the emotional center, a calm, polished, trustworthy
  morning companion with light Kyoto warmth. Use 健司 as Host 2: warmer,
  conversational, curious, and reactive; he should act as the listener proxy
  by asking practical questions and creating natural handoffs without filler.
- Shape the program for Japanese-speaking women in their 50s. Make it feel
  like a morning reset, not generic news. The listener should come away
  thinking: "I feel informed, and Mimi understands this stage of life."
- Include a signature health segment called 50代からのからだノート with one
  small evidence-safe practical takeaway for today.
- End with three short takeaways, then a brief recurring reflection called
  ミミのひとこと.
- Write native spoken Japanese that sounds like a real morning podcast, not a
  literal translation or textbook essay. Vary sentence length, endings, and
  breath patterns. Avoid repetitive です / ます chains.
- Include concise inline delivery notes and only occasional section-break
  pause markers where they improve pacing or emotional variation. Allowed notes include [warmly], [calmly],
  [slightly upbeat], [thoughtful], [soft emphasis], [transitioning],
  [conversational], [pause 0.6s], and [pause 1.0s].
- Do not use short micro-pause tags such as [pause 0.3s]. Let punctuation and
  natural phrasing handle short breaths.
- Do not overuse tags. They should shape the audio; they are not content.
- Add katakana reading help in parentheses for English names, organizations,
  places, and technical terms when it helps native-level audio.
- Spell Kyoto as 京都, not as the Latin word Kyoto.
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
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")

    if config.get("voice_engine") == "kokoro":
        final_path = script_path.parent / f"episode.{config['audio_format']}"
        env = os.environ.copy()
        env.setdefault("HF_HOME", "/Users/jeffbechtel/Morrning Brief GPT/.hf-cache")
        python = env.get(
            "MIMIS_KOKORO_PYTHON",
            "/Users/jeffbechtel/Morrning Brief GPT/.venv-kokoro/bin/python",
        )
        subprocess.run(
            [
                python,
                str(ROOT / "render_kokoro_japanese.py"),
                str(script_path),
                str(final_path),
                "--dialogue",
                "--female-voice",
                config.get("female_voice", "jf_nezumi"),
                "--male-voice",
                config.get("male_voice", "am_michael"),
                "--speed",
                str(config.get("kokoro_speed", 0.96)),
            ],
            env=env,
            check=True,
        )
        return final_path

    require_api_key()

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
