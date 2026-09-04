# 13: Transcribe a local Source Armenian audio file

**What to build:** Let a user transcribe one local Source Armenian audio file into
ordered Source Armenian text, continuing across independently recoverable segments
and exposing bounded model repetition without corrupting stdout.

**Blocked by:** 10 / Expose managed model status through a runnable CLI; 11 /
Download and publish the pinned model snapshot safely; 12 / Translate Source
Armenian text offline

**Status:** ready-for-agent

- [ ] `caraway transcribe [OPTIONS] AUDIO_FILE` requires exactly one readable local
      regular file and rejects a missing operand, extra operands, directories, URLs,
      and `-` before model loading.
- [ ] The command accepts `--source`, rejects `--target`, defaults to `hye`, and
      validates syntax and the backend's Source Armenian speech-to-text capability.
- [ ] Audio is decoded and processed as ordered, independently recoverable
      approximately ten-second segments through the pinned task-specific
      speech-to-text model on offline MPS/FP16.
- [ ] Generation guards remove cyclic suffixes. Useful retained text yields a
      degraded segment with reason `repetition`; no useful text yields skipped;
      neither prevents later segments from being attempted.
- [ ] A fatal segment failure stops processing, preserves already emitted results,
      and produces the specified failed exit and terminal JSONL summary when an
      orderly end remains possible.
- [ ] Aggregate completed, degraded, skipped, and failed outcomes and exit statuses
      follow the specification across multi-segment audio.
- [ ] Text output contains only ordered useful Source Armenian segment text with
      exact whitespace/LF semantics and no placeholders, labels, or diagnostics.
- [ ] JSONL emits one record for every attempted segment and a summary with source
      language, backend binding, and complete outcome counts; transcribe records do
      not duplicate text in a `source_transcript` field.
- [ ] Subprocess tests cover audio operand validation, segment continuation,
      repetition truncation, partial output, failure, serialization, and exits with
      a deterministic controlled backend.
- [ ] An opt-in real-model smoke test transcribes a short fixture through the same
      CLI seam without network access.

