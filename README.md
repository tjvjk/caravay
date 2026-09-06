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
