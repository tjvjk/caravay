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

Run the explicit composed speech-to-text and text-to-text plan to produce English
while retaining Source Armenian transcripts in JSONL output:

```console
uv run caraway run armenian.wav
uv run caraway run --format jsonl armenian.m4a
```

Backend diagnostics are hidden by default; pass `--verbose` after a processing
command to inspect model-loading details.
