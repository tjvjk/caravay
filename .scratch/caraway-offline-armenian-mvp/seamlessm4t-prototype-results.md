# SeamlessM4T Medium prototype results

Question: are direct speech-to-English and Armenian ASR followed by text
translation useful on the reference Apple-Silicon Mac, and which runtime path
is reliable enough for the MVP?

## Setup

- MacBook Pro `Mac17,7`, Apple M5 Max (18 cores), 36 GB RAM, macOS 26.6.2.
- Corpus: the full five-minute `WncDNZDeWr0` Eastern Armenian excerpt.
- Model: `facebook/hf-seamless-m4t-medium`, revision
  `ecf60d4df63baaac3f82ae6a7ad7adcb19dcb26c`, CC-BY-NC-4.0.
- Python 3.11.16, PyTorch 2.14.0, Transformers 5.16.1,
  SentencePiece 0.2.2, protobuf 7.36.1, ffmpeg 9.0.1.
- Ten-second fixed chunks; greedy generation defaults.

The current Transformers processor accepts `audio=`, not the `audios=` shown
in the model card. The unified `SeamlessM4TModel` rejects Armenian as a target
even for text-only generation, so the working path uses the documented
task-specific `SeamlessM4TForSpeechToText` and
`SeamlessM4TForTextToText` classes.

## Measurements

| Route | MPS time for 300 s | MPS real-time factor | CPU real-time factor (10 s control) |
| --- | ---: | ---: | ---: |
| Direct speech to English | 9.35 s | 0.031 | 0.132 |
| Armenian ASR + text translation | 24.15 s | 0.081 | 0.680 |

Model load took 8.70 seconds. Peak process RSS was 6.28 GiB. All 30 MPS
chunks completed without a runtime failure. The CPU/FP32 control produced the
same text as MPS/FP16 on the first chunk, so the observed repetitions are not
an MPS numerical artifact.

## Quality verdict

Direct speech-to-English is not useful enough for the MVP. It frequently
collapses into repeated generic phrases and loses concrete details. Examples
include repeating “this part” at 10–20 s and “we're going to take the village”
at 170–180 s.

The ASR-then-translation route is more useful and inspectable. It preserves
several topics and details that the direct route loses, including the priest,
incense and smoke story; the Golden Autumn concert; the grandmother's
superstitions; and not cutting nails at night. It still has material ASR errors,
hallucinated names, and occasional long repetitions. It is therefore the
better SeamlessM4T Medium route for further comparison, but it does not clear a
reasonable quality bar for the MVP on this corpus.

## Runtime verdict

The reliable supported runtime path is PyTorch/Transformers on MPS with FP16,
using the two task-specific classes and roughly ten-second chunks. CPU/FP32 is
a functional but substantially slower fallback. Runtime viability does not
rescue SeamlessM4T Medium's quality: task 04 should compare or reject the model
route rather than adopt direct speech translation as the MVP default.

Raw primary-source outputs are in `results/seamlessm4t/`.
