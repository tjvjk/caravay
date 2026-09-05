# 16: Strengthen cyclic generation detection

**What to build:** Prevent long model-generated repetition from reaching
transcription output when punctuation or a repeating multi-word phrase hides the
cycle from the current exact-suffix guard.

**Blocked by:** 13 / Transcribe a local Source Armenian audio file

**Status:** ready-for-agent

- [ ] Repetition detection compares normalized tokens so trailing punctuation does
      not make otherwise identical repetitions appear different.
- [ ] The guard detects repeated n-grams as well as a single repeated word,
      including cycles that reach the configured generation limit.
- [ ] Detection does not normalize or rewrite retained output; it preserves the
      original useful prefix exactly apart from the existing Unicode-edge trimming.
- [ ] A detected cycle is removed from final text and produces a degraded segment
      with reason `repetition` when useful prefix text remains.
- [ ] A detected cycle with no useful prefix produces a skipped segment with reason
      `repetition` and does not prevent later segments from being attempted.
- [ ] Ordinary grammatical repetition remains intact unless it crosses the bounded
      cyclic-generation threshold.
- [ ] Subprocess regression tests cover punctuation variants and repeated Armenian
      examples shaped like `տատիկին`, `նայեք`, and `մինա`, plus multi-word cycles.
- [ ] The fixed five-minute Source Armenian corpus emits none of the observed raw
      cyclic suffixes while retaining useful text before each cycle.

