#!/usr/bin/env python3
"""THROWAWAY Armenian Whisper fine-tune acceptance spike."""

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
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor


MODEL_ID = "ArthurYeghinyan/whisper-hy-am-asr-v2"
SAMPLE_RATE = 16_000


def read_audio(path: Path, start: float, duration: float) -> np.ndarray:
    command = [
        "ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration),
        "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-f", "f32le", "pipe:1",
    ]
    return np.frombuffer(subprocess.check_output(command), dtype=np.float32).copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--chunk", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    device = torch.device("mps")
    if not torch.backends.mps.is_available():
        raise SystemExit("MPS is not available")

    load_started = time.perf_counter()
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID, dtype=torch.float16
    ).to(device).eval()
    load_seconds = time.perf_counter() - load_started

    chunks = []
    offset = 0.0
    while offset < args.duration:
        duration = min(args.chunk, args.duration - offset)
        audio = read_audio(args.audio, offset, duration)
        inputs = processor(
            audio,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            return_attention_mask=True,
        )
        inputs = {
            key: value.to(device=device, dtype=torch.float16)
            if value.is_floating_point()
            else value.to(device)
            for key, value in inputs.items()
        }
        torch.mps.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            tokens = model.generate(**inputs, language="hy", task="transcribe")
        torch.mps.synchronize()
        elapsed = time.perf_counter() - started
        text = processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
        row = {"start_seconds": offset, "duration_seconds": duration, "text": text, "inference_seconds": elapsed}
        chunks.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        offset += duration

    output = {
        "prototype": "THROWAWAY",
        "model": MODEL_ID,
        "runtime": "Transformers/PyTorch MPS FP16",
        "machine": platform.platform(),
        "torch": torch.__version__,
        "load_seconds": load_seconds,
        "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3,
        "chunks": chunks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
