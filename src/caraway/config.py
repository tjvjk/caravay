"""Load Caraway's single strict macOS TOML configuration source."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


class InvalidConfigError(ValueError):
    """Signal that the selected configuration cannot be used."""


@dataclass(frozen=True)
class Config:
    """Resolved configuration values needed by the model-status slice."""

    cache: Path


def fail(key: str, detail: str) -> NoReturn:
    """Raise a configuration error identifying its dotted key."""
    raise InvalidConfigError(f"invalid_config: {key} {detail}")


def backend(value: object, key: str) -> bool:
    """Validate that a value names the packaged backend."""
    match value:
        case "seamlessm4t-large-v2":
            return True
        case _:
            fail(key, "must name a packaged backend")


def command(value: object, prefix: str) -> bool:
    """Validate one single-backend command table."""
    match value:
        case dict() as table:
            unknown = sorted(set(table) - {"backend"})
            if unknown:
                fail(f"{prefix}.{unknown[0]}", "is unknown")
            return "backend" not in table or backend(
                table["backend"], f"{prefix}.backend"
            )
        case _:
            fail(prefix, "must be a table")


def run(value: object) -> bool:
    """Validate the run route and its route-specific backend bindings."""
    match value:
        case dict() as table:
            allowed = {"route", "backend", "speech_backend", "translation_backend"}
            unknown = sorted(set(table) - allowed)
            if unknown:
                fail(f"commands.run.{unknown[0]}", "is unknown")
            route = table.get("route", "composed")
            for key, item in table.items():
                if key != "route":
                    backend(item, f"commands.run.{key}")
            if route == "composed" and "backend" in table:
                fail("commands.run.backend", "conflicts with the composed route")
            if route == "fused" and "speech_backend" in table:
                fail("commands.run.speech_backend", "conflicts with the fused route")
            if route == "fused" and "translation_backend" in table:
                fail(
                    "commands.run.translation_backend",
                    "conflicts with the fused route",
                )
            if route == "fused" and "backend" not in table:
                fail("commands.run.backend", "is required by the fused route")
            if route not in ("composed", "fused"):
                fail("commands.run.route", "must be composed or fused")
            return True
        case _:
            fail("commands.run", "must be a table")


def commands(value: object) -> bool:
    """Validate every optional per-command configuration table."""
    match value:
        case dict() as table:
            unknown = sorted(set(table) - {"transcribe", "translate", "run"})
            if unknown:
                fail(f"commands.{unknown[0]}", "is unknown")
            transcribe = "transcribe" not in table or command(
                table["transcribe"], "commands.transcribe"
            )
            translate = "translate" not in table or command(
                table["translate"], "commands.translate"
            )
            execution = "run" not in table or run(table["run"])
            return transcribe and translate and execution
        case _:
            fail("commands", "must be a table")


def validate(value: object) -> str:
    """Validate the complete document and return its configured cache value."""
    match value:
        case dict() as table:
            unknown = sorted(set(table) - {"cache_dir", "commands"})
            if unknown:
                fail(unknown[0], "is unknown")
            if "commands" in table:
                commands(table["commands"])
            match table.get("cache_dir", "~/Library/Caches/caraway"):
                case str() as cache:
                    return cache
                case _:
                    fail("cache_dir", "must be a string")
        case _:
            fail("configuration", "must be a table")


def load(path: Path, optional: bool) -> Config:
    """Load one selected TOML source, allowing only an absent default file."""
    if optional and not path.exists():
        return Config(Path("~/Library/Caches/caraway").expanduser())
    try:
        document: object = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise InvalidConfigError(
            f"invalid_config: configuration cannot be read from {path}: {error}"
        ) from error
    return Config(Path(validate(document)).expanduser())
