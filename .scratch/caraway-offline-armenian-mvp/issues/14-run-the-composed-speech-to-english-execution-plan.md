# 14: Run the composed speech-to-English execution plan

**What to build:** Let a user run the complete Source Armenian audio-to-English
workflow as one command while retaining the declared transcript boundary,
validating explicit routing, and propagating segment outcomes across both stages.

**Blocked by:** 12 / Translate Source Armenian text offline; 13 / Transcribe a local
Source Armenian audio file

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/5

- [x] `caraway run [OPTIONS] AUDIO_FILE` applies the same local-file, language,
      preloading validation, offline MPS/FP16, progress, and output-channel rules as
      the completed component commands.
- [x] The packaged default is an explicit composed plan binding Source Armenian
      speech-to-text and Armenian-to-English text-to-text to
      `seamlessm4t-large-v2` while preserving the transcript artifact.
- [x] CLI, configured, and packaged route/backend values resolve independently in
      that order, and the complete language-qualified execution plan is validated
      before loading either model.
- [x] Composed and fused route options are mutually exclusive; a fused route
      requires an explicit/configured capable backend, and the MVP never infers,
      substitutes, or falls back to one.
- [x] Each useful Source Armenian transcript is passed to translation; a skipped
      speech-to-text segment does not invoke translation, and later success cannot
      improve an earlier degraded outcome.
- [x] Repetition, skipped artifacts, fatal failures, later-segment continuation,
      aggregate outcomes, and exit statuses follow the shared pipeline semantics.
- [x] Text output contains only useful ordered English results and follows the
      exact whitespace/LF contract.
- [x] JSONL segment records include `source_transcript` only when the composed
      speech-to-text stage produced one, and the terminal summary reports the route,
      both capability bindings, languages, outcome, and counts.
- [x] The command produces deterministic output and outcomes for fixed input,
      backend, model revision, and dependency lock.
- [x] Subprocess tests exercise composed success and every outcome transition,
      routing/config conflicts, unsupported fused selection, transcript presence,
      output bytes, stderr isolation, and statuses using a controlled backend.
- [x] An opt-in real-model smoke test translates a short Source Armenian audio
      fixture to useful English through the same CLI seam without network access.
