#!/usr/bin/env python3
"""THROWAWAY Armenian STT acceptance spike using MLX Whisper."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import resource
import time
from pathlib import Path

import mlx_whisper


MODEL_ID = "mlx-community/whisper-large-v3-turbo"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--no-condition-on-previous-text", action="store_true")
    parser.add_argument("--no-word-timestamps", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    result = mlx_whisper.transcribe(
        str(args.audio),
        path_or_hf_repo=args.model,
        language="hy",
        task="transcribe",
        word_timestamps=not args.no_word_timestamps,
        condition_on_previous_text=not args.no_condition_on_previous_text,
        verbose=False,
    )
    elapsed = time.perf_counter() - started

    output = {
        "prototype": "THROWAWAY",
        "model": args.model,
        "runtime": "mlx-whisper",
        "mlx_whisper": importlib.metadata.version("mlx-whisper"),
        "machine": platform.platform(),
        "elapsed_seconds_including_model_load": elapsed,
        "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3,
        "language": result.get("language"),
        "condition_on_previous_text": not args.no_condition_on_previous_text,
        "word_timestamps": not args.no_word_timestamps,
        "text": result["text"],
        "segments": result["segments"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in output if key != "segments"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
