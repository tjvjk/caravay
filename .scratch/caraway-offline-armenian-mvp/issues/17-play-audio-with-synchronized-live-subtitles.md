# 17: Play local audio with synchronized live subtitles

**What to build:** Add an interactive post-MVP mode that plays one local Source
Armenian audio file while displaying each recognized Source Armenian segment as a
subtitle aligned with the corresponding playback position.

**Blocked by:** 13 / Transcribe a local Source Armenian audio file; 16 / Strengthen
cyclic generation detection

**Status:** needs-triage

_Reopens the current MVP decision that playback, timestamps, and subtitles are out
of scope. This ticket must not expand the acceptance boundary of issues 13–15
unless the MVP specification is deliberately revised._

- [ ] The CLI exposes an explicit interactive playback mode rather than changing
      the pipe-safe behavior of `caraway transcribe`.
- [ ] The mode accepts exactly one readable local regular audio file and retains
      the existing rejection of URLs, directories, stdin, and extra operands.
- [ ] Audio playback and subtitle presentation use the same ordered segmentation
      timeline, with explicit start and end positions for every displayed segment.
- [ ] A subtitle appears no later than its corresponding playback interval when
      recognition is fast enough; slow recognition has a documented deterministic
      policy such as pausing playback or presenting the subtitle late.
- [ ] Completed and degraded useful transcripts are displayed; skipped segments
      show no fabricated text, and fatal failures stop playback with a diagnostic.
- [ ] Repetition guards run before subtitle presentation so raw cyclic generation
      is never displayed.
- [ ] Playback controls define at least start, pause/resume, interruption, and
      orderly termination behavior.
- [ ] Normal stdout remains safe for automation; interactive rendering and
      diagnostics use an explicitly selected terminal/UI channel.
- [ ] Temporary decoded audio and playback resources are released after success,
      failure, or user interruption.
- [ ] Tests use a deterministic controlled clock, playback boundary, and speech
      backend to cover synchronization, late recognition, pause/resume, skipped
      segments, fatal failure, and interruption without using real speakers.
- [ ] An opt-in acceptance test plays a short local Source Armenian fixture on the
      reference Mac and records subtitle timing drift and operator observations.

