"""Test Caraway through its public subprocess interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def invoke(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Invoke the development command with an isolated home directory."""
    home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / "xdg")
    command = Path(sys.executable).with_name("caraway")
    return subprocess.run(
        (command, *arguments),
        check=False,
        capture_output=True,
        cwd=home,
        env=environment,
        text=True,
        timeout=5,
    )


def status(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Invoke model status with an explicit isolated cache configuration."""
    config = home / f"կարգավորում-{uuid4()}.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
    return invoke(home, "--config", str(config), "models", "status", *arguments)


def publish(home: Path) -> Path:
    """Publish a small valid snapshot fixture."""
    snapshot = (
        home
        / "Library"
        / "Caches"
        / "caraway"
        / "seamlessm4t-large-v2"
        / "5f8cc790b19fc3f67a61c105133b20b34e3dcb76"
    )
    snapshot.mkdir(parents=True)
    payload = f"կշիռ-{uuid4()}".encode()
    (snapshot / "weights.bin").write_bytes(payload)
    manifest = {
        "manifest_version": 1,
        "backend": "seamlessm4t-large-v2",
        "repository": "facebook/seamless-m4t-v2-large",
        "revision": "5f8cc790b19fc3f67a61c105133b20b34e3dcb76",
        "files": [
            {
                "path": "weights.bin",
                "size": len(payload),
                "sha256": "7d" * 32,
            }
        ],
    }
    target = snapshot / "manifest.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def test_models_status_reports_a_missing_snapshot(tmp_path: Path) -> None:
    result = invoke(tmp_path / f"տուն-{uuid4()}", "models", "status")
    assert (result.returncode, result.stdout) == (1, "missing\n"), (
        "missing snapshot was not reported exactly"
    )


def test_models_status_reports_a_ready_snapshot(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = status(home)
    assert (result.returncode, result.stdout) == (0, "ready\n"), (
        "ready snapshot was not reported exactly"
    )


def test_explicit_config_selects_its_managed_cache(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    cache = tmp_path / f"պահոց-{uuid4()}"
    configured = cache / "home"
    publish(configured)
    source = configured / "Library" / "Caches" / "caraway"
    source.rename(cache / "models")
    config = tmp_path / f"կարգավորում-{uuid4()}.toml"
    config.write_text(f'cache_dir = "{cache / "models"}"\n', encoding="utf-8")
    result = invoke(home, "--config", str(config), "models", "status")
    assert (result.returncode, result.stdout) == (0, "ready\n"), (
        "explicit config did not select its managed cache"
    )


def test_default_config_selects_its_managed_cache(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    cache = tmp_path / f"պահոց-{uuid4()}"
    configured = cache / "home"
    publish(configured)
    source = configured / "Library" / "Caches" / "caraway"
    source.rename(cache / "models")
    config = home / "Library" / "Application Support" / "caraway" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(f'cache_dir = "{cache / "models"}"\n', encoding="utf-8")
    result = invoke(home, "models", "status")
    assert (result.returncode, result.stdout) == (0, "ready\n"), (
        "default config did not select its managed cache"
    )


@pytest.mark.parametrize(
    "document",
    (
        'cache_dir = ["ոչ"]\n',
        'unknown = "ոչ"\n',
        '[commands.unknown]\nbackend = "seamlessm4t-large-v2"\n',
        '[commands.run]\nroute = "composed"\nbackend = "seamlessm4t-large-v2"\n',
        '[commands.run]\nroute = "fused"\nspeech_backend = "seamlessm4t-large-v2"\n',
        '[commands.run]\nroute = "fused"\n',
        '[commands.translate]\nbackend = "ոչ-փաթեթավորված"\n',
        "սխալ = [\n",
    ),
)
def test_invalid_config_leaves_primary_output_empty(
    tmp_path: Path, document: str
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    config = tmp_path / f"կարգավորում-{uuid4()}.toml"
    config.write_text(document, encoding="utf-8")
    result = invoke(home, "--config", str(config), "models", "status")
    assert (result.returncode, result.stdout, "invalid_config" in result.stderr) == (
        2,
        "",
        True,
    ), "invalid configuration polluted stdout or lacked its stable diagnostic"


def test_missing_explicit_config_is_invalid(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    config = tmp_path / f"отсутствует-{uuid4()}.toml"
    result = invoke(home, "--config", str(config), "models", "status")
    assert (result.returncode, result.stdout, "invalid_config" in result.stderr) == (
        2,
        "",
        True,
    ), "missing explicit configuration was accepted"


def test_unreadable_explicit_config_is_invalid(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    config = tmp_path / f"թղթապանակ-{uuid4()}.toml"
    config.mkdir()
    result = invoke(home, "--config", str(config), "models", "status")
    assert (result.returncode, result.stdout, "invalid_config" in result.stderr) == (
        2,
        "",
        True,
    ), "unreadable explicit configuration was accepted"


def test_explicit_config_replaces_an_invalid_default(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    default = home / "Library" / "Application Support" / "caraway" / "config.toml"
    default.parent.mkdir(parents=True)
    default.write_text("սխալ = [\n", encoding="utf-8")
    explicit = tmp_path / f"կարգավորում-{uuid4()}.toml"
    explicit.write_text("", encoding="utf-8")
    result = invoke(home, "--config", str(explicit), "models", "status")
    assert (result.returncode, result.stdout) == (1, "missing\n"), (
        "explicit config did not replace the default source"
    )


def test_project_and_xdg_configs_are_not_consulted(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    xdg = home / "xdg" / "caraway" / "config.toml"
    xdg.parent.mkdir(parents=True)
    xdg.write_text("սխալ = [\n", encoding="utf-8")
    (home / "config.toml").write_text("սխալ = [\n", encoding="utf-8")
    result = invoke(home, "models", "status")
    assert (result.returncode, result.stdout) == (1, "missing\n"), (
        "an unselected config source was consulted"
    )


def test_models_status_reports_a_malformed_manifest_as_invalid(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    manifest.write_text("ոչ-json", encoding="utf-8")
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "malformed manifest was not reported as invalid"
    )


def test_models_status_rejects_a_mismatched_identity(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["repository"] = f"ուրիշ/{uuid4()}"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "mismatched identity was not reported as invalid"
    )


def test_models_status_rejects_a_missing_expected_file(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    (manifest.parent / "weights.bin").unlink()
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "missing expected file was not reported as invalid"
    )


def test_models_status_rejects_an_expected_file_size_mismatch(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    with (manifest.parent / "weights.bin").open("ab") as stream:
        stream.write("ավելորդ".encode())
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "file size mismatch was not reported as invalid"
    )


def test_models_status_does_not_hash_expected_files(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    payload = (manifest.parent / "weights.bin").read_bytes()
    (manifest.parent / "weights.bin").write_bytes(b"x" * len(payload))
    result = status(home)
    assert (result.returncode, result.stdout) == (0, "ready\n"), (
        "normal status unexpectedly hashed model weights"
    )


def test_models_status_accepts_no_model_name(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = status(home, f"մոդել-{uuid4()}")
    assert (result.returncode, result.stdout) == (2, ""), (
        "models status accepted a model name"
    )


def test_models_status_rejects_a_boolean_manifest_version(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["manifest_version"] = True
    manifest.write_text(json.dumps(document), encoding="utf-8")
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "boolean manifest version was accepted as integer version one"
    )


def test_route_conflict_diagnostic_identifies_its_dotted_key(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    config = tmp_path / f"կարգավորում-{uuid4()}.toml"
    config.write_text(
        '[commands.run]\nroute = "composed"\nbackend = "seamlessm4t-large-v2"\n',
        encoding="utf-8",
    )
    result = invoke(home, "--config", str(config), "models", "status")
    assert "commands.run.backend" in result.stderr, (
        "route conflict diagnostic omitted its known dotted key"
    )
