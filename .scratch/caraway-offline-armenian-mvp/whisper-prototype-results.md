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

## Armenian Medium fine-tune follow-up

`ArthurYeghinyan/whisper-hy-am-asr-v2` revision
`308044aafb7843f255ff678dc799aa5c1863da49` was tested through Transformers
5.16.1 and PyTorch 2.14.0 on MPS/FP16. Its inference checkpoint occupies 2.8 GB
in the local Hub cache; the model card does not declare a license.

The model processed 300 seconds in 131.37 seconds of inference (RTF 0.438),
loaded in 5.66 seconds, and used 4.67 GiB peak RSS. Unlike generic Turbo, it
consistently emitted Armenian script and recovered recognizable details on
many chunks. It nevertheless entered obvious single-token repetition on 8 of
30 fixed ten-second chunks. Large v2 did so on 6 of 30 under the same simple
four-consecutive-token detector and ran its ASR at 0.085 RTF.

The fine-tune is useful evidence that Armenian-specific training matters, but
this checkpoint is not the MVP choice: it is slower than Seamless Large v2,
loops more often on this corpus, and has no declared license. Human review may
still find its non-looping Armenian transcript more accurate, so retain the raw
output as a comparison source.

Raw results are in `results/whisper/`. The executable spikes are in
[`prototypes/whisper/`](../../prototypes/whisper/) and
[`prototypes/whisper-finetune/`](../../prototypes/whisper-finetune/).
