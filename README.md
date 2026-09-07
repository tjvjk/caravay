# Caraway

Caraway is a development CLI for offline Source Armenian language processing on
macOS. It explicitly downloads its pinned managed model, transcribes Source
Armenian audio, and translates Source Armenian text to English without network
access during processing.

## Development setup

Install the locked Python 3.13 environment and run the command through `uv`:

```console
uv sync --python 3.13
uv run caraway models download
uv run caraway models status
```

Audio decoding requires `ffmpeg` on `PATH`.

## First-time macOS system-audio setup

The system-audio producer is a small native Swift executable. It uses Apple's
ScreenCaptureKit directly: no BlackHole, Loopback, virtual audio device, or other
capture utility is required. The producer needs macOS 13 or newer.

Install Apple's Command Line Tools once. They contain the Swift compiler, Swift
Package Manager, macOS SDK, and `swift-format`:

```console
xcode-select --install
swift --version
xcrun --sdk macosx --show-sdk-version
```

If `xcode-select --install` says the tools are already installed, that is fine.
You do not need the full Xcode application for this command-line package. Install
the Python and audio prerequisites with Homebrew if they are not already present:

```console
brew install uv python@3.13 ffmpeg
uv sync --python 3.13
```

`uv` creates the repository-local Python environment used by `caraway` and
installs the locked dependencies. `ffmpeg` is needed by Caraway's finite-file
audio commands; the native live-capture producer itself does not use it. Download
the offline translation model once (this is the large, networked setup step):

```console
uv run caraway models download
uv run caraway models status
```

Build the Swift producer from the repository root:

```console
swift build -c release --package-path native/SystemAudioCapture
```

The executable is then at:

```text
native/SystemAudioCapture/.build/release/caraway-capture
```

On its first real launch, macOS asks for **Screen & System Audio Recording**
permission. Approve `caraway-capture` (or the Terminal application that launched
it) under **System Settings → Privacy & Security → Screen & System Audio
Recording**. If macOS asks you to restart Terminal, do that and run the command
again. The executable captures the complete audible system mix, excludes its own
process audio, and never requests microphone access.

Start the complete live translation pipeline:

```console
native/SystemAudioCapture/.build/release/caraway-capture \
  | uv run caraway live --input-format f32le -
```

Then play a meeting, browser video, or media file normally. Audio remains audible
through the selected macOS output device while Caraway prints English lines. Stop
with `Ctrl-C`. The producer drains PCM it has already accepted, closes the pipe,
and exits with status 130; the downstream `caraway live` command sees normal EOF.

The pipe is intentionally binary on the left: `caraway-capture` writes only
headerless little-endian Float32 mono PCM at 16 kHz to stdout. All permission,
status, overload, and broken-pipe messages go to stderr. Do not redirect stderr
into stdout (`2>&1`), because that would corrupt the PCM stream.

For development, use the debug build and run the fast native-process tests:

```console
swift build --package-path native/SystemAudioCapture -Xswiftc -warnings-as-errors
xcrun swift-format lint --recursive native/SystemAudioCapture/Sources \
  native/SystemAudioCapture/Package.swift
uv run pytest tests/test_system_audio_capture.py -q
```

Fast tests use a debug-only controlled capture adapter and never open the privacy
prompt. A release build does not contain that adapter. If capture fails:

- `permission_denied` means permission is absent; enable it in System Settings and
  restart the launching terminal if requested;
- `capture_unavailable` means ScreenCaptureKit could not supply a display;
- `overload` means the consumer stopped draining fast enough; no PCM was silently
  dropped;
- `broken_pipe` means the downstream command closed its input.

The real end-to-end acceptance is opt-in because it opens ScreenCaptureKit, plays
audio through `afplay`, and loads the production model. Set the six values and run:

```console
export CARAWAY_REAL_MODEL_CONFIG=/absolute/path/to/config.toml
export CARAWAY_REAL_AUDIO=/absolute/path/to/source-armenian.m4a
export CARAWAY_CAPTURE_REPORT=/absolute/path/to/capture-report.json
export CARAWAY_CAPTURE_NOTES='audible throughout; no echo or routing change'
export CARAWAY_OUTPUT_DEVICE='name shown in System Settings > Sound'
export CARAWAY_CAPTURE_PERMISSION_STATE='granted before test'
uv run pytest tests/test_system_audio_capture_acceptance.py -q
```

The JSON report records the macOS version, named output device, permission state,
time to first accepted PCM, capture queue peak, termination reason, and live
translation latency/backlog measurements. Run this only with a known Source
Armenian fixture and listen during playback to confirm that capture does not mute,
reroute, or echo the source.

The status command prints exactly one value:

- `ready` with exit status `0` when the managed snapshot is usable;
- `missing` with exit status `1` when it has not been installed; or
- `invalid` with exit status `1` when its manifest or files are inconsistent.

The default optional configuration file is:

```text
~/Library/Application Support/caraway/config.toml
```

Without that file, Caraway uses `~/Library/Caches/caraway` as its managed cache.
To select another configuration file for one invocation, place `--config` before
the command:

```console
uv run caraway --config /path/to/config.toml models status
```

A minimal configuration can change the managed cache location:

```toml
cache_dir = "~/Library/Caches/caraway"
```

Configuration errors leave stdout empty, write an `invalid_config` diagnostic to
stderr, and exit with status `2`. Downloads use reusable temporary state, verify
every published file, and safely replace invalid snapshots.

Translate a UTF-8 file or piped text after downloading the model:

```console
uv run caraway translate armenian.txt
printf 'Բարեւ' | uv run caraway translate -
```

Transcribe one local audio file into ordered Source Armenian text:

```console
uv run caraway transcribe armenian.wav
uv run caraway transcribe --format jsonl armenian.m4a
```

Each completed audio segment is flushed to stdout as soon as it is ready.
Speech commands reject generated `#err`/`#er` markers and hash runs of eight or
more characters. Use `--artifact-hash-threshold` after `transcribe`, `run`, or
`live` to tune the hash-run threshold from 2 through 256.

Run the explicit composed speech-to-text and text-to-text plan to produce English
while retaining Source Armenian transcripts in JSONL output:

```console
uv run caraway run armenian.wav
uv run caraway run --format jsonl armenian.m4a
```

Translate live raw PCM from a paced producer without changing the finite-file
commands:

```console
ffmpeg -re -i armenian.wav -f f32le -ac 1 -ar 16000 pipe:1 | uv run caraway live --input-format f32le -
```

Live input is little-endian Float32 mono PCM at 16 kHz. The defaults close speech
after 600 ms of silence, cap a segment at 8 seconds, defer speech shorter than
200 ms, and allow a 30-second bounded input backlog. The corresponding options
can tune those timing bounds without changing language or backend routing. A full
backlog is reported as `overload` and exits unsuccessfully; samples are never
silently dropped. EOF finalizes remaining speech once and discards silence.

Each text result is flushed as one English line. JSONL adds source sample positions,
the Source Armenian transcript, end-to-end latency, maximum backlog, and a terminal
reason (`clean_eof`, `interruption`, `overload`, or `failure`). SIGINT cancels the
current work, preserves already emitted output, writes an interruption terminal
record in JSONL mode, and exits with status 130. A broken input pipe is a failure.

Backend diagnostics are hidden by default; pass `--verbose` after a processing
command to inspect model-loading details.
