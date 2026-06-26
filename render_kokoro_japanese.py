#!/usr/bin/env python3
"""Render Japanese podcast narration with the shared Kokoro-82M engine.

The renderer supports either a single narrator or a light two-host transcript
using speaker labels such as:

    ミミ：おはようさんです。
    健司：今朝のポイントを見ていきましょう。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import soundfile as sf
import torch
from kokoro import KPipeline
from misaki import ja


SAMPLE_RATE = 24000
DEFAULT_VOICE = "jf_nezumi"
DEFAULT_FEMALE_VOICE = "jf_nezumi"
DEFAULT_MALE_VOICE = "am_michael"
DEFAULT_SPEED = 0.96
KOKORO_VOICES = (
    "am_michael",
    "am_puck",
    "af_heart",
    "jf_alpha",
    "jf_gongitsune",
    "jf_nezumi",
    "jf_tebukuro",
)
SPEAKER_LABELS = {
    "ミミ": "female",
    "Mimi": "female",
    "mimi": "female",
    "健司": "male",
    "ケンジ": "male",
    "Kenji": "male",
    "kenji": "male",
}


def prepare_japanese_pipeline() -> KPipeline:
    """Create Kokoro's Japanese pipeline with pyopenjtalk G2P.

    This function is intentionally idempotent. Earlier versions monkeypatched
    Misaki inside every synthesis call, which broke subsequent renders in the
    same Python process.
    """

    if not getattr(ja.JAG2P, "_mimis_pyopenjtalk_patch", False):
        original_jag2p = ja.JAG2P

        class PyOpenJTalkJAG2P(original_jag2p):
            _mimis_pyopenjtalk_patch = True

            def __init__(self, *args, **kwargs) -> None:
                kwargs["version"] = "pyopenjtalk"
                super().__init__(*args, **kwargs)

        ja.JAG2P = PyOpenJTalkJAG2P

    return KPipeline(
        lang_code="j",
        repo_id="hexgrad/Kokoro-82M",
        device="cpu",
    )


def pronunciation_overrides(text: str) -> str:
    """Apply small text-only pronunciation hints for synthesis.

    The transcript can keep normal spelling while the TTS input gets safer
    Japanese readings. This specifically prevents Latin "Kyoto" from being
    read like an English approximation and reinforces 京都 as きょうと.
    """

    text = re.sub(r"\bKyoto\b", "きょうと", text, flags=re.IGNORECASE)
    text = text.replace("京都", "きょうと")
    text = text.replace("Mimi's Podcast", "ミミのポッドキャスト")
    return text


def synthesize_to_tensor(
    pipeline: KPipeline,
    text: str,
    voice: str,
    speed: float,
) -> torch.Tensor:
    chunks: list[torch.Tensor] = []
    for result in pipeline(
        pronunciation_overrides(text),
        voice=voice,
        speed=speed,
        split_pattern=r"\n+",
    ):
        if result.audio is not None:
            chunks.append(result.audio.detach().cpu())
    if not chunks:
        raise RuntimeError(f"No audio generated using Kokoro voice {voice}")
    return torch.cat(chunks)


def synthesize(text: str, voice: str, speed: float, wav_path: Path) -> None:
    pipeline = prepare_japanese_pipeline()
    audio = synthesize_to_tensor(pipeline, text, voice, speed)
    sf.write(wav_path, audio.numpy(), SAMPLE_RATE)


def parse_dialogue(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    current_speaker = "female"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        spoken = "\n".join(line for line in current_lines if line.strip()).strip()
        if spoken:
            segments.append((current_speaker, spoken))
        current_lines = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^([^：:]{1,16})[：:]\s*(.*)$", line)
        if match and match.group(1).strip() in SPEAKER_LABELS:
            flush()
            current_speaker = SPEAKER_LABELS[match.group(1).strip()]
            if match.group(2).strip():
                current_lines.append(match.group(2).strip())
        else:
            current_lines.append(line)

    flush()
    return segments


def synthesize_dialogue(
    text: str,
    female_voice: str,
    male_voice: str,
    speed: float,
    wav_path: Path,
) -> None:
    pipeline = prepare_japanese_pipeline()
    pieces: list[torch.Tensor] = []
    pause = torch.zeros(int(SAMPLE_RATE * 0.22))
    for speaker, spoken in parse_dialogue(text):
        voice = male_voice if speaker == "male" else female_voice
        pieces.append(synthesize_to_tensor(pipeline, spoken, voice, speed))
        pieces.append(pause)
    if not pieces:
        raise RuntimeError("No dialogue audio generated.")
    sf.write(wav_path, torch.cat(pieces).numpy(), SAMPLE_RATE)


def encode_mp3(wav_path: Path, output_path: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to encode MP3 audio.")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav_path),
            "-af",
            "highpass=f=55,loudnorm=I=-16:TP=-1.5:LRA=9",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "96k",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(output_path),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--voice", choices=KOKORO_VOICES, default=DEFAULT_VOICE)
    parser.add_argument("--dialogue", action="store_true")
    parser.add_argument(
        "--female-voice",
        choices=KOKORO_VOICES,
        default=DEFAULT_FEMALE_VOICE,
    )
    parser.add_argument(
        "--male-voice",
        choices=KOKORO_VOICES,
        default=DEFAULT_MALE_VOICE,
    )
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Input text is empty.")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mimis-kokoro-") as temp:
        wav_path = Path(temp) / "speech.wav"
        if args.dialogue:
            synthesize_dialogue(
                text,
                female_voice=args.female_voice,
                male_voice=args.male_voice,
                speed=args.speed,
                wav_path=wav_path,
            )
        else:
            synthesize(text, args.voice, args.speed, wav_path)
        encode_mp3(wav_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
