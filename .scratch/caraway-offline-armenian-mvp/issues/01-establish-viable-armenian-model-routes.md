# Establish the viable Armenian model routes

Type: research
Status: resolved

## Question

Which current open-source models can locally translate Eastern Armenian speech or text into English or Russian, particularly through a single model, and what execution paths are plausible on Apple Silicon?

## Answer

SeamlessM4T Medium is the best-supported first candidate: one 1.2B multitask model exposes Armenian ASR, Armenian-to-English/Russian speech-to-text translation, and text-to-text translation. Official sources do not establish direction-specific quality or Apple-Silicon latency, so it requires an acceptance prototype. Whisper is a useful English-only control and MMS plus NLLB is a two-model fallback.

Full findings: [Armenian speech translation models for a local Apple-Silicon MVP](../../mt-language-pipeline/research/armenian-speech-translation-models.md)

