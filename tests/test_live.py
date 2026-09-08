"""Exercise opt-in paced acceptance through the public live CLI seam."""

import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not {
        "CARAVAY_REAL_MODEL_CONFIG",
        "CARAVAY_REAL_AUDIO",
        "CARAVAY_LIVE_REPORT",
        "CARAVAY_LIVE_NOTES",
    }.issubset(os.environ),
    reason="paced live acceptance and report are opt-in",
)
def test_paced_live_audio_emits_before_capture_finishes() -> None:
    """Record live latency and usefulness evidence on the reference Mac."""
    started = time.monotonic()
    producer = subprocess.Popen(
        (
            "ffmpeg",
            "-re",
            "-i",
            os.environ["CARAVAY_REAL_AUDIO"],
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "pipe:1",
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert producer.stdout is not None
    command = Path(sys.executable).with_name("caravay")
    consumer = subprocess.Popen(
        (
            command,
            "--config",
            os.environ["CARAVAY_REAL_MODEL_CONFIG"],
            "live",
            "--source",
            "hye",
            "--target",
            "eng",
            "--input-format",
            "f32le",
            "--format",
            "jsonl",
            "-",
        ),
        stdin=producer.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    producer.stdout.close()
    assert consumer.stdout is not None
    ready, _, _ = select.select((consumer.stdout,), (), (), 60)
    first = consumer.stdout.readline() if ready else ""
    early = producer.poll() is None
    output, errors = consumer.communicate(timeout=1_800)
    producer.communicate(timeout=30)
    records = tuple(json.loads(line) for line in (first + output).splitlines())
    segments = tuple(record for record in records if record["type"] == "segment")
    terminal = records[-1]
    report = {
        "time_to_first_english_seconds": time.monotonic() - started if first else None,
        "result_latency_ms": [record["latency_ms"] for record in segments],
        "maximum_backlog_frames": terminal["maximum_backlog_frames"],
        "total_wall_seconds": time.monotonic() - started,
        "operator_notes": os.environ["CARAVAY_LIVE_NOTES"],
        "stderr": errors,
    }
    Path(os.environ["CARAVAY_LIVE_REPORT"]).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifact = re.compile(r"(?<![\w#])#(?:err|er)(?![\w#])|#{8,}")
    damaged = tuple(
        record
        for record in segments
        if artifact.search(record.get("source_transcript") or "")
    )
    assert (
        consumer.returncode,
        len(segments),
        early,
        terminal["completion"],
        bool(damaged),
        all(not artifact.search(record.get("text") or "") for record in segments),
        all(record["outcome"] in ("degraded", "skipped") for record in damaged),
    ) == (3, 39, True, "clean_eof", True, True, True), (
        "paced live acceptance leaked or concealed generation artifacts"
    )
