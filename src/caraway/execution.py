"""Run the explicit composed Source Armenian speech-to-English pipeline."""

import importlib
import json
import os
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, Protocol, TextIO, TypedDict, cast

from caraway import transcription, translation
from caraway.settings import Backend, Composed, Fused, Route, Settings
from caraway.translation import Format, Outcome, ValidationError

Stage = Literal["speech_to_text", "text_to_text"]


class IssueDocument(TypedDict):
    """Define one schema-version-one composed issue."""

    stage: Stage
    code: str
    message: str


class CountsDocument(TypedDict):
    """Define schema-version-one composed segment counts."""

    total: int
    completed: int
    degraded: int
    skipped: int
    failed: int


class BackendsDocument(TypedDict):
    """Define both resolved composed capability bindings."""

    speech_to_text: Backend
    text_to_text: Backend


class SegmentDocument(TypedDict):
    """Define one schema-version-one composed segment."""

    schema_version: Literal[1]
    type: Literal["segment"]
    index: int
    outcome: Outcome
    text: str | None
    issues: list[IssueDocument]
    source_transcript: NotRequired[str]


class SummaryDocument(TypedDict):
    """Define one schema-version-one composed summary."""

    schema_version: Literal[1]
    type: Literal["summary"]
    command: Literal["run"]
    route: Literal["composed"]
    outcome: Outcome
    source_language: str
    target_language: str
    backends: BackendsDocument
    segments: CountsDocument
    error: NotRequired[IssueDocument]


@dataclass(frozen=True)
class Issue:
    """Describe one issue from either composed stage."""

    stage: Stage
    code: str
    message: str


@dataclass(frozen=True)
class Result:
    """Hold one composed segment result and its transcript artifact."""

    outcome: Outcome
    text: str
    transcript: str
    issues: tuple[Issue, ...]


class Runtime(Protocol):
    """Describe the lazily imported heavyweight composed backend module."""

    def load_speech(self, path: Path) -> object:
        """Load the speech recognition stage."""
        ...

    def transcribe(
        self, backend: object, source: str, audio: array[float]
    ) -> transcription.Result:
        """Transcribe one audio segment."""
        ...

    def load(self, path: Path) -> object:
        """Load the text translation stage."""
        ...

    def generate(self, backend: object, source: str, target: str, text: str) -> str:
        """Translate one transcript."""
        ...

    def resolve(self, generated: str) -> translation.Result:
        """Resolve one generated translation outcome."""
        ...


def runtime() -> Runtime:
    """Load the heavyweight backend after complete plan validation."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return cast(Runtime, importlib.import_module("caraway.runtime"))


def plan(
    route: str,
    fused: str,
    speech: str,
    text: str,
    configured: Route,
    source: str,
    target: str,
) -> tuple[Backend, Backend]:
    """Resolve and validate the complete language-qualified execution plan."""
    if fused and (speech or text):
        raise ValidationError("invalid_route: composed and fused bindings conflict")
    selected = route or configured.route
    if selected == "fused":
        match configured:
            case Fused(backend=backend):
                binding = fused or backend
            case Composed():
                if not fused:
                    raise ValidationError(
                        "invalid_route: fused route requires a backend"
                    )
                binding = fused
        raise ValidationError(
            f"unsupported_capability: {binding} cannot translate "
            f"{source} speech to {target}"
        )
    if fused:
        raise ValidationError("invalid_route: fused backend requires the fused route")
    recognition: str
    translator: str
    match configured:
        case Composed(
            speech_backend=recognition,
            translation_backend=translator,
        ):
            pass
        case Fused():
            recognition = Settings.backend_name
            translator = Settings.backend_name
    recognizer = transcription.capability(speech or recognition, source)
    translator = translation.capability(text or translator, source, target)
    return recognizer, translator


def issue(stage: Stage, code: str, message: str) -> Issue:
    """Build one issue without coupling composed execution to stage types."""
    return Issue(stage, code, message)


def combine(speech: transcription.Result, translated: translation.Result) -> Result:
    """Propagate the worst upstream or downstream useful outcome."""
    problems = tuple(
        issue(value.stage, value.code, value.message) for value in speech.issues
    )
    problems += tuple(
        issue(value.stage, value.code, value.message) for value in translated.issues
    )
    outcome: Outcome = (
        "degraded"
        if speech.outcome == "degraded" and translated.outcome == "completed"
        else translated.outcome
    )
    return Result(outcome, translated.text, speech.text, problems)


def skip(speech: transcription.Result) -> Result:
    """Preserve a speech-stage outcome with no downstream invocation."""
    problems = tuple(
        issue(value.stage, value.code, value.message) for value in speech.issues
    )
    return Result(speech.outcome, "", speech.text, problems)


def aggregate(results: tuple[Result, ...]) -> Outcome:
    """Combine composed segment outcomes into one command outcome."""
    if any(result.outcome == "failed" for result in results):
        return "failed"
    useful = any(result.text for result in results)
    if useful and all(result.outcome == "completed" for result in results):
        return "completed"
    return "degraded" if useful else "skipped"


def document(problem: Issue) -> IssueDocument:
    """Serialize one composed issue."""
    return {"stage": problem.stage, "code": problem.code, "message": problem.message}


def segment(result: Result, index: int) -> SegmentDocument:
    """Build one composed segment document."""
    value: SegmentDocument = {
        "schema_version": 1,
        "type": "segment",
        "index": index,
        "outcome": result.outcome,
        "text": result.text or None,
        "issues": [document(problem) for problem in result.issues],
    }
    if result.transcript:
        value["source_transcript"] = result.transcript
    return value


def counts(results: tuple[Result, ...]) -> CountsDocument:
    """Count every attempted composed segment outcome."""
    return {
        "total": len(results),
        "completed": sum(result.outcome == "completed" for result in results),
        "degraded": sum(result.outcome == "degraded" for result in results),
        "skipped": sum(result.outcome == "skipped" for result in results),
        "failed": sum(result.outcome == "failed" for result in results),
    }


def summary(
    outcome: Outcome,
    source: str,
    target: str,
    speech: Backend,
    text: Backend,
    results: tuple[Result, ...],
) -> SummaryDocument:
    """Build the terminal composed summary."""
    return {
        "schema_version": 1,
        "type": "summary",
        "command": "run",
        "route": "composed",
        "outcome": outcome,
        "source_language": source,
        "target_language": target,
        "backends": {"speech_to_text": speech, "text_to_text": text},
        "segments": counts(results),
    }


def write(stream: TextIO, result: Result, index: int, representation: Format) -> bool:
    """Write and flush one composed segment result."""
    if representation == "text":
        if result.text:
            stream.write(f"{result.text.strip()}\n")
        stream.flush()
        return True
    stream.write(
        json.dumps(segment(result, index), ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )
    stream.flush()
    return True


def finish(
    stream: TextIO,
    results: tuple[Result, ...],
    representation: Format,
    source: str,
    target: str,
    speech: Backend,
    text: Backend,
) -> bool:
    """Write the terminal composed summary when selected."""
    if representation == "text":
        return True
    outcome = aggregate(results)
    terminal = summary(outcome, source, target, speech, text, results)
    if outcome == "failed":
        terminal["error"] = document(results[-1].issues[-1])
    stream.write(json.dumps(terminal, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True


def fail(
    stream: TextIO,
    representation: Format,
    source: str,
    target: str,
    speech: Backend,
    text: Backend,
    problem: Issue,
) -> bool:
    """Write a failed zero-attempt summary after model loading fails."""
    if representation == "text":
        return True
    terminal = summary("failed", source, target, speech, text, ())
    terminal["error"] = document(problem)
    stream.write(json.dumps(terminal, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True
