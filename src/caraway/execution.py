"""Run the explicit composed speech-to-text translation pipeline."""

from __future__ import annotations

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


@dataclass(frozen=True)
class Plan:
    """Hold the complete resolved composed execution plan."""

    source: str
    target: str
    speech: Backend
    text: Backend


@dataclass(frozen=True)
class Request:
    """Hold unresolved command input and configuration."""

    route: str
    fused: str
    speech: str
    text: str
    configured: Route
    source: str
    target: str
    audio: str
    root: Path
    verbose: bool
    hashes: int


@dataclass(frozen=True)
class Prepared:
    """Hold the validated plan, snapshot, and decoded input."""

    plan: Plan
    path: Path
    segments: tuple[array[float], ...]
    hashes: int


@dataclass(frozen=True)
class Loaded:
    """Hold both loaded stage implementations and their runtime."""

    backend: Runtime
    recognizer: object
    translator: object


@dataclass(frozen=True)
class Attempt:
    """Hold one segment result and any fatal diagnostic."""

    result: Result
    diagnostic: str


class Runtime(Protocol):
    """Describe the lazily imported heavyweight composed backend module."""

    def recognize(self, path: Path) -> object:
        """Load the speech recognition stage."""
        ...

    def transcribe(
        self,
        backend: object,
        source: str,
        audio: array[float],
        hashes: int,
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


def prepare(request: Request) -> Prepared:
    """Validate the complete request before loading either model."""
    source = translation.language(request.source)
    target = translation.language(request.target)
    audio = transcription.read(request.audio)
    resolved = plan(
        request.route,
        request.fused,
        request.speech,
        request.text,
        request.configured,
        source,
        target,
    )
    path = transcription.validate(request.root, request.verbose)
    segments = transcription.decode(audio)
    return Prepared(resolved, path, segments, request.hashes)


def load(prepared: Prepared, backend: Runtime) -> Loaded:
    """Load both implementations required by a validated plan."""
    recognizer = backend.recognize(prepared.path)
    translator = backend.load(prepared.path)
    return Loaded(backend, recognizer, translator)


def plan(
    route: str,
    fused: str,
    speech: str,
    text: str,
    configured: Route,
    source: str,
    target: str,
) -> Plan:
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
    return Plan(source, target, recognizer, translator)


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
    return Result(outcome, translated.text, speech.transcript, problems)


def skip(speech: transcription.Result) -> Result:
    """Preserve a speech-stage outcome with no downstream invocation."""
    problems = tuple(
        issue(value.stage, value.code, value.message) for value in speech.issues
    )
    return Result(speech.outcome, "", speech.transcript, problems)


def attempt(audio: array[float], prepared: Prepared, loaded: Loaded) -> Attempt:
    """Process one independently recoverable composed segment."""
    try:
        recognized = loaded.backend.transcribe(
            loaded.recognizer, prepared.plan.source, audio, prepared.hashes
        )
    except Exception as error:
        problem = Issue(
            "speech_to_text", "transcription_failed", "speech transcription failed"
        )
        diagnostic = f"transcription_failed: speech transcription failed: {error}"
        return Attempt(Result("failed", "", "", (problem,)), diagnostic)
    if not recognized.text:
        return Attempt(skip(recognized), "")
    try:
        generated = loaded.backend.generate(
            loaded.translator,
            prepared.plan.source,
            prepared.plan.target,
            recognized.text,
        )
        result = combine(recognized, loaded.backend.resolve(generated))
        return Attempt(result, "")
    except Exception as error:
        problem = Issue("text_to_text", "translation_failed", "text translation failed")
        diagnostic = f"translation_failed: text translation failed: {error}"
        return Attempt(
            Result("failed", "", recognized.transcript, (problem,)), diagnostic
        )


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
    plan: Plan,
    results: tuple[Result, ...],
) -> SummaryDocument:
    """Build the terminal composed summary."""
    return {
        "schema_version": 1,
        "type": "summary",
        "command": "run",
        "route": "composed",
        "outcome": outcome,
        "source_language": plan.source,
        "target_language": plan.target,
        "backends": {"speech_to_text": plan.speech, "text_to_text": plan.text},
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


def execute(
    prepared: Prepared,
    loaded: Loaded,
    output: TextIO,
    diagnostics: TextIO,
    representation: Format,
) -> tuple[Result, ...]:
    """Execute and stream the prepared segments until completion or failure."""
    results: list[Result] = []
    for index, audio in enumerate(prepared.segments):
        attempted = attempt(audio, prepared, loaded)
        if attempted.diagnostic:
            print(attempted.diagnostic, file=diagnostics)
        results.append(attempted.result)
        write(output, attempted.result, index, representation)
        if attempted.result.outcome in ("degraded", "skipped"):
            for problem in attempted.result.issues:
                print(f"{problem.code}: {problem.message}", file=diagnostics)
        if attempted.result.outcome == "failed":
            break
    return tuple(results)


def finish(
    stream: TextIO,
    results: tuple[Result, ...],
    representation: Format,
    plan: Plan,
) -> bool:
    """Write the terminal composed summary when selected."""
    if representation == "text":
        return True
    outcome = aggregate(results)
    terminal = summary(outcome, plan, results)
    if outcome == "failed":
        terminal["error"] = document(results[-1].issues[-1])
    stream.write(json.dumps(terminal, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True


def fail(
    stream: TextIO,
    representation: Format,
    plan: Plan,
    problem: Issue,
) -> bool:
    """Write a failed zero-attempt summary after model loading fails."""
    if representation == "text":
        return True
    terminal = summary("failed", plan, ())
    terminal["error"] = document(problem)
    stream.write(json.dumps(terminal, ensure_ascii=False, separators=(",", ":")) + "\n")
    return True
