# Usage reference

See [README.md](README.md) for live translation, audio files, supported languages,
and installation. All examples run from the repository root. Choose `--source`
and `--target` explicitly for translation; transcription requires `--source` only.

## Saving results

Redirect output to a file, or display it and save it with `tee`:

```console
uv run caravay run --source kaz --target rus meeting.wav > translation.txt
uv run caravay run --source kaz --target rus meeting.wav | tee translation.txt
```

`>` and `tee` overwrite the destination. Use `>>` or `tee -a` to append.
Diagnostics go to stderr and are not included in these result files. For live
capture, do not add `2>&1` to the capture command: it mixes diagnostics into the
binary audio stream and corrupts the input.

## Original transcripts and JSONL

Use `--format jsonl` to save structured results, including the original
transcripts and translations:

```console
uv run caravay run --source hye --target eng --format jsonl armenian.m4a > result.jsonl
```

JSONL contains one JSON object per line, with segment outcomes and a final summary.
Live output also includes source sample positions and latency measurements:

```console
caravay-audio \
  | uv run caravay live --source hye --target eng --input-format f32le --format jsonl - \
  > live.jsonl
```

## Piped text input

Use `-` to read UTF-8 text from standard input:

```console
printf 'Բարեւ' | uv run caravay translate --source hye --target eng -
```

Omitting the text operand also reads redirected standard input. Interactive input
requires an operand or an explicit `-`.

## Configuration and model cache

The optional configuration file is
`~/Library/Application Support/caravay/config.toml`. Models are stored in
`~/Library/Caches/caravay` by default. To change the cache location:

```toml
cache_dir = "/path/to/model-cache"
```

To select a different configuration file, place `--config` before the command:

```console
uv run caravay --config /path/to/config.toml models status
```

`models status` prints `ready` when the cache is usable, `missing` when the model
has not been installed, or `invalid` when its manifest or files are inconsistent.
Run `uv run caravay models download` to install, resume an interrupted download,
or repair an invalid snapshot. Installation and repair require at least 20 GiB
of free disk space.

## Troubleshooting

| Diagnostic | Meaning and next step |
| --- | --- |
| `permission_denied` | Enable Screen & System Audio Recording permission and restart Terminal if macOS asks |
| `capture_unavailable` | ScreenCaptureKit could not supply a display; check the capture diagnostics |
| `overload` | Processing could not keep up with incoming audio; file processing may still work |
| `broken_pipe` | The downstream command closed its input; check its error output |
| `model_not_installed` | Run `uv run caravay models download` |
| `model_cache_invalid` | Run the download command again to repair the model cache |
| `mps_unavailable` | Required Metal acceleration is unavailable; check the system requirements |
| `invalid_config` | Check the selected TOML file and the setting named in the diagnostic |

Pass `--verbose` after a processing command for model-loading diagnostics.
Use `--help` to see the options for that command:

```console
uv run caravay live --help
uv run caravay run --source kaz --target rus --verbose meeting.wav > translation.txt
```
