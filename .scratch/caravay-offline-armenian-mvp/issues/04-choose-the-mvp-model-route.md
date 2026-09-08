# Choose the MVP model route

Type: grilling
Status: resolved
Blocked by: 03

## Question

Given the prototype's human quality ratings, failure modes, latency, memory use, and model footprint, which model and direct or composed route should the MVP specification require, and is a fallback comparison necessary before committing?

## Answer

The MVP specification requires `facebook/seamless-m4t-v2-large` through a
composed pipeline:

1. Source Armenian speech → Source Armenian text with
   `SeamlessM4Tv2ForSpeechToText`.
2. Source Armenian text → English text with
   `SeamlessM4Tv2ForTextToText`.

The intermediate transcript is part of the pipeline boundary. This supports
the standalone `transcribe` and `translate` commands and makes recognition and
translation failures independently observable. Direct speech-to-English is
not the MVP route.

The prototype's current quality is accepted for the MVP. Repetition on
difficult chunks is a known limitation rather than a selection blocker; later
pipeline semantics must define how cyclic generation is detected and reported.
Large v2 completed all 30 ten-second MPS/FP16 chunks, ran ASR plus translation
at 0.157 RTF, and used 8.99 GiB peak RSS on the reference M5 Max Mac.

No additional fallback-model comparison is required before committing to the
MVP specification. The model's CC-BY-NC-4.0 license is acceptable because the
current MVP is explicitly personal/research and non-commercial. Commercial use
would require reopening the model-selection decision.
