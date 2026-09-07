# 25: Introduce a speech backend seam and Whisper adapter

**What to build:** Replace the singleton SeamlessM4T speech implementation with a
small capability-driven backend interface, preserve SeamlessM4T behind one adapter,
and add `openai/whisper-large-v3` behind a second adapter. A caller must be able to
select either packaged backend without knowing its processor, language tokens,
generation options, files, or damage-detection rules.

**Blocked by:** 24 / Translate multilingual live speech directly to English

**Status:** ready-for-agent
**State:** open

_This ticket creates an in-process extension seam for packaged speech models. It
does not implement runtime plugin discovery, arbitrary user-supplied Hugging Face
repositories, remote inference, speaker diarization, or a generic abstraction over
every possible machine-learning task._

## Context

The current backend is structurally a singleton. `settings.py` defines one backend
literal, repository, and revision; `models.py` owns one fixed file inventory; and
`runtime.py` directly imports and operates SeamlessM4T classes. The nominal runtime
protocol therefore exposes the current implementation rather than a stable speech
interface. Adding Whisper through conditionals in those modules would spread
model-specific knowledge across configuration, download, routing, execution, and
tests.

Two real adapters now justify a seam. The intended shape is:

```text
CLI / execution / live segmentation
              |
       Speech backend interface
          /             \
 SeamlessM4T adapter   Whisper adapter
```

Whisper provides multilingual speech recognition, spoken-language identification,
and direct speech-to-English translation. The multilingual `large-v3` checkpoint
is selected because Whisper `turbo` is not trained for translation and may return
source-language text for the translate task.

## Interface direction

The exact Python types may evolve during implementation, but the external seam
must remain no larger than the following concepts:

```python
SpeechRequest(
    operation="transcribe" | "translate_to_english",
    source_language="hye" | "auto",
)

SpeechResult(
    outcome=...,
    text=...,
    detected_language=...,
    language_confidence=...,
    issues=...,
)
```

Loading is performed once from a validated local snapshot. The adapter accepts
normalized 16 kHz mono Float32 samples and returns data; it does not parse CLI
arguments, write stdout/stderr, segment live audio, download files, or construct
JSONL.

## Acceptance criteria

- [ ] A backend registry defines each packaged backend's stable name, immutable
      Hugging Face repository and revision, required file inventory, disk-space
      requirement, supported capabilities, language policy, and adapter factory.
      Adding a backend does not require editing unrelated command execution logic.
- [ ] `Backend` and configuration validation accept at least
      `seamlessm4t-large-v2` and `whisper-large-v3`. Unknown names and unsupported
      capability/language combinations fail before model loading with the existing
      stable validation style.
- [ ] The speech backend interface accepts one normalized request plus audio and
      returns one normalized result. Model-specific processor calls, decoder
      prompts, language-code conversion, token limits, confidence extraction, and
      generation cleanup remain inside the selected adapter.
- [ ] The existing SeamlessM4T speech implementation moves behind an adapter
      satisfying the new interface. Its Source Armenian ASR and direct
      speech-to-English behavior, outcomes, ordering, offline execution, and
      observable output do not regress.
- [ ] A Whisper adapter loads a pinned `openai/whisper-large-v3` snapshot locally
      through `WhisperProcessor` and `WhisperForConditionalGeneration` using the
      project's pinned Transformers runtime and supported MPS precision.
- [ ] Whisper `transcribe` produces source-language text for an explicitly
      supported source language. Whisper `translate_to_english` accepts an
      unspecified/automatic source language and produces English text. No target
      other than English is advertised for Whisper speech translation.
- [ ] Caraway's canonical ISO 639-3 codes are mapped to and from Whisper's language
      tokens inside the Whisper adapter, including at least `hye`/`hy`, `rus`/`ru`,
      and `eng`/`en`. Unsupported or unmapped codes are rejected rather than
      silently treated as English.
- [ ] When Whisper performs automatic language identification, the adapter returns
      the detected canonical language and an available confidence/probability.
      Fixed-language requests do not pretend that a language was detected.
- [ ] The direct multilingual live route from issue 24 can select Whisper with an
      invocation equivalent to
      `caraway live --route fused --backend whisper-large-v3 --target eng --input-format f32le -`
      without changes to capture, VAD, buffering, segment ordering, or terminal
      presentation.
- [ ] Consecutive finalized live segments may contain different languages and are
      independently identified and translated by Whisper. Detecting or correctly
      transcribing a language change inside one finalized segment remains outside
      scope and is documented as such.
- [ ] Backend-specific generation guards live behind the adapter seam. Existing
      SeamlessM4T artifact and repetition handling remains intact; Whisper handles
      at least hallucination on silence/low-evidence audio, repetition, empty
      output, and low-confidence language identification without leaking raw model
      tokens into normal output.
- [ ] Generic execution maps adapter results into the existing completed,
      degraded, skipped, and failed outcomes. It does not branch on a backend name
      to interpret processor output or model diagnostics.
- [ ] Text output remains only useful final text. JSONL records the selected
      backend and operation, omits unavailable source transcripts, and includes
      detected-language metadata only when the adapter actually produced it. Any
      incompatible change to schema-version-one fields uses an explicitly selected
      new schema version.
- [ ] `caraway models status` reports every packaged backend independently, and
      `caraway models download BACKEND` downloads only the selected immutable
      snapshot. Verification, locking, staging, quarantine recovery, and atomic
      publication work per backend rather than relying on SeamlessM4T globals.
- [ ] Required-file inventories come from the selected backend definition. A valid
      snapshot for one backend cannot satisfy, invalidate, quarantine, or overwrite
      another backend's snapshot.
- [ ] The model manager preserves the rule that runtime commands are offline and
      only an explicit model-download command accesses the network. Repository,
      revision, sizes, and cryptographic digests are captured in each published
      manifest.
- [ ] Configuration can bind different compatible backends to speech recognition,
      direct speech translation, and text translation. An invalid composition is
      rejected by capabilities; Whisper is never selected for `text_to_text`.
- [ ] Fast contract tests exercise the same speech-backend interface against
      controlled SeamlessM4T and Whisper adapters, plus an in-memory fake used by
      execution tests. Tests assert normalized behavior through the interface and
      keep library-specific assertions inside adapter tests.
- [ ] Fast subprocess tests cover backend selection, missing and invalid snapshots,
      unsupported capabilities, ISO-code mapping, fixed and automatic language
      requests, Whisper ASR, Whisper direct English translation, structured
      provenance, and preservation of existing SeamlessM4T defaults.
- [ ] Opt-in acceptance runs the same Armenian, Russian, and English single-language
      segment fixture through both direct backends. It records useful English,
      detected language where available, time to first result, per-segment latency,
      peak MPS memory, maximum live backlog, and every degraded/skipped result.
- [ ] The acceptance report explicitly compares Whisper `large-v3` with
      SeamlessM4T Large v2 rather than assuming interchangeability. Whisper is not
      made a packaged default until bilingual quality and reference-Mac resource
      measurements justify a separate product decision.
- [ ] Contributor documentation gives one worked example of adding a hypothetical
      third packaged speech model. The example requires a backend definition,
      adapter, adapter contract tests, pinned snapshot metadata, and capability
      declaration, but no edits to live segmentation or command result rendering.

## Non-goals

- Loading `openai/whisper-large-v3-turbo` for speech translation.
- Using Whisper as a text-to-text translator.
- Holding Whisper and SeamlessM4T in memory simultaneously unless an explicitly
  selected composed route requires both and passes a separate resource budget.
- Carrying Whisper decoder prompts across finalized live segments in the first
  implementation; this avoids stale-language and hallucinated-context bleed.
- Guaranteeing identical output or issue codes across fundamentally different
  model implementations.
- Selecting a backend automatically based on audio content.

## Comments

