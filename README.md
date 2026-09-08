# Caravay

Caravay captures system audio on macOS and translates speech into text as you
listen. Use it with meetings, browser videos, or any other playing audio. Once
the model is downloaded, processing works offline.

## Live translation of system audio

After the [first-time setup](#installation-and-first-run), start capture and
translation from the repository root:

```console
caravay-audio \
  | uv run caravay live --source hye --target eng --input-format f32le -
```

This translates Armenian speech into English text. Play your meeting or video
normally: audio remains audible through the selected output device, and Caravay
prints each translated segment as it becomes ready. Stop with `Ctrl-C`.

To display the live translation and save it to a text file at the same time:

```console
caravay-audio \
  | uv run caravay live --source hye --target eng --input-format f32le - \
  | tee translation.txt
```

Capture includes the complete audible system mix, so other playing apps can also
be translated. Microphone access and virtual audio devices are not required.

Always choose both `--source` and `--target`; there are no default languages or
automatic language detection. See [supported languages](#supported-languages).

## Audio files

Audio files can be processed much faster than real time: Caravay processes the
recording without waiting for it to play. Actual speed depends on your Mac, the
recording, and the selected languages; the first run also includes model loading.

Translate speech from a local audio file and save the result:

```console
uv run caravay run --source kaz --target rus meeting.wav > translation.txt
```

For transcription in the original language, only `--source` is needed:

```console
uv run caravay transcribe --source kaz meeting.wav > transcript.txt
```

## Text translation

Translate a UTF-8 file and save the result:

```console
uv run caravay translate --source hye --target eng armenian.txt > english.txt
```

Remove `> filename` from these examples to print the result in the terminal.
`>` and `tee` overwrite an existing file; use `>>` or `tee -a` to append.
See [usage.md](usage.md) for piped input and JSONL output with original transcripts.

## Supported languages

These languages are available for incoming audio and outgoing text, and for text
translation:

| Language | Code |
| --- | --- |
| Eastern Armenian (Yerevan) | `hye` |
| Kazakh | `kaz` |
| Russian | `rus` |
| English | `eng` |
| German | `deu` |
| Turkish | `tur` |
| French | `fra` |
| Spanish | `spa` |

## System requirements

- Mac with Apple Silicon and macOS 14 or newer.
- At least 20 GiB free for model installation; the model cache uses about 9 GiB.
- Python 3.13 and `ffmpeg`; live system capture also needs
  [Caravay Audio](https://github.com/tjvjk/caravay-audio).

Tested on **MacBook Pro, M5 Max, 36 GB memory, macOS 26.6.2**.
Other Apple Silicon Macs may work, but minimum memory and live-processing speed
have not been verified on them.

## Installation and first run

Run these commands from the repository root on a Mac meeting the
[system requirements](#system-requirements).

### 1. Install prerequisites

Install Python and the other prerequisites with Homebrew:

```console
brew install uv python@3.13 ffmpeg
uv sync --python 3.13
```

### 2. Download the model

This is the large download needed before offline processing:

```console
uv run caravay models download
uv run caravay models status
```

Status should be `ready`. If installation was interrupted or the cache is invalid,
run the download command again.

### 3. Install system-audio capture

Install [Caravay Audio](https://github.com/tjvjk/caravay-audio) following its README.
It is a separate Swift project with its own build, tests and installation.
Confirm the command is on PATH:

```console
caravay-audio --version
```

### 4. Start live translation and allow capture

Run the live translation command above. On the first launch, macOS asks for
**Screen & System Audio Recording** permission. Approve `caravay-audio` (or its
launching Terminal app) under **System Settings → Privacy & Security → Screen &
System Audio Recording**. Restart Terminal if macOS requests it, then run the
command again and play your audio.

## Help with startup

- If recording permission is denied, enable it in macOS settings and restart
  Terminal if asked.
- If the model is missing or invalid, run `uv run caravay models download` again.
- If processing reports `overload`, your Mac is not keeping up with live audio.
  File processing may still work.

Use `--help` for command options and `--verbose` for additional diagnostics.

See [usage.md](usage.md) for configuration, output formats, and error details,
or [development.md](development.md) for development and testing.
