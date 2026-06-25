#!/usr/bin/env python3
"""Render Japanese podcast narration with the shared Kokoro-82M engine."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import soundfile as sf
import torch
from kokoro import KPipeline
from misaki import ja


SAMPLE_RATE = 24000
DEFAULT_VOICE = "jf_alpha"
DEFAULT_SPEED = 0.96
JAPANESE_FEMALE_VOICES = (
    "jf_alpha",
    "jf_gongitsune",
    "jf_nezumi",
    "jf_tebukuro",
)


def synthesize(text: str, voice: str, speed: float, wav_path: Path) -> None:
    # Kokoro 0.9.4 defaults to Misaki's older Cutlet tokenizer, which requires
    # a separate full UniDic download. Use Misaki's newer pyopenjtalk path for
    # Japanese pitch accents and phrase merging instead.
    original_jag2p = ja.JAG2P

    class PyOpenJTalkJAG2P(original_jag2p):
        def __init__(self) -> None:
            super().__init__(version="pyopenjtalk")

    ja.JAG2P = PyOpenJTalkJAG2P
    pipeline = KPipeline(
        lang_code="j",
        repo_id="hexgrad/Kokoro-82M",
        device="cpu",
    )
    chunks: list[torch.Tensor] = []
    for result in pipeline(
        text,
        voice=voice,
        speed=speed,
        split_pattern=r"\n+",
    ):
        if result.audio is not None:
            chunks.append(result.audio.detach().cpu())
    if not chunks:
        raise RuntimeError(f"No audio generated using Kokoro voice {voice}")
    sf.write(wav_path, torch.cat(chunks).numpy(), SAMPLE_RATE)


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
    parser.add_argument("--voice", choices=JAPANESE_FEMALE_VOICES, default=DEFAULT_VOICE)
    parser.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("Input text is empty.")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mimis-kokoro-") as temp:
        wav_path = Path(temp) / "speech.wav"
        synthesize(text, args.voice, args.speed, wav_path)
        encode_mp3(wav_path, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
