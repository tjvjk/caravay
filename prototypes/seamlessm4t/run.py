#!/usr/bin/env python3
"""THROWAWAY acceptance spike for SeamlessM4T Medium on Apple Silicon."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from transformers import (
    AutoProcessor,
    SeamlessM4TForSpeechToText,
    SeamlessM4TForTextToText,
)


MODEL_ID = "facebook/hf-seamless-m4t-medium"
SAMPLE_RATE = 16_000


def read_audio(path: Path, start: float, duration: float) -> np.ndarray:
    command = [
        "ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration),
        "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-f", "f32le", "pipe:1",
    ]
    return np.frombuffer(subprocess.check_output(command), dtype=np.float32).copy()


def sync(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()


def timed_generate(model, device, **kwargs):
    sync(device)
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**kwargs)
    sync(device)
    return output, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float, default=20)
    parser.add_argument("--chunk", type=float, default=20)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    device = torch.device(args.device)
    if device.type == "mps" and not torch.backends.mps.is_available():
        raise SystemExit("MPS is not available")
    dtype = torch.float16 if device.type == "mps" else torch.float32

    load_started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    speech_model = SeamlessM4TForSpeechToText.from_pretrained(
        MODEL_ID, dtype=dtype
    ).to(device).eval()
    text_model = SeamlessM4TForTextToText.from_pretrained(
        MODEL_ID, dtype=dtype
    ).to(device).eval()
    load_seconds = time.perf_counter() - load_started

    rows = []
    offset = 0.0
    while offset < args.duration:
        duration = min(args.chunk, args.duration - offset)
        audio = read_audio(args.audio, args.start + offset, duration)
        speech = processor(audio=audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        speech = {key: value.to(device=device, dtype=dtype) for key, value in speech.items()}

        direct_tokens, direct_seconds = timed_generate(
            speech_model, device, **speech, tgt_lang="eng"
        )
        direct = processor.decode(direct_tokens[0].tolist(), skip_special_tokens=True)

        asr_tokens, asr_seconds = timed_generate(
            speech_model, device, **speech, tgt_lang="hye"
        )
        armenian = processor.decode(asr_tokens[0].tolist(), skip_special_tokens=True)

        text = processor(text=armenian, src_lang="hye", return_tensors="pt")
        text = {key: value.to(device) for key, value in text.items()}
        translated_tokens, text_seconds = timed_generate(
            text_model, device, **text, tgt_lang="eng"
        )
        cascaded = processor.decode(translated_tokens[0].tolist(), skip_special_tokens=True)

        row = {
            "start_seconds": args.start + offset,
            "duration_seconds": duration,
            "direct_english": direct,
            "armenian_asr": armenian,
            "cascaded_english": cascaded,
            "timings_seconds": {
                "direct": direct_seconds,
                "asr": asr_seconds,
                "text_translation": text_seconds,
            },
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        offset += duration

    result = {
        "prototype": "THROWAWAY",
        "model": MODEL_ID,
        "device": args.device,
        "machine": platform.platform(),
        "torch": torch.__version__,
        "load_seconds": load_seconds,
        "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3,
        "chunks": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
