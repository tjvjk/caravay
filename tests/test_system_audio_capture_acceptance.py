"""Exercise opt-in ScreenCaptureKit-to-live translation on the reference Mac."""

import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REQUIRED = {
    "CARAWAY_REAL_MODEL_CONFIG",
    "CARAWAY_REAL_AUDIO",
    "CARAWAY_CAPTURE_REPORT",
    "CARAWAY_CAPTURE_NOTES",
    "CARAWAY_OUTPUT_DEVICE",
    "CARAWAY_CAPTURE_PERMISSION_STATE",
}


@pytest.mark.timeout(1_800)
@pytest.mark.skipif(
    not REQUIRED.issubset(os.environ),
    reason="real system-audio capture acceptance is opt-in",
)
def test_system_audio_reaches_live_translation_before_playback_finishes() -> None:
    """Record end-to-end reference-Mac evidence while playing a normal audio app."""
    root = Path(__file__).parents[1]
    package = root / "native" / "SystemAudioCapture"
    subprocess.run(
        ("swift", "build", "-c", "release", "--package-path", str(package)),
        check=True,
    )
    producer = subprocess.Popen(
        package / ".build" / "release" / "caraway-capture",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert producer.stdout is not None
    assert producer.stderr is not None
    consumer = subprocess.Popen(
        (
            str(Path(sys.executable).with_name("caraway")),
            "--config",
            os.environ["CARAWAY_REAL_MODEL_CONFIG"],
            "live",
            "--input-format",
            "f32le",
            "--format",
            "jsonl",
            "-",
        ),
        stdin=producer.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=root,
    )
    assert consumer.stdout is not None
    consumer_output = consumer.stdout
    translated: list[tuple[float, bytes]] = []

    def collect() -> None:
        for line in consumer_output:
            translated.append((time.monotonic(), line))

    output_thread = threading.Thread(target=collect)
    producer.stdout.close()
    output_thread.start()
    capture_started = time.monotonic()
    initial_diagnostic = producer.stderr.readline().decode()
    assert initial_diagnostic.startswith("capturing system audio")
    playback = subprocess.Popen(("afplay", os.environ["CARAWAY_REAL_AUDIO"]))
    playback_started = time.monotonic()
    playback.wait(timeout=600)
    playback_finished = time.monotonic()
    producer.send_signal(signal.SIGINT)
    producer_returncode = producer.wait(timeout=30)
    consumer_returncode = consumer.wait(timeout=1_200)
    output_thread.join(timeout=30)
    producer_diagnostics = initial_diagnostic + producer.stderr.read().decode()
    consumer_diagnostics = consumer.stderr.read().decode() if consumer.stderr else ""
    records = [json.loads(line) for _, line in translated]
    segments = [record for record in records if record["type"] == "segment"]
    terminal = records[-1]
    peak_marker = "capture_queue_peak="
    peak = int(producer_diagnostics.rsplit(peak_marker, 1)[1].split()[0])
    first_pcm_marker = "first_pcm: uptime_seconds="
    first_pcm = float(producer_diagnostics.split(first_pcm_marker, 1)[1].split()[0])
    early_records = [
        json.loads(line)
        for timestamp, line in translated
        if timestamp < playback_finished
    ]
    early_segments = [record for record in early_records if record["type"] == "segment"]
    report = {
        "macos_version": platform.mac_ver()[0],
        "output_audio_device": os.environ["CARAWAY_OUTPUT_DEVICE"],
        "permission_state": os.environ["CARAWAY_CAPTURE_PERMISSION_STATE"],
        "time_to_first_accepted_pcm_seconds": first_pcm - playback_started,
        "capture_queue_peak": peak,
        "producer_termination": "interruption",
        "producer_exit_status": producer_returncode,
        "live_exit_status": consumer_returncode,
        "live_result_latency_ms": [record["latency_ms"] for record in segments],
        "live_maximum_backlog_frames": terminal["maximum_backlog_frames"],
        "operator_notes": os.environ["CARAWAY_CAPTURE_NOTES"],
        "producer_stderr": producer_diagnostics,
        "consumer_stderr": consumer_diagnostics,
        "capture_start_to_playback_seconds": playback_started - capture_started,
    }
    Path(os.environ["CARAWAY_CAPTURE_REPORT"]).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assert any(record.get("text") for record in early_segments)
    assert any(record.get("text") for record in segments)
    assert producer_returncode == 130
