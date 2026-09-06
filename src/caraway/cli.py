"""Command-line entry point for Caraway."""

import argparse
import io
import sys
from enum import Enum, auto
from pathlib import Path
from typing import cast

from caraway import execution, live, transcription
from caraway.models import DownloadError, DownloadLockError, download, inspect
from caraway.settings import InvalidConfigError, Settings, load
from caraway.translation import (
    FORMAT,
    Issue,
    Result,
    ValidationError,
    capability,
    emit,
    empty,
    language,
    translate,
    validate,
)


class Input(Enum):
    """Distinguish omitted input from every possible file operand."""

    STDIN = auto()


def parser() -> argparse.ArgumentParser:
    """Build the development command parser."""
    result = argparse.ArgumentParser(prog="caraway")
    result.add_argument("--config", type=Path)
    result.add_argument("--quiet", action="store_true")
    commands = result.add_subparsers(dest="command", required=True)
    models = commands.add_parser("models")
    actions = models.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
    actions.add_parser("download")
    translation = commands.add_parser("translate")
    translation.add_argument("text", nargs="?", default=Input.STDIN)
    translation.add_argument("--source", default="hye")
    translation.add_argument("--target", default="eng")
    translation.add_argument("--backend")
    translation.add_argument("--format", choices=FORMAT, default="text")
    translation.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    translation.add_argument("--verbose", action="store_true")
    speech = commands.add_parser("transcribe")
    speech.add_argument("audio")
    speech.add_argument("--source", default="hye")
    speech.add_argument("--backend")
    speech.add_argument("--format", choices=FORMAT, default="text")
    speech.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    speech.add_argument("--verbose", action="store_true")
    composed = commands.add_parser("run")
    composed.add_argument("audio")
    composed.add_argument("--source", default="hye")
    composed.add_argument("--target", default="eng")
    composed.add_argument("--route", choices=("composed", "fused"))
    composed.add_argument("--speech-backend", dest="speech", default="")
    composed.add_argument("--translation-backend", dest="translation", default="")
    composed.add_argument("--backend", dest="fused", default="")
    composed.add_argument("--format", choices=FORMAT, default="text")
    composed.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    composed.add_argument("--verbose", action="store_true")
    streaming = commands.add_parser("live")
    streaming.add_argument("input")
    streaming.add_argument("--input-format", required=True, choices=("f32le",))
    streaming.add_argument("--source", default="hye")
    streaming.add_argument("--target", default="eng")
    streaming.add_argument("--speech-backend", dest="speech", default="")
    streaming.add_argument("--translation-backend", dest="translation", default="")
    streaming.add_argument("--format", choices=FORMAT, default="text")
    streaming.add_argument("--silence-ms", type=int, default=live.SILENCE_MS)
    streaming.add_argument(
        "--max-segment-seconds", type=float, default=live.MAX_SECONDS
    )
    streaming.add_argument("--min-segment-ms", type=int, default=live.MIN_MS)
    streaming.add_argument("--buffer-seconds", type=float, default=live.BUFFER_SECONDS)
    streaming.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
    streaming.add_argument("--verbose", action="store_true")
    return result


def read(value: str | Input) -> str:
    """Read one UTF-8 text operand or standard input."""
    try:
        if value is Input.STDIN:
            if sys.stdin.isatty():
                raise ValidationError(
                    "invalid_input: interactive stdin requires an operand or -"
                )
            return sys.stdin.read()
        match value:
            case "-":
                return sys.stdin.read()
            case str() as operand:
                path = Path(operand)
            case _:
                raise ValidationError("invalid_input: text operand is invalid")
        if not path.is_file():
            raise ValidationError(
                f"invalid_input: {path} is not a readable regular file"
            )
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValidationError(
            "invalid_input: input is not readable UTF-8 text"
        ) from error


def process(arguments: argparse.Namespace, config: Settings) -> int:
    """Validate and execute one offline text translation."""
    try:
        source = language(arguments.source)
        target = language(arguments.target)
        text = read(arguments.text)
        backend = capability(
            arguments.backend or config.commands.translate.backend, source, target
        )
        if not text:
            empty(sys.stdout, arguments.format, source, target, backend)
            return 4
        path = validate(config.cache_dir, arguments.verbose)
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 2
    try:
        progress = not arguments.quiet and sys.stderr.isatty()
        if progress:
            print("Loading translation model", file=sys.stderr)
        result = translate(path, source, target, text)
        if progress:
            print(file=sys.stderr)
    except Exception as error:
        print(f"translation_failed: text translation failed: {error}", file=sys.stderr)
        result = Result(
            "failed",
            "",
            (
                Issue(
                    "text_to_text",
                    "translation_failed",
                    "text translation failed",
                ),
            ),
        )
    if result.outcome in ("degraded", "skipped"):
        for problem in result.issues:
            print(f"{problem.code}: {problem.message}", file=sys.stderr)
    emit(sys.stdout, result, arguments.format, source, target, backend)
    return {"completed": 0, "failed": 1, "degraded": 3, "skipped": 4}[result.outcome]


def transcribe(arguments: argparse.Namespace, config: Settings) -> int:
    """Validate and execute one offline audio transcription."""
    try:
        source = language(arguments.source)
        audio = transcription.read(arguments.audio)
        backend = transcription.capability(
            arguments.backend or config.commands.transcribe.backend, source
        )
        path = transcription.validate(config.cache_dir, arguments.verbose)
        segments = transcription.decode(audio)
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 2
    results: list[transcription.Result] = []
    try:
        loaded = transcription.load(path)
    except Exception as error:
        print(
            f"transcription_failed: speech model loading failed: {error}",
            file=sys.stderr,
        )
        problem = transcription.Issue(
            "speech_to_text",
            "transcription_failed",
            "speech model loading failed",
        )
        transcription.fail(sys.stdout, arguments.format, source, backend, problem)
        return 1
    for index, segment in enumerate(segments):
        try:
            result = transcription.transcribe(loaded, source, segment)
        except Exception as error:
            print(
                f"transcription_failed: speech transcription failed: {error}",
                file=sys.stderr,
            )
            result = transcription.Result(
                "failed",
                "",
                (
                    transcription.Issue(
                        "speech_to_text",
                        "transcription_failed",
                        "speech transcription failed",
                    ),
                ),
            )
        results.append(result)
        transcription.write(sys.stdout, result, index, arguments.format)
        if result.outcome in ("degraded", "skipped"):
            for problem in result.issues:
                print(f"{problem.code}: {problem.message}", file=sys.stderr)
        if result.outcome == "failed":
            break
    values = tuple(results)
    transcription.finish(sys.stdout, values, arguments.format, source, backend)
    outcome = transcription.aggregate(values)
    return {"completed": 0, "failed": 1, "degraded": 3, "skipped": 4}[outcome]


def run(arguments: argparse.Namespace, config: Settings) -> int:
    """Validate and execute the explicit composed speech-to-English plan."""
    try:
        prepared = execution.prepare(
            execution.Request(
                arguments.route or "",
                arguments.fused,
                arguments.speech,
                arguments.translation,
                config.commands.run,
                arguments.source,
                arguments.target,
                arguments.audio,
                config.cache_dir,
                arguments.verbose,
            )
        )
    except ValidationError as error:
        print(error, file=sys.stderr)
        return 2
    backend = execution.runtime()
    try:
        if not arguments.quiet and sys.stderr.isatty():
            print("Loading composed models", file=sys.stderr)
        loaded = execution.load(prepared, backend)
    except Exception as error:
        print(f"execution_failed: model loading failed: {error}", file=sys.stderr)
        problem = execution.Issue(
            "speech_to_text", "execution_failed", "model loading failed"
        )
        execution.fail(
            sys.stdout,
            arguments.format,
            prepared.plan,
            problem,
        )
        return 1
    values = execution.execute(
        prepared, loaded, sys.stdout, sys.stderr, arguments.format
    )
    execution.finish(sys.stdout, values, arguments.format, prepared.plan)
    outcome = execution.aggregate(values)
    return {"completed": 0, "failed": 1, "degraded": 3, "skipped": 4}[outcome]


def stream(arguments: argparse.Namespace, config: Settings) -> int:
    """Validate and execute the bounded live PCM translation pipeline."""
    try:
        if arguments.input != "-" or sys.stdin.isatty():
            raise ValidationError(
                "invalid_input: live requires explicit non-interactive stdin -"
            )
        settings = live.options(
            arguments.silence_ms,
            arguments.max_segment_seconds,
            arguments.min_segment_ms,
            arguments.buffer_seconds,
        )
        source = language(arguments.source)
        target = language(arguments.target)
        plan = execution.plan(
            "composed",
            "",
            arguments.speech,
            arguments.translation,
            config.commands.run,
            source,
            target,
        )
        path = transcription.validate(config.cache_dir, arguments.verbose)
        prepared = execution.Prepared(plan, path, ())
    except (ValidationError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    capture = live.capture(sys.stdin.buffer, settings)
    backend = execution.runtime()
    try:
        loaded = execution.load(prepared, backend)
    except KeyboardInterrupt:
        live.settle(capture, sys.stdin.buffer)
        live.terminal(
            sys.stdout, arguments.format, plan, (), live.Terminal("interruption", 0)
        )
        return 130
    except Exception as error:
        live.settle(capture, sys.stdin.buffer)
        print(f"execution_failed: model loading failed: {error}", file=sys.stderr)
        live.terminal(
            sys.stdout, arguments.format, plan, (), live.Terminal("failure", 0)
        )
        return 1
    results, terminal = live.execute(
        capture,
        sys.stdin.buffer,
        sys.stdout,
        sys.stderr,
        prepared,
        loaded,
        settings,
        arguments.format,
    )
    live.terminal(sys.stdout, arguments.format, plan, results, terminal)
    if terminal.completion in ("overload", "failure"):
        return 1
    if terminal.completion == "interruption":
        return 130
    outcome = execution.aggregate(results)
    return {"completed": 0, "failed": 1, "degraded": 3, "skipped": 4}[outcome]


def main() -> int:
    """Run the Caraway command-line interface."""
    cast(io.TextIOWrapper, sys.stdin).reconfigure(encoding="utf-8", errors="strict")
    cast(io.TextIOWrapper, sys.stdout).reconfigure(
        encoding="utf-8", errors="strict", newline="\n"
    )
    cast(io.TextIOWrapper, sys.stderr).reconfigure(
        encoding="utf-8", errors="replace", newline="\n"
    )
    arguments = parser().parse_args()
    try:
        config = (
            load(Settings.config_path, True)
            if arguments.config is None
            else load(arguments.config, False)
        )
    except InvalidConfigError as error:
        print(error, file=sys.stderr)
        return 2
    if arguments.command == "translate":
        return process(arguments, config)
    if arguments.command == "transcribe":
        return transcribe(arguments, config)
    if arguments.command == "run":
        return run(arguments, config)
    if arguments.command == "live":
        return stream(arguments, config)
    if arguments.action == "status":
        state = inspect(config.cache_dir)
        print(state)
        return 0 if state == "ready" else 1
    try:
        progress = io.StringIO() if arguments.quiet else sys.stderr
        download(config.cache_dir, progress)
    except DownloadLockError as error:
        print(f"download_in_progress: {error}", file=sys.stderr)
        return 1
    except DownloadError as error:
        print(f"download_failed: {error}", file=sys.stderr)
        return 1
    return 0
