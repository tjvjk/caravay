"""Exercise the native system-audio producer through its process boundary."""

import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[1] / "native" / "SystemAudioCapture"
pytestmark = pytest.mark.timeout(60)


@pytest.fixture(scope="session")
def capture_command() -> Path:
    """Build the debug executable that exposes the controlled capture adapter."""
    subprocess.run(
        ("swift", "build", "--package-path", str(PACKAGE)),
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ("swift", "build", "--package-path", str(PACKAGE), "--show-bin-path"),
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()) / "caraway-capture"


def invoke(
    command: Path,
    events: list[dict[str, object]],
    extra_environment: dict[str, str] | None = None,
    *arguments: str,
) -> subprocess.CompletedProcess[bytes]:
    """Run one controlled capture script without ScreenCaptureKit permission."""
    environment = os.environ.copy()
    environment["CARAWAY_CAPTURE_TEST_EVENTS"] = json.dumps(events)
    environment.update(extra_environment or {})
    return subprocess.run(
        (command, *arguments), env=environment, capture_output=True, check=False
    )


def test_success_writes_only_mono_float32_pcm_to_stdout(
    capture_command: Path,
) -> None:
    """Mix native stereo samples while keeping diagnostics off the PCM stream."""
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 2,
                "samples": [0.25, 0.75, -0.5, 0.5],
            },
            {"type": "eof"},
        ],
    )

    assert result.returncode == 0
    assert struct.unpack("<2f", result.stdout) == pytest.approx((0.5, 0.0))
    assert result.stderr == b"capturing system audio; press Ctrl-C to stop\n"


def test_success_resamples_successive_native_buffers_in_order(
    capture_command: Path,
) -> None:
    """Convert the discovered rate without duplicating or reordering buffers."""
    first = [0.25] * 3_200
    second = [0.75] * 3_200
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 32_000,
                "channels": 1,
                "samples": first,
            },
            {
                "type": "audio",
                "sample_rate": 32_000,
                "channels": 1,
                "samples": second,
            },
            {"type": "eof"},
        ],
    )

    assert result.returncode == 0
    converted = struct.unpack(f"<{len(result.stdout) // 4}f", result.stdout)
    assert len(converted) == 3_200
    assert converted[100:1_500] == pytest.approx([0.25] * 1_400, abs=0.01)
    assert converted[1_700:3_100] == pytest.approx([0.75] * 1_400, abs=0.01)


def test_permission_denial_leaves_stdout_empty(capture_command: Path) -> None:
    """Guide the user to the macOS permission without contaminating PCM."""
    result = invoke(capture_command, [{"type": "permission_denied"}])

    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == (
        b"permission_denied: allow Screen & System Audio Recording for "
        b"caraway-capture in System Settings > Privacy & Security, then retry\n"
    )


def test_full_capture_queue_is_fatal_instead_of_dropping(
    capture_command: Path,
) -> None:
    """Fail explicitly when stdout backpressure exhausts the bounded queue."""
    audio = {
        "type": "audio",
        "sample_rate": 16_000,
        "channels": 1,
        "samples": [0.25] * 320,
    }
    result = invoke(
        capture_command,
        [audio] * 10 + [{"type": "eof"}],
        {
            "CARAWAY_CAPTURE_TEST_QUEUE_CAPACITY": "1",
            "CARAWAY_CAPTURE_TEST_WRITE_DELAY_MS": "200",
        },
    )

    assert result.returncode == 1
    assert result.stderr.endswith(
        b"overload: stdout could not keep up with captured audio\n"
    )


def test_stream_failure_drains_accepted_pcm_then_fails(capture_command: Path) -> None:
    """Preserve accepted ordering and report a ScreenCaptureKit stream failure."""
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.5, -0.5],
            },
            {"type": "stream_failure"},
        ],
    )

    assert result.returncode == 1
    assert struct.unpack("<2f", result.stdout) == pytest.approx((0.5, -0.5))
    assert result.stderr.endswith(
        b"stream_failed: system audio capture stopped unexpectedly\n"
    )


def test_broken_downstream_pipe_stops_without_pcm_diagnostic(
    capture_command: Path,
) -> None:
    """Turn EPIPE into a controlled failure written only to stderr."""
    event = {
        "type": "audio",
        "sample_rate": 16_000,
        "channels": 1,
        "samples": [0.5] * 8_000,
    }
    environment = os.environ.copy()
    environment["CARAWAY_CAPTURE_TEST_EVENTS"] = json.dumps([event] * 8)
    process = subprocess.Popen(
        capture_command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdout.close()
    diagnostics = process.stderr.read()
    returncode = process.wait(timeout=10)

    assert returncode == 1
    assert diagnostics.endswith(b"broken_pipe: downstream consumer closed the pipe\n")


def test_interruption_drains_accepted_pcm_and_exits_130(capture_command: Path) -> None:
    """Represent Ctrl-C as an orderly drain with the conventional exit code."""
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.5, -0.5],
            },
            {"type": "interruption"},
        ],
    )

    assert result.returncode == 130
    assert struct.unpack("<2f", result.stdout) == pytest.approx((0.5, -0.5))
    assert result.stderr == b"capturing system audio; press Ctrl-C to stop\n"


def test_verbose_capture_retains_measurement_diagnostics(
    capture_command: Path,
) -> None:
    """Expose native termination detail only through explicit diagnostics."""
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.5, -0.5],
            },
            {"type": "interruption"},
        ],
        None,
        "--verbose",
    )
    assert (
        result.returncode,
        b"capture_queue_peak=" in result.stderr,
        result.stderr.endswith(b"interrupted: capture stopped by SIGINT\n"),
    ) == (130, True, True), "verbose capture hid acceptance diagnostics"


def test_fragmented_output_write_failure_is_reported(capture_command: Path) -> None:
    """Retry short writes and surface a later controlled output failure."""
    result = invoke(
        capture_command,
        [
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.25, 0.5, 0.75, 1.0],
            },
            {"type": "eof"},
        ],
        {
            "CARAWAY_CAPTURE_TEST_MAX_WRITE_BYTES": "3",
            "CARAWAY_CAPTURE_TEST_FAIL_AFTER_WRITES": "2",
        },
    )

    assert result.returncode == 1
    assert len(result.stdout) == 6
    assert result.stderr.endswith(
        b"output_failed: PCM could not be written to stdout\n"
    )


def test_eof_rejects_later_scripted_audio(capture_command: Path) -> None:
    """Close the ordered input at EOF instead of accepting later buffers."""
    result = invoke(
        capture_command,
        [
            {"type": "eof"},
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.75],
            },
        ],
    )

    assert result.returncode == 0
    assert result.stdout == b""


def test_silence_does_not_fabricate_keepalive_samples(capture_command: Path) -> None:
    """Remain alive through silence and resume with only captured audio."""
    result = invoke(
        capture_command,
        [
            {"type": "silence"},
            {
                "type": "audio",
                "sample_rate": 16_000,
                "channels": 1,
                "samples": [0.75],
            },
            {"type": "eof"},
        ],
    )

    assert result.returncode == 0
    assert struct.unpack("<f", result.stdout) == pytest.approx((0.75,))


def test_unavailable_capture_content_is_stable(capture_command: Path) -> None:
    """Fail without stdout when ScreenCaptureKit cannot supply a display."""
    result = invoke(capture_command, [{"type": "content_unavailable"}])

    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == (
        b"capture_unavailable: ScreenCaptureKit found no display to capture\n"
    )
