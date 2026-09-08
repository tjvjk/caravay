# 24: Translate multilingual live speech directly to English

**What to build:** Add an explicit live route that sends each finalized speech
segment directly through SeamlessM4T Large v2 speech-to-text translation and emits
English text. Successive segments may contain different supported source
languages; the user does not select a source language and Caravay does not claim
to detect or report one.

**Blocked by:** 18 / Translate a live PCM stream from stdin; 19 / Mark damaged
composed segments

**Status:** ready-for-agent
**State:** open

_This ticket supports language changes between finalized segments. Detecting or
faithfully transcribing multiple languages inside one segment is explicitly out
of scope. Source-language identification, confidence reporting, and source
transcripts are also outside its scope._

## Context

The current live route is fixed to Source Armenian speech-to-text followed by
Armenian-to-English text translation:

```text
speech --ASR(hye)--> Armenian transcript --T2TT(hye, eng)--> English
```

That route cannot follow a meeting that switches from Armenian to Russian,
English, or another supported language. SeamlessM4T Large v2 also supports direct
speech-to-text translation: audio features do not require a source-language token,
while generation is constrained to the requested target language. The desired
route is therefore:

```text
supported speech --S2TT(target=eng)--> English
```

This is distinct from issue 20. Issue 20 retains the composed Armenian route and
uses direct translation only as a guarded retry for a damaged segment. This ticket
makes direct translation an independently selected primary route for every live
segment.

## Acceptance criteria

- [ ] `caravay live --route fused --target eng --input-format f32le -` selects
      multilingual speech input and English text output without requiring or
      implying a source language. An explicitly supplied `--source` conflicts
      with this route. Omitting `--route` retains the existing composed `hye` to
      `eng` route and its backward-compatible defaults.
- [ ] The direct route accepts the same paced headerless little-endian Float32 mono
      16 kHz stdin contract, segmentation settings, bounded buffering, ordering,
      flushing, EOF, interruption, and overload behavior as composed live mode.
- [ ] Every finalized segment is passed once to the pinned
      `facebook/seamless-m4t-v2-large` speech-to-text generation implementation
      with English (`eng`) as the target. It does not run Source Armenian ASR,
      text-to-text translation, language identification, or speculative inference
      across multiple source languages.
- [ ] The execution-plan interface represents composed and fused plans as distinct
      validated variants. A fused plan binds one `speech_to_text_translation`
      capability and cannot accidentally load or call the composed ASR and text
      translation stages.
- [ ] The packaged backend advertises direct speech-to-English as a
      language-qualified capability over its documented set of supported speech
      inputs. Unsupported target languages and conflicting composed/fused options
      fail validation before model loading.
- [ ] A meeting may switch source language at a finalized segment boundary without
      restarting Caravay or changing flags. Each segment is translated to English
      independently and remains in source-audio order.
- [ ] Mixed-language speech within a single finalized segment has no correctness
      guarantee in this version. The documentation states this limitation and
      does not describe the route as language detection or attach a guessed source
      language to its output.
- [ ] Direct text output contains only useful English, with the same LF and flush
      behavior as existing live text output. It contains no source-language label,
      fabricated source transcript, model token, or rejected generation artifact.
- [ ] Direct JSONL segments identify the selected fused route and omit
      `source_transcript`. Their language metadata distinguishes a multilingual or
      unspecified source policy from a detected language; it must not serialize
      `hye` merely because that is the composed-route default. Any incompatible
      change to required schema-version-one fields uses an explicitly selected
      new schema version.
- [ ] Generation-artifact, repetition, empty-output, failure, degraded/skipped
      outcome, aggregate count, diagnostic, and exit-status rules apply directly
      to the English candidate. There is no downstream stage whose result can hide
      or improve direct generation damage.
- [ ] The direct route reuses one loaded model snapshot and does not load duplicate
      weights for unused composed stages. Startup time, peak memory, per-segment
      latency, and live backlog are measured against the existing composed route.
- [ ] Fast tests use controlled backends and audio segments to cover plan
      validation, fused-only model loading, direct invocation arguments, ordered
      language changes between segments, artifact filtering, empty output,
      failure, JSONL provenance, EOF, SIGINT, overload, and rejection of option
      conflicts.
- [ ] An opt-in acceptance fixture contains consecutive single-language utterances
      in at least Source Armenian, Russian, and English, with segment boundaries
      between language changes. One live session produces useful ordered English
      for all three without a source-language option or restart.
- [ ] A bilingual reviewer evaluates meaning for every acceptance utterance. The
      acceptance record includes the exact source languages and boundaries as
      fixture knowledge, but the runtime output does not claim to have detected
      them.

## Non-goals

- Identifying the source language or returning a language confidence.
- Producing an Armenian, Russian, or other source-language transcript.
- Detecting a language transition and splitting an already open speech segment.
- Guaranteeing correct translation when two languages occur inside one segment.
- Automatically falling back between fused and composed routes.
- Changing the source-language policy of `transcribe` or `translate`.

## Comments
