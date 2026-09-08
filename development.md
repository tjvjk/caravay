# Development

See [README.md](README.md) for use cases, prerequisites, model installation, and
first-time macOS recording permissions. Run commands here from the repository
root.

## Compatibility and validation

The runtime uses MPS with FP16 and requires Apple Metal acceleration. It does not
fall back to CPU. Intel Macs, Windows, Linux, and CUDA are outside the current
supported configuration.

Python must be `>=3.13,<3.14`; dependency versions are pinned in `uv.lock`.
The pinned PyTorch 2.14.0 macOS wheel targets macOS 14+ on arm64. The capture
executable is maintained in [Caravay Audio](https://github.com/tjvjk/caravay-audio).
Its Swift toolchain requirements and native checks live in that repository.
`ffmpeg` is used for audio-file decoding, not native system-audio capture.

The reference computer is MacBook Pro `Mac17,7`, M5 Max, 36 GB unified memory,
macOS 26.6.2. Real-model file-processing and paced live-stream measurements exist
for this machine. This does not imply acceptance of every language pair or
system-audio capture setup. Other Apple Silicon Macs are unvalidated; neither
8 GB nor 16 GB configurations have confirmed support or live-performance results.

The selected languages are declared in the
[model card](https://huggingface.co/facebook/seamless-m4t-v2-large#supported-languages).
Recognition and translation quality still need evaluation on representative
recordings for each language.

## Python checks

Install the locked Python 3.13 environment, including development tools:

```console
uv sync --python 3.13
```

Run the same checks as CI:

```console
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy --strict src tests
uv run pytest
```

Automated tests verify all 64 combinations of the eight supported languages
through file and live processing, using controlled model outputs. They verify
language routing, not recognition or translation quality. Real-model tests are
opt-in.

## Native system-audio capture

Install `caravay-audio` separately and follow its repository's development checks.
Caravay consumes its documented PCM stream and does not build native Swift code.

## Real system-audio acceptance

This opt-in test opens ScreenCaptureKit, plays audio through `afplay`, and loads
the production model. Install `caravay-audio` on PATH, then set the six values and run:

```console
export CARAVAY_REAL_MODEL_CONFIG=/absolute/path/to/config.toml
export CARAVAY_REAL_AUDIO=/absolute/path/to/source-armenian.m4a
export CARAVAY_CAPTURE_REPORT=/absolute/path/to/capture-report.json
export CARAVAY_CAPTURE_NOTES='audible throughout; no echo or routing change'
export CARAVAY_OUTPUT_DEVICE='name shown in System Settings > Sound'
export CARAVAY_CAPTURE_PERMISSION_STATE='granted before test'
uv run pytest tests/test_system_audio_capture_acceptance.py -q
```

To use a custom executable, set `CARAVAY_AUDIO_COMMAND` to its absolute path.
The test explicitly selects Armenian input and English output. Use a known
Eastern Armenian fixture and listen during playback to confirm that capture does
not mute, reroute, or echo the source.

The JSON report records the macOS version, output device, permission state, time
to first accepted PCM, capture queue peak, termination reason, and live
translation latency/backlog measurements.

## Live audio protocol

`caravay-audio` writes only headerless little-endian Float32 mono PCM at 16 kHz
to stdout. Permission, status, overload, and broken-pipe diagnostics go to stderr.
Do not merge stderr into stdout. Capture includes the complete audible system mix
and excludes the producer's own process audio.

To exercise live processing with a paced file producer:

```console
ffmpeg -re -i armenian.wav -f f32le -ac 1 -ar 16000 pipe:1 \
  | uv run caravay live --source hye --target eng --input-format f32le -
```

Default segmentation closes speech after 600 ms of silence, caps a segment at
8 seconds, defers speech shorter than 200 ms, and allows a 30-second input backlog.
Use `--silence-ms`, `--max-segment-seconds`, `--min-segment-ms`, and
`--buffer-seconds` to adjust these bounds. A full backlog reports `overload` and
exits unsuccessfully; samples are never silently dropped. EOF finalizes remaining
speech once and discards silence.

Each text result is flushed as one line in the target language. JSONL adds source
sample positions, the source transcript, end-to-end latency, maximum backlog, and
a terminal reason (`clean_eof`, `interruption`, `overload`, or `failure`). SIGINT
cancels current processing, preserves emitted output, writes an interruption
terminal record in JSONL mode, and exits with status 130. A broken input pipe is
a failure.

On interruption, the capture producer drains accepted PCM, closes its pipe, and
exits with status 130. The downstream command sees normal EOF when only the
producer is interrupted.

## Output cleanup and model state

Speech commands reject generated `#err`/`#er` markers and hash runs of eight or
more characters. Use `--artifact-hash-threshold` after `transcribe`, `run`, or
`live` to tune the threshold from 2 through 256.

`models status` prints exactly one value:

- `ready`, exit status `0`: the managed snapshot is usable.
- `missing`, exit status `1`: it has not been installed.
- `invalid`, exit status `1`: its manifest or files are inconsistent.

Downloads use reusable temporary state, verify every published file, and replace
invalid snapshots. Configuration errors leave stdout empty, write an
`invalid_config` diagnostic to stderr, and exit with status `2`.
