# Generic Whisper Armenian STT prototype results

Research date: 2026-09-04

## Question

Is generic Whisper Large v3 Turbo a useful offline Eastern Armenian STT
baseline on the reference Apple-Silicon Mac?

## Setup

- Model: `mlx-community/whisper-large-v3-turbo`, revision
  `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`, unquantized, 1.61 GB.
- Runtime: `mlx-whisper` 0.4.3 / MLX 0.32.2.
- Machine and corpus: the same M5 Max, 36 GB Mac and five-minute Eastern
  Armenian excerpt used for SeamlessM4T.
- Forced `language="hy"`, `task="transcribe"`.

## Measurements

The cached no-context run processed 300 seconds in 43.66 seconds including
model loading (RTF 0.146) and used 1.76 GiB peak RSS. The first run with word
timestamps took 95.48 seconds including the initial model download and used
2.37 GiB peak RSS.

## Quality verdict

Generic Large v3 Turbo is not useful for this corpus. With Whisper's default
`condition_on_previous_text=True`, an early decoding failure propagated into
long repetitions across later windows. Disabling previous-text conditioning
prevented cross-window propagation but did not make the transcription usable.
Both runs contain extensive repetitions, English hallucinations, mixed Latin,
Korean, Hebrew, and malformed Armenian text despite forcing Armenian.

This rejects only the generic Turbo checkpoint. It does not reject
Armenian-fine-tuned Whisper checkpoints such as
`ArthurYeghinyan/whisper-hy-am-asr-v2`, nor generic Whisper Large v3, whose
decoder differs from Turbo and would require its own run.

Raw results are in `results/whisper/`. The executable spike is in
[`prototypes/whisper/`](../../prototypes/whisper/).
