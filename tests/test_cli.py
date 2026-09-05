"""Test Caraway through its public subprocess interface."""

import json
import os
import pty
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import pytest


def invoke(
    home: Path,
    *arguments: str,
    additions: Mapping[str, str] | None = None,
    stdin: str = "",
    network: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke the development command with an isolated home directory."""
    home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / "xdg")
    environment["CACHE_DIR"] = str(home / f"չթույլատրված-{uuid4()}")
    if additions is not None:
        environment.update(additions)
    executable = Path(sys.executable).with_name("caraway")
    command = (
        (executable, *arguments)
        if network
        else (
            "/usr/bin/sandbox-exec",
            "-p",
            "(version 1)(allow default)(deny network*)",
            executable,
            *arguments,
        )
    )
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=home,
        env=environment,
        input=stdin,
        text=True,
        timeout=5,
    )


def hub(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Create a deterministic subprocess-visible fake Hugging Face boundary."""
    package = tmp_path / f"կեղծ-{uuid4()}" / "huggingface_hub"
    package.mkdir(parents=True)
    package.joinpath("__init__.py").write_text(
        '''"""Controlled Hugging Face download fixture."""
import json
import os
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

class RepoFile:
    def __init__(self, path: str, content: bytes) -> None:
        self.path = path
        self.size = len(content)
        self.blob_id = ""
        self.lfs = SimpleNamespace(sha256=hashlib.sha256(content).hexdigest())

class HfApi:
    def get_paths_info(
        self, repo_id: str, paths: list[str], *, revision: str
    ) -> list[RepoFile]:
        return [RepoFile(path, ("fixture:" + path).encode()) for path in paths]

def snapshot_download(
    repo_id: str,
    *,
    revision: str,
    local_dir: str,
    allow_patterns: list[str],
    **options: Any,
) -> str:
    root = Path(local_dir)
    fixture = Path(os.environ["CARAWAY_HUB_FIXTURE"])
    fixture.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("CARAWAY_PROGRESS_DISABLED"):
        print("controlled progress", file=__import__("sys").stderr)
    request = {"repo_id": repo_id, "revision": revision, "files": allow_patterns}
    fixture.joinpath("request.json").write_text(json.dumps(request), encoding="utf-8")
    if seconds := os.environ.get("CARAWAY_HUB_SLEEP"):
        import time
        time.sleep(float(seconds))
    if os.environ.get("CARAWAY_HUB_FAIL") == "before":
        raise RuntimeError("controlled network failure")
    for name in allow_patterns:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            fixture.joinpath("reused").write_text(name, encoding="utf-8")
        else:
            content = (
                "corrupt"
                if os.environ.get("CARAWAY_HUB_CORRUPT")
                else "fixture:" + name
            )
            target.write_bytes(content.encode())
        if os.environ.get("CARAWAY_HUB_FAIL") == "after_first":
            raise RuntimeError("controlled interrupted transfer")
    return str(root)
''',
        encoding="utf-8",
    )
    utilities = package / "utils"
    utilities.mkdir()
    utilities.joinpath("__init__.py").write_text("", encoding="utf-8")
    utilities.joinpath("tqdm.py").write_text(
        '"""Controlled progress fixture."""\n\n'
        "import os\n\ndef disable_progress_bars() -> bool:\n"
        '    os.environ["CARAWAY_PROGRESS_DISABLED"] = "1"\n'
        "    return True\n",
        encoding="utf-8",
    )
    package.parent.joinpath("sitecustomize.py").write_text(
        '''"""Controlled operating-system failure fixtures."""
import os
import pathlib
import shutil

if os.environ.get("CARAWAY_LOW_SPACE"):
    usage = shutil._ntuple_diskusage(1024, 1023, 1)
    def disk_usage(path: str) -> tuple[int, int, int]:
        return usage
    shutil.disk_usage = disk_usage

if os.environ.get("CARAWAY_PUBLISH_FAIL"):
    replace = pathlib.Path.replace
    def fail(source: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
        if source.name.endswith(".partial"):
            raise OSError("controlled publication failure")
        return replace(source, target)
    pathlib.Path.replace = fail
''',
        encoding="utf-8",
    )
    fixture = tmp_path / f"сервер-{uuid4()}"
    additions = {
        "PYTHONPATH": str(package.parent),
        "CARAWAY_HUB_FIXTURE": str(fixture),
    }
    return fixture, additions


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
    names = (
        "added_tokens.json",
        "config.json",
        "generation_config.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "model.safetensors.index.json",
        "preprocessor_config.json",
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer.model",
        "tokenizer_config.json",
    )
    files = []
    for name in names:
        payload = f"կշիռ-{name}-{uuid4()}".encode()
        (snapshot / name).write_bytes(payload)
        files.append({"path": name, "size": len(payload), "sha256": "7d" * 32})
    manifest = {
        "manifest_version": 1,
        "backend": "seamlessm4t-large-v2",
        "repository": "facebook/seamless-m4t-v2-large",
        "revision": "5f8cc790b19fc3f67a61c105133b20b34e3dcb76",
        "files": files,
    }
    target = snapshot / "manifest.json"
    target.write_text(json.dumps(manifest), encoding="utf-8")
    return target


def runtime(tmp_path: Path, output: str = "Good morning") -> dict[str, str]:
    """Create deterministic subprocess-visible Torch and Transformers boundaries."""
    root = tmp_path / f"գործարկում-{uuid4()}"
    torch = root / "torch"
    torch.mkdir(parents=True)
    torch.joinpath("__init__.py").write_text(
        '''"""Controlled Torch fixture."""
import os
from types import SimpleNamespace

float16 = "float16"
backends = SimpleNamespace(
    mps=SimpleNamespace(is_available=lambda: os.environ.get("CARAWAY_MPS") == "1")
)

class inference_mode:
    def __enter__(self):
        return self
    def __exit__(self, kind, value, traceback):
        return False
''',
        encoding="utf-8",
    )
    transformers = root / "transformers"
    transformers.mkdir()
    transformers.joinpath("__init__.py").write_text(
        '''"""Controlled Transformers fixture."""
import os
import sys

class Logging:
    def __init__(self):
        self.quiet = False
    def set_verbosity_error(self):
        self.quiet = True
    def set_verbosity_warning(self):
        self.quiet = False
    def disable_progress_bar(self):
        self.quiet = True
    def enable_progress_bar(self):
        self.quiet = False

logging = Logging()

class Batch(dict):
    def to(self, device):
        return self

class AutoProcessor:
    @classmethod
    def from_pretrained(cls, path, **options):
        if (
            not options.get("local_files_only")
            or os.environ.get("HF_HUB_OFFLINE") != "1"
            or os.environ.get("TRANSFORMERS_OFFLINE") != "1"
        ):
            raise RuntimeError("network loading was enabled")
        if not logging.quiet:
            print("controlled processor report", file=sys.stderr)
        return cls()
    def __call__(self, *, text, src_lang, return_tensors):
        return Batch(input_text=text, source=src_lang)
    def decode(self, tokens, *, skip_special_tokens, clean_up_tokenization_spaces):
        if clean_up_tokenization_spaces is not False:
            print("controlled BPE warning", file=sys.stderr)
        return os.environ["CARAWAY_OUTPUT"]

class SeamlessM4Tv2ForTextToText:
    @classmethod
    def from_pretrained(cls, path, **options):
        if not options.get("local_files_only") or options.get("dtype") != "float16":
            raise RuntimeError("unsafe model loading options")
        if not logging.quiet:
            print("controlled model report", file=sys.stderr)
        return cls()
    def to(self, device):
        if device != "mps":
            raise RuntimeError("CPU fallback")
        return self
    def eval(self):
        return self
    def generate(self, **options):
        if os.environ.get("CARAWAY_RUNTIME_FAIL"):
            raise RuntimeError("controlled inference failure")
        if options.get("tgt_lang") != "eng":
            raise RuntimeError("wrong target")
        return [[1]]
''',
        encoding="utf-8",
    )
    return {
        "PYTHONPATH": str(root),
        "CARAWAY_MPS": "1",
        "CARAWAY_OUTPUT": output,
    }


def test_translate_reads_source_armenian_from_a_file(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = tmp_path / f"աղբյուր-{uuid4()}.txt"
    source.write_text("Բարի լույս", encoding="utf-8")
    result = invoke(home, "translate", str(source), additions=runtime(tmp_path))
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "Good morning\n",
        "",
    ), "translation did not preserve the CLI output contract"


def test_translate_verbose_exposes_backend_diagnostics(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        "--verbose",
        "-",
        additions=runtime(tmp_path),
        stdin="Բարև",
    )
    assert (result.returncode, "controlled model report" in result.stderr) == (
        0,
        True,
    ), "verbose translation hid backend diagnostics"


def test_models_status_reports_a_missing_snapshot(tmp_path: Path) -> None:
    result = invoke(tmp_path / f"տուն-{uuid4()}", "models", "status")
    assert (result.returncode, result.stdout) == (1, "missing\n"), (
        "missing snapshot was not reported exactly"
    )


def test_translate_reads_source_armenian_from_standard_input(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        "-",
        additions=runtime(tmp_path, "  Welcome home  "),
        stdin="Բարի գալուստ",
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "Welcome home\n",
        "",
    ), "standard input translation was not edge trimmed"


def test_translate_writes_utf8_with_a_physical_lf(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    environment = os.environ.copy()
    environment.update(runtime(tmp_path, "English Ա"))
    environment["HOME"] = str(home)
    command = Path(sys.executable).with_name("caraway")
    result = subprocess.run(
        (command, "translate", "-"),
        input="Բարև".encode(),
        capture_output=True,
        check=False,
        env=environment,
        timeout=5,
    )
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "English Ա\n".encode(),
        b"",
    ), "translation output did not use UTF-8 and one physical LF"


def test_translate_succeeds_with_network_access_denied(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        "-",
        additions=runtime(tmp_path, "Offline result"),
        stdin="Անցանց",
        network=False,
    )
    assert (result.returncode, result.stdout) == (0, "Offline result\n"), (
        "translation required network access"
    )


def test_translate_omitted_operand_reads_noninteractive_input(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        additions=runtime(tmp_path, "Hello"),
        stdin="Բարև",
    )
    assert (result.returncode, result.stdout) == (0, "Hello\n"), (
        "omitted operand did not consume redirected input"
    )


def test_translate_rejects_an_invalid_utf8_file_before_model_validation(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    source = tmp_path / f"աղբյուր-{uuid4()}.txt"
    source.write_bytes(b"\xff")
    result = invoke(home, "translate", str(source))
    assert (result.returncode, result.stdout) == (2, ""), (
        "invalid UTF-8 input reached model validation"
    )


def test_translate_rejects_invalid_utf8_standard_input(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    command = Path(sys.executable).with_name("caraway")
    result = subprocess.run(
        (command, "translate", "-"),
        input=b"\xff",
        capture_output=True,
        check=False,
        env=environment,
        timeout=5,
    )
    assert (result.returncode, result.stdout) == (2, b""), (
        "invalid UTF-8 standard input caused an operational failure"
    )


def test_translate_omitted_operand_rejects_an_interactive_terminal(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    command = Path(sys.executable).with_name("caraway")
    master, slave = pty.openpty()
    try:
        with subprocess.Popen(
            (command, "translate"),
            stdin=slave,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            text=True,
        ) as process:
            stdout, stderr = process.communicate(timeout=5)
    finally:
        os.close(master)
        os.close(slave)
    assert (process.returncode, stdout, "invalid_input" in stderr) == (2, "", True), (
        "interactive omission waited for input"
    )


def test_translate_empty_text_skips_without_an_installed_model(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "translate", "-", stdin="")
    assert (result.returncode, result.stdout) == (4, ""), (
        "empty translation attempted backend setup"
    )


def test_translate_empty_jsonl_has_only_a_zero_count_summary(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "translate", "--format", "jsonl", "-", stdin="")
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        len(records),
        records[0]["outcome"],
        records[0]["segments"],
    ) == (
        4,
        1,
        "skipped",
        {"total": 0, "completed": 0, "degraded": 0, "skipped": 0, "failed": 0},
    ), "empty translation emitted an invalid JSONL summary"


@pytest.mark.parametrize("value", ("HY", "hye ", "hyե", "HYE"))
def test_translate_rejects_malformed_language_codes(tmp_path: Path, value: str) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "translate", "--source", value, "-", stdin="Բարև")
    assert (result.returncode, result.stdout, "invalid_language" in result.stderr) == (
        2,
        "",
        True,
    ), "malformed language code was accepted"


def test_translate_distinguishes_an_unsupported_capability(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "translate", "--target", "fra", "-", stdin="Բարև")
    assert (
        result.returncode,
        result.stdout,
        "unsupported_capability" in result.stderr,
    ) == (
        2,
        "",
        True,
    ), "unsupported capability was reported as malformed"


def test_translate_reports_a_missing_snapshot_before_mps(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "translate", "-", stdin="Բարև")
    assert (
        result.returncode,
        result.stdout,
        "model_not_installed" in result.stderr,
    ) == (
        2,
        "",
        True,
    ), "missing snapshot was not validated first"


def test_translate_rejects_an_invalid_snapshot_before_mps(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home).write_text("չվավեր", encoding="utf-8")
    result = invoke(home, "translate", "-", stdin="Բարև")
    assert (
        result.returncode,
        result.stdout,
        "model_cache_invalid" in result.stderr,
    ) == (
        2,
        "",
        True,
    ), "invalid snapshot reached MPS validation"


def test_translate_reports_unavailable_mps_without_loading_transformers(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    additions = runtime(tmp_path)
    additions["CARAWAY_MPS"] = "0"
    result = invoke(home, "translate", "-", additions=additions, stdin="Բարև")
    assert (result.returncode, result.stdout, "mps_unavailable" in result.stderr) == (
        2,
        "",
        True,
    ), "unavailable MPS reached model loading"


def test_translate_emits_schema_version_one_jsonl(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        "--format",
        "jsonl",
        "-",
        additions=runtime(tmp_path, "Hello, friend"),
        stdin="Բարև՛ ընկեր",
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (result.returncode, records) == (
        0,
        (
            {
                "schema_version": 1,
                "type": "segment",
                "index": 0,
                "outcome": "completed",
                "text": "Hello, friend",
                "issues": [],
            },
            {
                "schema_version": 1,
                "type": "summary",
                "command": "translate",
                "outcome": "completed",
                "source_language": "hye",
                "target_language": "eng",
                "backends": {"text_to_text": "seamlessm4t-large-v2"},
                "segments": {
                    "total": 1,
                    "completed": 1,
                    "degraded": 0,
                    "skipped": 0,
                    "failed": 0,
                },
            },
        ),
    ), "translation emitted the wrong JSONL records"


def test_translate_marks_repeating_output_as_degraded(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = invoke(
        home,
        "translate",
        "--format",
        "jsonl",
        "-",
        additions=runtime(tmp_path, "Useful  text loop loop loop"),
        stdin="Օգտակար տեքստ",
    )
    record = json.loads(result.stdout.splitlines()[0])
    assert (
        result.returncode,
        record["outcome"],
        record["text"],
        record["issues"][0]["code"],
    ) == (
        3,
        "degraded",
        "Useful  text",
        "repetition",
    ), "repeating suffix was not reported as degraded"


def test_translate_serializes_a_processing_failure(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    additions = runtime(tmp_path)
    additions["CARAWAY_RUNTIME_FAIL"] = "1"
    result = invoke(
        home,
        "translate",
        "--format",
        "jsonl",
        "-",
        additions=additions,
        stdin="Սխալ",
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        records[0]["outcome"],
        records[1]["outcome"],
        records[1]["error"],
    ) == (1, "failed", "failed", records[0]["issues"][0]), (
        "processing failure lacked matching segment and summary issues"
    )


@pytest.mark.skipif(
    "CARAWAY_REAL_MODEL_CONFIG" not in os.environ,
    reason="real model smoke test is opt-in",
)
def test_translate_real_model_produces_useful_english(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(
        home,
        "--config",
        os.environ["CARAWAY_REAL_MODEL_CONFIG"],
        "translate",
        "-",
        stdin="Բարև",
    )
    assert (result.returncode, "hello" in result.stdout.lower()) == (0, True), (
        "real model did not produce useful English"
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
    (manifest.parent / "config.json").unlink()
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "missing expected file was not reported as invalid"
    )


def test_models_status_rejects_an_incomplete_file_manifest(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["files"] = document["files"][:1]
    manifest.write_text(json.dumps(document), encoding="utf-8")
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "incomplete file manifest was reported as ready"
    )


def test_models_status_rejects_an_expected_file_size_mismatch(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    with (manifest.parent / "config.json").open("ab") as stream:
        stream.write("ավելորդ".encode())
    result = status(home)
    assert (result.returncode, result.stdout) == (1, "invalid\n"), (
        "file size mismatch was not reported as invalid"
    )


def test_models_status_does_not_hash_expected_files(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    payload = (manifest.parent / "config.json").read_bytes()
    (manifest.parent / "config.json").write_bytes(b"x" * len(payload))
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


def test_models_download_publishes_the_exact_pinned_snapshot(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    fixture, additions = hub(tmp_path)
    result = invoke(home, "models", "download", additions=additions)
    state = invoke(home, "models", "status")
    request = json.loads((fixture / "request.json").read_text(encoding="utf-8"))
    assert (
        result.returncode,
        result.stdout,
        result.stderr,
        state.stdout,
        request["repo_id"],
        request["revision"],
    ) == (
        0,
        "",
        "",
        "ready\n",
        "facebook/seamless-m4t-v2-large",
        "5f8cc790b19fc3f67a61c105133b20b34e3dcb76",
    ), "download did not publish the exact pinned snapshot"


def test_models_download_reuses_completed_staging_after_interruption(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    fixture, additions = hub(tmp_path)
    failed = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_FAIL": "after_first"},
    )
    resumed = invoke(home, "models", "download", additions=additions)
    assert (
        failed.returncode,
        failed.stdout,
        resumed.returncode,
        resumed.stdout,
        (fixture / "reused").exists(),
    ) == (1, "", 0, "", True), "download did not preserve reusable staging"


def test_models_download_failure_does_not_publish_staging(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    _, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_FAIL": "before"},
    )
    state = invoke(home, "models", "status")
    assert (result.returncode, result.stdout, state.stdout) == (1, "", "missing\n"), (
        "failed download published incomplete staging"
    )


def test_models_download_rejects_files_that_fail_verification(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    _, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_CORRUPT": "1"},
    )
    state = invoke(home, "models", "status")
    assert (result.returncode, result.stdout, state.stdout) == (1, "", "missing\n"), (
        "verification failure published a corrupted snapshot"
    )


def test_models_download_is_idempotent_without_a_network_request(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    fixture, additions = hub(tmp_path)
    invoke(home, "models", "download", additions=additions)
    (fixture / "request.json").unlink()
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_FAIL": "before"},
    )
    assert (result.returncode, result.stdout, (fixture / "request.json").exists()) == (
        0,
        "",
        False,
    ), "ready download path contacted the network"


def test_models_download_replaces_an_invalid_snapshot(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home).write_text("ոչ-json", encoding="utf-8")
    _, additions = hub(tmp_path)
    result = invoke(home, "models", "download", additions=additions)
    state = invoke(home, "models", "status")
    base = home / "Library" / "Caches" / "caraway" / "seamlessm4t-large-v2"
    copies = tuple(path.name for path in base.iterdir() if path.is_dir())
    assert (result.returncode, state.stdout, len(copies)) == (0, "ready\n", 1), (
        "invalid replacement was not atomic and singular"
    )


def test_models_download_recovers_interrupted_quarantine(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    snapshot = manifest.parent
    quarantine = snapshot.with_name(f"{snapshot.name}.quarantine")
    snapshot.rename(quarantine)
    fixture, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_FAIL": "before"},
    )
    assert (
        result.returncode,
        result.stdout,
        snapshot.exists(),
        quarantine.exists(),
        (fixture / "request.json").exists(),
    ) == (0, "", True, False, False), "download did not recover quarantine first"


def test_models_download_accepts_no_model_name(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = invoke(home, "models", "download", f"մոդել-{uuid4()}")
    assert (result.returncode, result.stdout) == (2, ""), (
        "models download accepted a model name"
    )


def test_models_download_accepts_the_global_quiet_option(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    _, additions = hub(tmp_path)
    result = invoke(home, "--quiet", "models", "download", additions=additions)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", ""), (
        "quiet model download emitted output"
    )


def test_models_download_rejects_a_concurrent_downloader(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    fixture, additions = hub(tmp_path)
    environment = os.environ.copy()
    environment.update(additions)
    environment["HOME"] = str(home)
    environment["CARAWAY_HUB_SLEEP"] = "1"
    command = Path(sys.executable).with_name("caraway")
    with subprocess.Popen(
        (command, "models", "download"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    ) as process:
        deadline = time.monotonic() + 3
        while not (fixture / "request.json").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        result = invoke(home, "models", "download", additions=additions)
        process.communicate(timeout=5)
    assert (
        result.returncode,
        result.stdout,
        "download_in_progress" in result.stderr,
    ) == (
        1,
        "",
        True,
    ), "concurrent downloader was not rejected"


def test_models_download_checks_free_space_before_network(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    fixture, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_LOW_SPACE": "1"},
    )
    assert (
        result.returncode,
        result.stdout,
        "download_failed" in result.stderr,
        (fixture / "request.json").exists(),
    ) == (1, "", True, False), "insufficient space did not fail before network"


def test_models_download_failure_preserves_an_invalid_snapshot(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    manifest.write_text("չվավեր", encoding="utf-8")
    _, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_HUB_FAIL": "before"},
    )
    assert (result.returncode, result.stdout, manifest.read_text(encoding="utf-8")) == (
        1,
        "",
        "չվավեր",
    ), "failed transfer damaged the existing invalid snapshot"


def test_models_download_restores_an_invalid_snapshot_after_publish_failure(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    manifest = publish(home)
    manifest.write_text("չվավեր", encoding="utf-8")
    _, additions = hub(tmp_path)
    result = invoke(
        home,
        "models",
        "download",
        additions={**additions, "CARAWAY_PUBLISH_FAIL": "1"},
    )
    assert (result.returncode, result.stdout, manifest.read_text(encoding="utf-8")) == (
        1,
        "",
        "չվավեր",
    ), "failed publication did not restore the invalid snapshot"
