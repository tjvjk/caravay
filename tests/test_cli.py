"""Test Caraway through its public subprocess interface."""

import json
import os
import pty
import subprocess
import sys
import time
import wave
from array import array
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
    executable = str(Path(sys.executable).with_name("caraway"))
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

class Tensor:
    def to(self, **options):
        return self

class AutoProcessor:
    index = 0
    @classmethod
    def from_pretrained(cls, path, **options):
        if os.environ.get("CARAWAY_RUNTIME_FAIL") == "load":
            raise RuntimeError("controlled model loading failure")
        if (
            not options.get("local_files_only")
            or os.environ.get("HF_HUB_OFFLINE") != "1"
            or os.environ.get("TRANSFORMERS_OFFLINE") != "1"
        ):
            raise RuntimeError("network loading was enabled")
        if not logging.quiet:
            print("controlled processor report", file=sys.stderr)
        return cls()
    def __call__(self, **options):
        if "audio" in options:
            if not isinstance(options["audio"], list):
                raise TypeError(
                    "only a single or a list of entries is supported but got "
                    f"type={type(options['audio'])}"
                )
            return Batch(input_features=Tensor())
        return Batch(options)
    def decode(self, tokens, *, skip_special_tokens, clean_up_tokenization_spaces):
        if clean_up_tokenization_spaces is not False:
            print("controlled BPE warning", file=sys.stderr)
        outputs = __import__("json").loads(
            os.environ.get(
                "CARAWAY_OUTPUTS",
                __import__("json").dumps([os.environ["CARAWAY_OUTPUT"]]),
            )
        )
        output = outputs[AutoProcessor.index]
        AutoProcessor.index += 1
        return output

class SeamlessM4Tv2ForTextToText:
    generated = 0
    @classmethod
    def from_pretrained(cls, path, **options):
        if os.environ.get("CARAWAY_RUNTIME_FAIL") == "load":
            raise RuntimeError("controlled model loading failure")
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
        if (
            SeamlessM4Tv2ForTextToText.generated > 0
            and (seconds := os.environ.get("CARAWAY_RUNTIME_DELAY_AFTER_FIRST"))
        ):
            Path = __import__("pathlib").Path
            Path(os.environ["CARAWAY_LATER_STARTED"]).touch()
            __import__("time").sleep(float(seconds))
        if os.environ.get("CARAWAY_RUNTIME_FAIL") or os.environ.get(
            "CARAWAY_RUNTIME_FAIL_INDEX"
        ) == str(SeamlessM4Tv2ForTextToText.generated):
            raise RuntimeError("controlled inference failure")
        if options.get("tgt_lang") not in ("eng", "hye"):
            raise RuntimeError("wrong target")
        if options.get("tgt_lang") == "hye" and options.get("max_new_tokens") != 256:
            raise RuntimeError("unbounded speech generation")
        SeamlessM4Tv2ForTextToText.generated += 1
        length = 257 if os.environ.get("CARAWAY_RUNTIME_LIMITED") == "1" else 1
        return [[1] * length]

class SeamlessM4Tv2ForSpeechToText(SeamlessM4Tv2ForTextToText):
    pass
''',
        encoding="utf-8",
    )
    return {
        "PYTHONPATH": str(root),
        "CARAWAY_MPS": "1",
        "CARAWAY_OUTPUT": output,
    }


def audio(tmp_path: Path, seconds: int = 21) -> Path:
    """Create a small irregular silent WAV input."""
    path = tmp_path / f"ձայն-{uuid4()}.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(b"\0\0" * 16_000 * seconds)
    return path


def speech(tmp_path: Path, outputs: tuple[str, ...]) -> dict[str, str]:
    """Create a controlled speech runtime with one output per segment."""
    additions = runtime(tmp_path)
    additions["CARAWAY_OUTPUTS"] = json.dumps(outputs, ensure_ascii=False)
    return additions


def transcribe(
    home: Path,
    *arguments: str,
    additions: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke transcription with an explicit isolated configuration."""
    home.mkdir(parents=True, exist_ok=True)
    config = home / f"կարգավորում-{uuid4()}.toml"
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
    return invoke(
        home, "--config", str(config), "transcribe", *arguments, additions=additions
    )


def run(
    home: Path,
    *arguments: str,
    additions: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the composed pipeline with an explicit isolated configuration."""
    home.mkdir(parents=True, exist_ok=True)
    config = home / f"կարգավորում-{uuid4()}.toml"
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
    return invoke(home, "--config", str(config), "run", *arguments, additions=additions)


def live(
    home: Path,
    samples: tuple[float, ...],
    *arguments: str,
    additions: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Invoke live translation with explicit raw PCM standard input."""
    home.mkdir(parents=True, exist_ok=True)
    config = home / f"կարգավորում-{uuid4()}.toml"
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    if additions is not None:
        environment.update(additions)
    command = Path(sys.executable).with_name("caraway")
    return subprocess.run(
        (
            command,
            "--config",
            config,
            "live",
            "--input-format",
            "f32le",
            *arguments,
            "-",
        ),
        input=array("f", samples).tobytes(),
        capture_output=True,
        check=False,
        env=environment,
        timeout=5,
    )


def test_live_translates_one_pcm_utterance_at_eof(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    samples = (0.2,) * 8_000
    result = live(home, samples, additions=speech(tmp_path, ("Բարեւ", "Hello")))
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        b"Hello\n",
        b"",
    ), "live PCM speech was not translated at end of input"


@pytest.mark.parametrize("arguments", ((), ("--input-format", "s16le", "-")))
def test_live_rejects_an_invalid_input_contract_before_model_loading(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    additions = runtime(tmp_path)
    additions["CARAWAY_RUNTIME_FAIL"] = "load"
    result = invoke(home, "live", *arguments, additions=additions)
    assert (result.returncode, result.stdout) == (2, ""), (
        "invalid live input reached model loading"
    )


def test_live_jsonl_preserves_sample_positions_and_clean_completion(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    samples = (0.2,) * 3_200 + (0.0,) * 9_600 + (0.3,) * 4_800
    result = live(
        home,
        samples,
        "--format",
        "jsonl",
        additions=speech(tmp_path, ("Առաջին", "First", "Երկրորդ", "Second")),
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        tuple(
            (record["source_start_sample"], record["source_end_sample"])
            for record in records[:-1]
        ),
        tuple(record["text"] for record in records[:-1]),
        records[-1]["command"],
        records[-1]["completion"],
    ) == (
        0,
        ((0, 3_200), (12_800, 17_600)),
        ("First", "Second"),
        "live",
        "clean_eof",
    ), "live JSONL lost ordered sample positions or completion"


def test_live_combines_short_speech_fragments_without_losing_samples(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    samples = (0.2,) * 1_600 + (0.0,) * 9_600 + (0.3,) * 2_400
    result = live(
        home,
        samples,
        additions=speech(tmp_path, ("Միասին", "Together")),
    )
    assert (result.returncode, result.stdout) == (0, b"Together\n"), (
        "short live fragments were lost or attempted separately"
    )


def test_live_reports_bounded_buffer_overload(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = live(
        home,
        (0.2,) * 160_000,
        "--buffer-seconds",
        "0.02",
        "--format",
        "jsonl",
        additions=speech(tmp_path, ("Չօգտագործված",)),
    )
    terminal = json.loads(result.stdout.splitlines()[-1])
    assert (result.returncode, terminal["completion"], bool(result.stderr)) == (
        1,
        "overload",
        True,
    ), "live overload was silent or successful"


def test_live_stops_after_a_fatal_segment(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    additions = speech(tmp_path, ("Չօգտագործված",))
    additions["CARAWAY_RUNTIME_FAIL_INDEX"] = "0"
    result = live(
        home,
        (0.2,) * 4_800,
        "--format",
        "jsonl",
        additions=additions,
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        records[0]["outcome"],
        records[-1]["completion"],
    ) == (1, "failed", "failure"), "fatal live inference did not terminate the stream"


def test_live_enforces_the_configured_maximum_speech_duration(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = live(
        home,
        (0.2,) * 12_800,
        "--max-segment-seconds",
        "0.4",
        "--buffer-seconds",
        "2",
        additions=speech(tmp_path, ("Մեկ", "One", "Երկու", "Two")),
    )
    assert (result.returncode, result.stdout) == (0, b"One\nTwo\n"), (
        "maximum live duration did not split continuous speech"
    )


def test_live_discards_silence_at_clean_eof(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    result = live(
        home,
        (0.0,) * 4_800,
        additions=speech(tmp_path, ("Չօգտագործված",)),
    )
    assert (result.returncode, result.stdout, result.stderr) == (4, b"", b""), (
        "live EOF fabricated output from buffered silence"
    )


def test_run_emits_ordered_useful_english_segments(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    additions = speech(
        tmp_path,
        ("Բարեւ", "Hello", "", "Վերջ", "The end"),
    )
    result = run(home, str(source), additions=additions)
    assert (result.returncode, result.stdout, result.stderr) == (
        3,
        "Hello\nThe end\n",
        "empty_output: transcription produced no useful text\n",
    ), "composed execution lost ordered useful English text"


def test_run_preserves_transcripts_and_resolved_plan_in_jsonl(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = run(
        home,
        "--format",
        "jsonl",
        str(source),
        additions=speech(tmp_path, ("Բարի լույս", "Good morning")),
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
                "text": "Good morning",
                "issues": [],
                "source_transcript": "Բարի լույս",
            },
            {
                "schema_version": 1,
                "type": "summary",
                "command": "run",
                "route": "composed",
                "outcome": "completed",
                "source_language": "hye",
                "target_language": "eng",
                "backends": {
                    "speech_to_text": "seamlessm4t-large-v2",
                    "text_to_text": "seamlessm4t-large-v2",
                },
                "segments": {
                    "total": 1,
                    "completed": 1,
                    "degraded": 0,
                    "skipped": 0,
                    "failed": 0,
                },
            },
        ),
    ), "composed JSONL omitted its transcript or explicit plan"


@pytest.mark.parametrize(
    ("outputs", "status", "outcome", "text", "transcript"),
    (
        (("Բարեւ կրկին կրկին կրկին", "Hello"), 3, "degraded", "Hello", "Բարեւ"),
        (
            ("Բարեւ կրկին կրկին կրկին", "Hello again again again"),
            3,
            "degraded",
            "Hello",
            "Բարեւ",
        ),
        (("Բարեւ կրկին կրկին կրկին", ""), 4, "skipped", None, "Բարեւ"),
        (("Բարեւ", "Hello again again again"), 3, "degraded", "Hello", "Բարեւ"),
        (("",), 4, "skipped", None, None),
        (("Բարեւ", ""), 4, "skipped", None, "Բարեւ"),
    ),
)
def test_run_propagates_each_nonfatal_stage_outcome(
    tmp_path: Path,
    outputs: tuple[str, ...],
    status: int,
    outcome: str,
    text: str | None,
    transcript: str | None,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = run(
        home,
        "--format",
        "jsonl",
        str(source),
        additions=speech(tmp_path, outputs),
    )
    record = json.loads(result.stdout.splitlines()[0])
    assert (
        result.returncode,
        record["outcome"],
        record["text"],
        record.get("source_transcript"),
    ) == (status, outcome, text, transcript), (
        "composed stage outcome was improved or lost"
    )


def test_run_stops_after_a_fatal_translation_and_reports_it(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    additions = speech(tmp_path, ("Առաջին", "Չօգտագործված"))
    additions["CARAWAY_RUNTIME_FAIL_INDEX"] = "1"
    result = run(home, "--format", "jsonl", str(source), additions=additions)
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        len(records),
        records[0].get("source_transcript"),
        records[0]["outcome"],
        records[1]["segments"],
        records[1]["error"]["stage"],
    ) == (
        1,
        2,
        "Առաջին",
        "failed",
        {"total": 1, "completed": 0, "degraded": 0, "skipped": 0, "failed": 1},
        "text_to_text",
    ), "fatal translation did not preserve the partial composed outcome"


def test_run_omits_a_transcript_after_fatal_speech_recognition(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    additions = speech(tmp_path, ("Չօգտագործված",))
    additions["CARAWAY_RUNTIME_FAIL_INDEX"] = "0"
    result = run(home, "--format", "jsonl", str(source), additions=additions)
    record = json.loads(result.stdout.splitlines()[0])
    assert (
        result.returncode,
        record["outcome"],
        record["issues"][0]["stage"],
        "source_transcript" in record,
    ) == (1, "failed", "speech_to_text", False), (
        "fatal speech recognition fabricated a transcript"
    )


def test_run_model_load_failure_reports_zero_attempted_segments(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    additions = speech(tmp_path, ("Չօգտագործված",))
    additions["CARAWAY_RUNTIME_FAIL"] = "load"
    result = run(home, "--format", "jsonl", str(source), additions=additions)
    summary = json.loads(result.stdout)
    assert (result.returncode, summary["outcome"], summary["segments"]) == (
        1,
        "failed",
        {"total": 0, "completed": 0, "degraded": 0, "skipped": 0, "failed": 0},
    ), "model load failure fabricated a composed segment"


def test_run_validates_the_complete_plan_before_model_loading(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    additions = speech(tmp_path, ("Չօգտագործված",))
    additions["CARAWAY_RUNTIME_FAIL"] = "load"
    result = run(
        home,
        "--translation-backend",
        "անհայտ",
        str(source),
        additions=additions,
    )
    assert (result.returncode, result.stdout) == (2, ""), (
        "invalid complete plan reached model loading"
    )


@pytest.mark.parametrize(
    ("arguments", "operand"),
    (
        (("--source", "HYE"), "audio"),
        (("--target", "fra"), "audio"),
        ((), "-"),
        ((), "https://օրինակ.test/ձայն.wav"),
        ((), "folder"),
    ),
)
def test_run_rejects_invalid_input_and_languages_before_loading(
    tmp_path: Path, arguments: tuple[str, ...], operand: str
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    home.joinpath("folder").mkdir(parents=True)
    source = str(audio(tmp_path, 1)) if operand == "audio" else operand
    additions = runtime(tmp_path)
    additions["CARAWAY_RUNTIME_FAIL"] = "load"
    result = run(home, *arguments, source, additions=additions)
    assert (result.returncode, result.stdout) == (2, ""), (
        "invalid run input or language reached model loading"
    )


def test_run_writes_deterministic_utf8_lf_output_bytes(tmp_path: Path) -> None:
    outputs = ("Բարի լույս", "Good morning Ա")
    results = []
    for _ in range(2):
        home = tmp_path / f"տուն-{uuid4()}"
        publish(home)
        source = audio(tmp_path, 1)
        additions = speech(tmp_path, outputs)
        environment = os.environ.copy()
        environment.update(additions)
        environment["HOME"] = str(home)
        config = home / f"կարգավորում-{uuid4()}.toml"
        cache = home / "Library" / "Caches" / "caraway"
        config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
        command = Path(sys.executable).with_name("caraway")
        results.append(
            subprocess.run(
                (command, "--config", str(config), "run", str(source)),
                capture_output=True,
                check=False,
                env=environment,
                timeout=5,
            )
        )
    assert tuple(
        (result.returncode, result.stdout, result.stderr) for result in results
    ) == (
        (0, "Good morning Ա\n".encode(), b""),
        (0, "Good morning Ա\n".encode(), b""),
    ), "fixed composed execution produced nondeterministic output bytes"


@pytest.mark.parametrize(
    "arguments",
    (
        ("--route", "composed", "--backend", "seamlessm4t-large-v2"),
        (
            "--route",
            "fused",
            "--backend",
            "seamlessm4t-large-v2",
            "--speech-backend",
            "seamlessm4t-large-v2",
        ),
    ),
)
def test_run_rejects_conflicting_route_options(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    source = audio(tmp_path, 1)
    result = run(tmp_path / f"տուն-{uuid4()}", *arguments, str(source))
    assert (result.returncode, result.stdout) == (2, ""), (
        "conflicting composed and fused options were accepted"
    )


def test_run_rejects_a_configured_unsupported_fused_route(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    home.mkdir()
    source = audio(tmp_path, 1)
    config = home / f"կարգավորում-{uuid4()}.toml"
    config.write_text(
        '[commands.run]\nroute = "fused"\nbackend = "seamlessm4t-large-v2"\n',
        encoding="utf-8",
    )
    result = invoke(home, "--config", str(config), "run", str(source))
    assert (result.returncode, result.stdout) == (2, ""), (
        "unsupported configured fused route was executed"
    )


def test_run_cli_route_overrides_the_configured_route_independently(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    home.mkdir()
    publish(home)
    source = audio(tmp_path, 1)
    config = home / f"կարգավորում-{uuid4()}.toml"
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(
        f'cache_dir = "{cache}"\n'
        '[commands.run]\nroute = "fused"\nbackend = "seamlessm4t-large-v2"\n',
        encoding="utf-8",
    )
    result = invoke(
        home,
        "--config",
        str(config),
        "run",
        "--route",
        "composed",
        str(source),
        additions=speech(tmp_path, ("Բարեւ", "Hello")),
    )
    assert (result.returncode, result.stdout) == (0, "Hello\n"), (
        "CLI route did not independently override the configured route"
    )


@pytest.mark.skipif(
    "CARAWAY_REAL_MODEL_CONFIG" not in os.environ,
    reason="real model smoke test is opt-in",
)
def test_run_real_model_produces_useful_english(tmp_path: Path) -> None:
    result = invoke(
        tmp_path / f"տուն-{uuid4()}",
        "--config",
        os.environ["CARAWAY_REAL_MODEL_CONFIG"],
        "run",
        os.environ["CARAWAY_REAL_AUDIO"],
        network=False,
    )
    assert (result.returncode, bool(result.stdout.strip())) == (0, True), (
        "real composed model did not produce useful English"
    )


def test_transcribe_requires_one_local_audio_file(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = transcribe(home, "-")
    assert (result.returncode, result.stdout) == (2, ""), "audio stdin was accepted"


def test_transcribe_requires_an_audio_operand(tmp_path: Path) -> None:
    result = transcribe(tmp_path / f"տուն-{uuid4()}")
    assert (result.returncode, result.stdout) == (2, ""), (
        "missing audio operand was accepted"
    )


def test_transcribe_rejects_an_unreadable_audio_file(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    source = tmp_path / f"ձայն-{uuid4()}.wav"
    source.write_bytes("անվավեր".encode())
    source.chmod(0)
    result = transcribe(home, str(source))
    assert (result.returncode, result.stdout) == (2, ""), (
        "unreadable audio file was accepted"
    )


def test_transcribe_emits_ordered_useful_segments(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    result = transcribe(
        home,
        str(source),
        additions=speech(tmp_path, ("  Բարեւ  ", "", "Վերջ")),
    )
    assert (result.returncode, result.stdout) == (3, "Բարեւ\nՎերջ\n"), (
        "transcription lost ordered useful text"
    )


def test_transcribe_flushes_each_completed_segment(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    additions = speech(tmp_path, ("Առաջին", "Երկրորդ", "Երրորդ"))
    additions["CARAWAY_RUNTIME_DELAY_AFTER_FIRST"] = "1.5"
    marker = tmp_path / f"հաջորդ-{uuid4()}"
    additions["CARAWAY_LATER_STARTED"] = str(marker)
    environment = os.environ.copy()
    environment.update(additions)
    environment["HOME"] = str(home)
    config = home / f"կարգավորում-{uuid4()}.toml"
    cache = home / "Library" / "Caches" / "caraway"
    config.write_text(f'cache_dir = "{cache}"\n', encoding="utf-8")
    command = Path(sys.executable).with_name("caraway")
    with subprocess.Popen(
        (command, "--config", str(config), "transcribe", str(source)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        text=True,
    ) as process:
        assert process.stdout is not None
        line = process.stdout.readline()
        delayed = marker.exists()
        process.communicate(timeout=8)
    assert (line, delayed) == ("Առաջին\n", False), (
        "completed transcription segment remained buffered"
    )


@pytest.mark.parametrize("operand", ("https://օրինակ.test/ձայն.wav", "folder"))
def test_transcribe_rejects_non_file_audio_operands(
    tmp_path: Path, operand: str
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    home.joinpath("folder").mkdir(parents=True)
    result = transcribe(home, operand)
    assert (result.returncode, result.stdout) == (2, ""), (
        "non-file audio operand was accepted"
    )


def test_transcribe_rejects_extra_audio_operands(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    result = transcribe(home, "մեկ.wav", "երկու.wav")
    assert (result.returncode, result.stdout) == (2, ""), (
        "extra audio operand was accepted"
    )


def test_transcribe_truncates_repetition_and_continues(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    result = transcribe(
        home,
        "--format",
        "jsonl",
        str(source),
        additions=speech(tmp_path, ("Օգտակար կրկին կրկին կրկին", "Հաջորդ", "Վերջ")),
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        tuple(record.get("text") for record in records[:-1]),
        tuple(record["outcome"] for record in records[:-1]),
        records[-1],
    ) == (
        3,
        ("Օգտակար", "Հաջորդ", "Վերջ"),
        ("degraded", "completed", "completed"),
        {
            "schema_version": 1,
            "type": "summary",
            "command": "transcribe",
            "outcome": "degraded",
            "source_language": "hye",
            "backends": {"speech_to_text": "seamlessm4t-large-v2"},
            "segments": {
                "total": 3,
                "completed": 2,
                "degraded": 1,
                "skipped": 0,
                "failed": 0,
            },
        },
    ), "repetition prevented later transcription segments"


def test_transcribe_truncates_repetition_with_varied_punctuation(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = transcribe(
        home,
        "--format",
        "jsonl",
        str(source),
        additions=speech(
            tmp_path,
            ("Օգտակար,  տեքստ տատիկին, տատիկին\u0589 տատիկին՜",),
        ),
    )
    record = json.loads(result.stdout.splitlines()[0])
    assert (result.returncode, record["outcome"], record["text"]) == (
        3,
        "degraded",
        "Օգտակար,  տեքստ",
    ), "punctuation concealed a cyclic Armenian suffix"


def test_transcribe_truncates_a_multiword_cycle_at_the_generation_limit(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = transcribe(
        home,
        "--format",
        "jsonl",
        str(source),
        additions={
            **speech(tmp_path, ("Սկիզբ նայեք մինա նայեք մինա նայեք",)),
            "CARAWAY_RUNTIME_LIMITED": "1",
        },
    )
    record = json.loads(result.stdout.splitlines()[0])
    assert (result.returncode, record["outcome"], record["text"]) == (
        3,
        "degraded",
        "Սկիզբ",
    ), "generation-limit cutoff concealed a multiword cycle"


def test_transcribe_preserves_a_partial_cycle_below_the_generation_limit(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = transcribe(
        home,
        str(source),
        additions=speech(tmp_path, ("Սկիզբ նայեք մինա նայեք մինա նայեք",)),
    )
    assert (result.returncode, result.stdout) == (
        0,
        "Սկիզբ նայեք մինա նայեք մինա նայեք\n",
    ), "partial repetition below the generation limit was removed"


def test_transcribe_preserves_distinct_punctuation_tokens(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = transcribe(
        home,
        str(source),
        additions=speech(tmp_path, ("Ի՞նչ ! ? …",)),
    )
    assert (result.returncode, result.stdout) == (
        0,
        "Ի՞նչ ! ? …\n",
    ), "distinct punctuation tokens were treated as a cycle"


def test_transcribe_removes_bounded_armenian_cycles_and_continues(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    result = transcribe(
        home,
        "--format",
        "jsonl",
        str(source),
        additions=speech(
            tmp_path,
            (
                "Պահպանված նայեք մինա նայեք\u055d մինա\u055d նայեք\u0589 մինա\u0589",
                "մինա\u055d մինա\u0589 մինա՜",
                "Վերջ",
            ),
        ),
    )
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        tuple(record.get("text") for record in records[:-1]),
        tuple(record["outcome"] for record in records[:-1]),
        tuple(
            record["issues"][0]["code"] if record["issues"] else None
            for record in records[:-1]
        ),
    ) == (
        3,
        ("Պահպանված", None, "Վերջ"),
        ("degraded", "skipped", "completed"),
        ("repetition", "repetition", None),
    ), "bounded Armenian cycles escaped or stopped later segments"


def test_transcribe_preserves_ordinary_grammatical_repetition(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    result = transcribe(
        home,
        str(source),
        additions=speech(tmp_path, ("Նայեք, նայեք\u055d տատիկին\u0589",)),
    )
    assert (result.returncode, result.stdout) == (
        0,
        "Նայեք, նայեք\u055d տատիկին\u0589\n",
    ), "ordinary grammatical repetition was removed"


def test_transcribe_serializes_a_fatal_partial_jsonl_outcome(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    additions = speech(tmp_path, ("Առաջին", "Չօգտագործված"))
    additions["CARAWAY_RUNTIME_FAIL_INDEX"] = "1"
    result = transcribe(home, "--format", "jsonl", str(source), additions=additions)
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (
        result.returncode,
        len(records),
        records[0]["text"],
        records[1]["outcome"],
        records[2]["segments"],
        records[2]["error"],
    ) == (
        1,
        3,
        "Առաջին",
        "failed",
        {"total": 2, "completed": 1, "degraded": 0, "skipped": 0, "failed": 1},
        records[1]["issues"][0],
    ), "fatal partial transcription serialized an invalid JSONL outcome"


def test_transcribe_preserves_text_before_a_fatal_segment(tmp_path: Path) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path)
    additions = speech(tmp_path, ("Պահպանված", "Չօգտագործված"))
    additions["CARAWAY_RUNTIME_FAIL_INDEX"] = "1"
    result = transcribe(home, str(source), additions=additions)
    assert (result.returncode, result.stdout) == (1, "Պահպանված\n"), (
        "fatal transcription discarded prior text output"
    )


def test_transcribe_model_load_failure_attempts_no_jsonl_segments(
    tmp_path: Path,
) -> None:
    home = tmp_path / f"տուն-{uuid4()}"
    publish(home)
    source = audio(tmp_path, 1)
    additions = speech(tmp_path, ("Չօգտագործված",))
    additions["CARAWAY_RUNTIME_FAIL"] = "load"
    result = transcribe(home, "--format", "jsonl", str(source), additions=additions)
    records = tuple(json.loads(line) for line in result.stdout.splitlines())
    assert (result.returncode, len(records), records[0]["segments"]["total"]) == (
        1,
        1,
        0,
    ), "model load failure fabricated an attempted segment"


@pytest.mark.parametrize("value", ("HY", "hye ", "hyե", "HYE"))
def test_transcribe_rejects_malformed_language_codes(
    tmp_path: Path, value: str
) -> None:
    source = audio(tmp_path, 1)
    result = transcribe(tmp_path / f"տուն-{uuid4()}", "--source", value, str(source))
    assert (result.returncode, result.stdout) == (2, ""), (
        "malformed transcription language was accepted"
    )


def test_transcribe_rejects_an_unsupported_capability(tmp_path: Path) -> None:
    source = audio(tmp_path, 1)
    result = transcribe(
        tmp_path / f"տուն-{uuid4()}",
        "--source",
        "fra",
        str(source),
    )
    assert (result.returncode, result.stdout) == (2, ""), (
        "unsupported transcription capability was accepted"
    )


@pytest.mark.skipif(
    "CARAWAY_REAL_MODEL_CONFIG" not in os.environ,
    reason="real model smoke test is opt-in",
)
def test_transcribe_real_model_produces_useful_source_armenian(tmp_path: Path) -> None:
    result = invoke(
        tmp_path / f"տուն-{uuid4()}",
        "--config",
        os.environ["CARAWAY_REAL_MODEL_CONFIG"],
        "transcribe",
        os.environ["CARAWAY_REAL_AUDIO"],
        network=False,
    )
    assert (result.returncode, bool(result.stdout.strip())) == (0, True), (
        "real model did not produce useful Source Armenian"
    )


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
