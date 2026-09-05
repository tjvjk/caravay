"""Define and load Caraway application settings."""

import tomllib
from pathlib import Path
from typing import Annotated, ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
    TomlConfigSettingsSource,
)

DEFAULT_BACKEND: Final = "seamlessm4t-large-v2"
MODEL_REPOSITORY: Final = "facebook/seamless-m4t-v2-large"
MODEL_REVISION: Final = "5f8cc790b19fc3f67a61c105133b20b34e3dcb76"
Backend = Literal["seamlessm4t-large-v2"]


class InvalidConfigError(ValueError):
    """Signal that the selected configuration cannot be used."""


class Command(BaseModel):
    """Select the packaged backend for a single-stage command."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    backend: Backend = DEFAULT_BACKEND


class Composed(BaseModel):
    """Select both backend bindings for the composed run route."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    route: Literal["composed"] = "composed"
    speech_backend: Backend = DEFAULT_BACKEND
    translation_backend: Backend = DEFAULT_BACKEND


class Fused(BaseModel):
    """Select an explicit backend for a fused run route."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    route: Literal["fused"]
    backend: Backend


Route = Annotated[Composed | Fused, Field(discriminator="route")]


class Commands(BaseModel):
    """Hold optional settings for every processing command."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    transcribe: Command = Field(default_factory=Command)
    translate: Command = Field(default_factory=Command)
    run: Route = Field(default_factory=Composed)


class Settings(BaseSettings):
    """Hold packaged identity, macOS paths, and strict user configuration."""

    model_config = SettingsConfigDict(extra="forbid", frozen=True, strict=True)

    application_name: ClassVar[str] = "caraway"
    config_name: ClassVar[str] = "config.toml"
    manifest_name: ClassVar[str] = "manifest.json"
    manifest_version: ClassVar[int] = 1
    base_path: ClassVar[Path] = Path.home() / "Library"
    support_path: ClassVar[Path] = base_path / "Application Support" / application_name
    config_path: ClassVar[Path] = support_path / config_name
    cache_path: ClassVar[Path] = base_path / "Caches" / application_name
    backend_name: ClassVar[str] = DEFAULT_BACKEND
    repository_name: ClassVar[str] = MODEL_REPOSITORY
    revision: ClassVar[str] = MODEL_REVISION

    cache_dir: Path = Field(
        default_factory=lambda: Settings.cache_path,
        strict=False,
    )
    commands: Commands = Field(default_factory=Commands)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use constructor values only and never consult environment settings."""
        return (init_settings,)


def key(error: ValidationError) -> str:
    """Return the first invalid setting as a dotted key."""
    location = error.errors()[0]["loc"]
    parts = tuple(part for part in location if part not in ("composed", "fused"))
    return ".".join(str(part) for part in parts)


def load(path: Path, optional: bool) -> Settings:
    """Load one TOML source, allowing only an absent default file."""
    if optional and not path.exists():
        return Settings()
    if not path.is_file():
        raise InvalidConfigError(
            f"invalid_config: configuration cannot be read from {path}"
        )
    try:
        source = TomlConfigSettingsSource(Settings, path)
        return Settings.model_validate(source())
    except (OSError, UnicodeError, SettingsError, tomllib.TOMLDecodeError) as error:
        raise InvalidConfigError(
            f"invalid_config: configuration cannot be read from {path}: {error}"
        ) from error
    except ValidationError as error:
        raise InvalidConfigError(
            f"invalid_config: {key(error)} has an invalid value"
        ) from error
