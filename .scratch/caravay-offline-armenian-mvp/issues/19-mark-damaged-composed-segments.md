# 19: Mark damaged composed segments

**What to build:** Keep the composed Armenian-speech-to-English route and extend
its generation guards so recognizable error artifacts cannot pass as completed
text. Preserve useful Armenian content, translate its marker-free form, and make
the damage observable as a degraded segment.

**Blocked by:** 18 / Translate a live PCM stream from stdin

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caravay/pull/7

## Evidence

On the first five minutes of `I2Iivo9wSew`, the same 39 live segment boundaries
produced 29 `#err` markers across 20 Armenian transcripts. The composed translator
copied those markers into English, and all affected segments were incorrectly
reported as completed. Five-, eight-, and ten-second maximum durations produced
respectively 7.75, 7.03, and 7.37 markers per 1,000 recognized Armenian characters;
adding surrounding audio context did not repair a reproducible code-switched
“ride hailing” example. Output guards, rather than segmentation tuning, are the
bounded correction for this ticket.

- [x] Armenian speech recognition treats standalone `#err` and `#er`, including
      punctuation-adjacent forms, as generation artifacts before transcript or
      translation text is exposed.
- [x] A configurable bounded run of `#` characters is a generation artifact; the
      threshold rejects the observed 256-character run without damaging ordinary
      prose containing a single hash or hashtag.
- [x] Existing cyclic-generation detection remains authoritative for repeated
      phrases, and every artifact type follows the same completed/degraded/skipped
      outcome semantics.
- [x] A damaged transcript with useful Armenian text retains its original text in
      `source_transcript`, including artifact markers, and has outcome `degraded`.
- [x] Artifact markers are removed from the text passed to composed translation
      without joining surrounding words or rewriting the remaining Armenian text.
- [x] A damaged transcript with no useful Armenian text is `skipped` and does not
      invoke text translation.
- [x] A successful downstream translation cannot improve an upstream degraded
      outcome to completed.
- [x] Text output exposes only useful marker-free English. Raw artifact markers
      and rejected cyclic suffixes never reach stdout.
- [x] JSONL reports stable issue code `generation_artifact` at stage
      `speech_to_text`, preserves the damaged source transcript, and needs no new
      required schema-version-one fields.
- [x] Diagnostics stay on stderr; summary counts and exit status include affected
      useful segments as degraded and artifact-only segments as skipped.
- [x] Healthy Armenian transcripts, literal single `#` characters, and ordinary
      grammatical repetition retain their current text and completed outcomes.
- [x] Fast subprocess tests cover each marker form, punctuation adjacency, useful
      prefix/suffix preservation, artifact-only output, long hash runs, healthy
      hashes, cyclic phrases, downstream outcome propagation, ordered continuation,
      text output, JSONL, diagnostics, and exit statuses.
- [ ] Opt-in acceptance on the first five minutes of `I2Iivo9wSew` attempts all 39
      stored segment boundaries without a fatal failure, exposes no raw generation
      artifact in English text, and reports every affected segment as degraded or
      skipped rather than completed.
