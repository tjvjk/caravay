"""Translate a bounded live raw PCM stream through the composed pipeline."""

import json
import math
import os
import queue
import threading
import time
from array import array
from collections.abc import Iterator
from dataclasses import dataclass
from typing import BinaryIO, Final, Literal, TextIO, TypedDict

from caravay import execution
from caravay.translation import Format, Outcome

RATE: Final = 16_000
FRAME: Final = 320
SILENCE_MS: Final = 600
MAX_SECONDS: Final = 8.0
MIN_MS: Final = 200
BUFFER_SECONDS: Final = 30.0
THRESHOLD: Final = 0.01
Completion = Literal["clean_eof", "interruption", "overload", "failure"]
Phase = Literal["listening", "transcribing"]


class LiveDocument(TypedDict):
    """Define one schema-version-one live segment record."""

    schema_version: Literal[1]
    type: Literal["segment"]
    mode: Literal["live"]
    index: int
    outcome: Outcome
    source_start_sample: int
    source_end_sample: int
    source_transcript: str | None
    text: str | None
    issues: list[execution.IssueDocument]
    latency_ms: int


@dataclass(frozen=True)
class Options:
    """Hold validated live timing and buffering options."""

    silence: int
    maximum: int
    minimum: int
    capacity: int


@dataclass(frozen=True)
class Frame:
    """Hold one sequential PCM frame and its sample position."""

    start: int
    samples: array[float]
    received: float


@dataclass(frozen=True)
class Segment:
    """Hold one finalized speech candidate and its source positions."""

    start: int
    end: int
    samples: array[float]
    closed: float


@dataclass(frozen=True)
class Terminal:
    """Hold the observable termination reason and maximum frame backlog."""

    completion: Completion
    backlog: int


@dataclass(frozen=True)
class Capture:
    """Hold the independently draining bounded PCM input boundary."""

    frames: queue.Queue[Frame]
    overload: threading.Event
    failed: threading.Event
    eof: threading.Event
    stop: threading.Event
    errors: list[str]
    peak: list[int]
    reader: threading.Thread


@dataclass(frozen=True)
class Presentation:
    """Hold synchronized transient terminal presentation state."""

    stream: TextIO
    enabled: bool
    started: float
    phase: list[Phase]
    lock: threading.Lock
    stopped: threading.Event
    renderer: threading.Thread


def label(phase: Phase, started: float) -> str:
    """Describe one live phase within the available terminal width."""
    if phase == "transcribing":
        return "Transcribing..."
    elapsed = max(0, int(time.monotonic() - started))
    return f"Listening... {elapsed // 60:02d}:{elapsed % 60:02d}"


def render(stream: TextIO, phase: Phase, started: float) -> bool:
    """Replace the current transient line with a width-safe phase label."""
    try:
        width = max(1, os.get_terminal_size(stream.fileno()).columns)
    except (AttributeError, OSError):
        width = 80
    stream.write("\r\033[2K" + label(phase, started)[:width])
    stream.flush()
    return True


def refresh(
    stream: TextIO,
    started: float,
    phase: list[Phase],
    lock: threading.Lock,
    stopped: threading.Event,
) -> bool:
    """Refresh elapsed listening time at a restrained cadence."""
    while not stopped.wait(1):
        with lock:
            render(stream, phase[0], started)
    return True


def present(stream: TextIO, enabled: bool) -> Presentation:
    """Start transient live presentation when diagnostics support it."""
    started = time.monotonic()
    phase: list[Phase] = ["listening"]
    lock = threading.Lock()
    stopped = threading.Event()
    renderer = threading.Thread(
        target=refresh,
        args=(stream, started, phase, lock, stopped),
        daemon=True,
    )
    result = Presentation(stream, enabled, started, phase, lock, stopped, renderer)
    if enabled:
        render(stream, phase[0], started)
        renderer.start()
    return result


def show(presentation: Presentation, phase: Phase) -> bool:
    """Change and immediately display the current live phase."""
    if not presentation.enabled:
        return False
    with presentation.lock:
        presentation.phase[0] = phase
        render(presentation.stream, phase, presentation.started)
    return True


def clear(presentation: Presentation) -> bool:
    """Clear transient presentation before durable output."""
    if not presentation.enabled:
        return False
    presentation.stream.write("\r\033[2K")
    presentation.stream.flush()
    return True


def diagnose(presentation: Presentation, message: str) -> bool:
    """Write one durable diagnostic without corrupting transient status."""
    with presentation.lock:
        clear(presentation)
        print(message, file=presentation.stream, flush=True)
        if presentation.enabled:
            render(presentation.stream, presentation.phase[0], presentation.started)
    return True


def dismiss(presentation: Presentation) -> bool:
    """Stop and remove transient live presentation."""
    if not presentation.enabled:
        return False
    presentation.stopped.set()
    presentation.renderer.join(timeout=1)
    with presentation.lock:
        clear(presentation)
    return True


def options(
    silence: int = SILENCE_MS,
    maximum: float = MAX_SECONDS,
    minimum: int = MIN_MS,
    capacity: float = BUFFER_SECONDS,
) -> Options:
    """Convert positive public durations into sample and frame bounds."""
    if silence <= 0 or maximum <= 0 or minimum <= 0 or capacity <= 0:
        raise ValueError("invalid_live_option: live durations must be positive")
    if minimum > maximum * 1_000:
        raise ValueError("invalid_live_option: minimum duration exceeds maximum")
    return Options(
        round(RATE * silence / 1_000),
        round(RATE * maximum),
        round(RATE * minimum / 1_000),
        max(1, math.ceil(RATE * capacity / FRAME)),
    )


def speech(samples: array[float]) -> bool:
    """Classify one short normalized Float32 frame by signal energy."""
    return bool(samples) and max(abs(value) for value in samples) >= THRESHOLD


def read(
    stream: BinaryIO,
    frames: queue.Queue[Frame],
    overload: threading.Event,
    failed: threading.Event,
    eof: threading.Event,
    stop: threading.Event,
    errors: list[str],
    peak: list[int],
) -> bool:
    """Drain fragmented raw PCM input into a bounded frame queue."""
    remainder = b""
    position = 0
    try:
        while payload := stream.read(FRAME * 4):
            if stop.is_set():
                return False
            remainder += payload
            size = len(remainder) // 4 * 4
            values = array("f")
            values.frombytes(remainder[:size])
            remainder = remainder[size:]
            while len(values) >= FRAME:
                frame = Frame(position, values[:FRAME], time.monotonic())
                try:
                    frames.put_nowait(frame)
                except queue.Full:
                    overload.set()
                    return False
                position += FRAME
                del values[:FRAME]
                peak[0] = max(peak[0], frames.qsize())
            if values:
                remainder = values.tobytes() + remainder
        if remainder:
            if len(remainder) % 4:
                failed.set()
                return False
            values = array("f")
            values.frombytes(remainder)
            try:
                frames.put_nowait(Frame(position, values, time.monotonic()))
            except queue.Full:
                overload.set()
                return False
        return True
    except (OSError, ValueError) as error:
        errors.append(str(error))
        failed.set()
        return False
    finally:
        eof.set()


def capture(source: BinaryIO, settings: Options) -> Capture:
    """Start draining live PCM before heavyweight model loading begins."""
    frames: queue.Queue[Frame] = queue.Queue(settings.capacity)
    overload = threading.Event()
    failed = threading.Event()
    eof = threading.Event()
    stop = threading.Event()
    errors: list[str] = []
    peak = [0]
    reader = threading.Thread(
        target=read,
        args=(source, frames, overload, failed, eof, stop, errors, peak),
        daemon=True,
    )
    reader.start()
    return Capture(frames, overload, failed, eof, stop, errors, peak, reader)


def settle(capture: Capture, source: BinaryIO) -> bool:
    """Stop capture and wait a bounded interval for its reader resource."""
    capture.stop.set()
    if capture.reader.is_alive():
        source.close()
    capture.reader.join(timeout=1)
    return not capture.reader.is_alive()


def close(
    start: int,
    samples: array[float],
    silence: int,
    ended: float,
    pending: Segment | None,
) -> tuple[Segment, Segment | None]:
    """Finalize a candidate while carrying a deferred short fragment forward."""
    end = start + len(samples) - silence
    audio = samples[:-silence] if silence else samples
    segment = Segment(start, end, audio, ended)
    if pending is None:
        return segment, None
    combined = array("f", pending.samples)
    gap = max(0, segment.start - pending.end)
    combined.extend(array("f", (0.0 for _ in range(gap))))
    combined.extend(segment.samples)
    return Segment(pending.start, segment.end, combined, segment.closed), None


def terminal(
    stream: TextIO,
    representation: Format,
    plan: execution.Plan,
    results: tuple[execution.Result, ...],
    state: Terminal,
) -> bool:
    """Write and flush the terminal live JSONL record when selected."""
    if representation == "text":
        return True
    outcome: Outcome = (
        execution.aggregate(results) if state.completion == "clean_eof" else "failed"
    )
    document: dict[str, object] = {
        "schema_version": 1,
        "type": "summary",
        "command": "live",
        "mode": "live",
        "route": "composed",
        "outcome": outcome,
        "completion": state.completion,
        "source_language": plan.source,
        "target_language": plan.target,
        "backends": {"speech_to_text": plan.speech, "text_to_text": plan.text},
        "segments": execution.counts(results),
        "maximum_backlog_frames": state.backlog,
    }
    stream.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()
    return True


def write(
    stream: TextIO,
    result: execution.Result,
    segment: Segment,
    index: int,
    representation: Format,
) -> bool:
    """Write and immediately flush one ordered live result."""
    if representation == "text":
        return execution.write(stream, result, index, representation)
    document: LiveDocument = {
        "schema_version": 1,
        "type": "segment",
        "mode": "live",
        "index": index,
        "outcome": result.outcome,
        "source_start_sample": segment.start,
        "source_end_sample": segment.end,
        "source_transcript": result.transcript or None,
        "text": result.text or None,
        "issues": [execution.document(problem) for problem in result.issues],
        "latency_ms": max(0, round((time.monotonic() - segment.closed) * 1_000)),
    }
    stream.write(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()
    return True


def segments(
    frames: queue.Queue[Frame],
    overload: threading.Event,
    failed: threading.Event,
    eof: threading.Event,
    settings: Options,
) -> Iterator[Segment | Terminal]:
    """Yield finalized candidates while inference runs between queue reads."""
    candidate = array("f")
    start = 0
    quiet = 0
    ended = time.monotonic()
    pending: Segment | None = None
    while True:
        if overload.is_set():
            yield Terminal("overload", 0)
            return
        if failed.is_set():
            yield Terminal("failure", 0)
            return
        try:
            frame = frames.get(timeout=0.05)
        except queue.Empty:
            if not eof.is_set():
                continue
            if candidate:
                final, pending = close(start, candidate, 0, ended, pending)
                pending = final if len(final.samples) < settings.minimum else None
                if pending is None:
                    yield final
            if pending is not None:
                yield pending
            yield Terminal("clean_eof", 0)
            return
        voiced = speech(frame.samples)
        if not candidate and not voiced:
            continue
        if not candidate:
            start = frame.start
        candidate.extend(frame.samples)
        if voiced:
            ended = frame.received
        quiet = 0 if voiced else quiet + len(frame.samples)
        if quiet < settings.silence and len(candidate) < settings.maximum:
            continue
        final, pending = close(start, candidate, quiet, ended, pending)
        candidate = array("f")
        quiet = 0
        if len(final.samples) < settings.minimum:
            pending = final
            continue
        yield final


def attempt(
    segment: Segment,
    prepared: execution.Prepared,
    loaded: execution.Loaded,
    output: TextIO,
    presentation: Presentation,
    representation: Format,
    index: int,
    verbose: bool,
) -> execution.Result:
    """Run and emit one finalized live speech segment."""
    show(presentation, "transcribing")
    attempted = execution.attempt(segment.samples, prepared, loaded)
    if attempted.diagnostic:
        diagnose(presentation, attempted.diagnostic)
    if attempted.result.outcome in ("degraded", "skipped"):
        for problem in attempted.result.issues:
            if problem.code in ("generation_artifact", "repetition"):
                if verbose:
                    message = (
                        "cleanup: omitted non-speech model output"
                        if problem.code == "generation_artifact"
                        else "cleanup: trimmed repeated model output"
                    )
                    diagnose(presentation, message)
            else:
                diagnose(presentation, f"{problem.code}: {problem.message}")
    with presentation.lock:
        clear(presentation)
        write(output, attempted.result, segment, index, representation)
        presentation.phase[0] = "listening"
        if presentation.enabled:
            render(
                presentation.stream,
                presentation.phase[0],
                presentation.started,
            )
    return attempted.result


def execute(
    capture: Capture,
    source: BinaryIO,
    output: TextIO,
    presentation: Presentation,
    prepared: execution.Prepared,
    loaded: execution.Loaded,
    settings: Options,
    representation: Format,
    verbose: bool,
) -> tuple[tuple[execution.Result, ...], Terminal]:
    """Drain, segment, translate, and emit one bounded live PCM stream."""
    results: list[execution.Result] = []
    state = Terminal("clean_eof", 0)
    try:
        for value in segments(
            capture.frames,
            capture.overload,
            capture.failed,
            capture.eof,
            settings,
        ):
            match value:
                case Terminal():
                    state = Terminal(value.completion, capture.peak[0])
                    break
                case Segment():
                    result = attempt(
                        value,
                        prepared,
                        loaded,
                        output,
                        presentation,
                        representation,
                        len(results),
                        verbose,
                    )
            results.append(result)
            if result.outcome == "failed":
                state = Terminal("failure", capture.peak[0])
                break
    except KeyboardInterrupt:
        state = Terminal("interruption", capture.peak[0])
    if state.completion == "overload":
        diagnose(
            presentation,
            f"overload: live backlog exceeded {settings.capacity} frames",
        )
    if capture.failed.is_set():
        detail = capture.errors[-1] if capture.errors else "unknown input error"
        diagnose(presentation, f"invalid_input: live PCM input pipe failed: {detail}")
    settle(capture, source)
    return tuple(results), state
