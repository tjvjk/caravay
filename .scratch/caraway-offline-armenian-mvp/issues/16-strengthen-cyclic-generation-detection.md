# 16: Strengthen cyclic generation detection

**What to build:** Prevent long model-generated repetition from reaching
transcription output when punctuation or a repeating multi-word phrase hides the
cycle from the current exact-suffix guard.

**Blocked by:** 13 / Transcribe a local Source Armenian audio file

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/6

- [x] Repetition detection compares normalized tokens so trailing punctuation does
      not make otherwise identical repetitions appear different.
- [x] The guard detects repeated n-grams as well as a single repeated word,
      including cycles that reach the configured generation limit.
- [x] Detection does not normalize or rewrite retained output; it preserves the
      original useful prefix exactly apart from the existing Unicode-edge trimming.
- [x] A detected cycle is removed from final text and produces a degraded segment
      with reason `repetition` when useful prefix text remains.
- [x] A detected cycle with no useful prefix produces a skipped segment with reason
      `repetition` and does not prevent later segments from being attempted.
- [x] Ordinary grammatical repetition remains intact unless it crosses the bounded
      cyclic-generation threshold.
- [x] Subprocess regression tests cover punctuation variants and repeated Armenian
      examples shaped like `տատիկին`, `նայեք`, and `մինա`, plus multi-word cycles.
- [x] The fixed five-minute Source Armenian corpus emits none of the observed raw
      cyclic suffixes while retaining useful text before each cycle.

## Comments

### 2026-09-06 implementation verification

Ran the packaged backend offline on the fixed five-minute corpus with
`caraway --quiet transcribe --format jsonl`. All 30 segments were attempted:
23 completed, 7 degraded for `repetition`, 0 skipped, and 0 failed. The observed
raw `ծխի`, `ոսկե`, `նայեք`, and `մինա` cyclic suffixes were absent,
while the useful text preceding each detected cycle was retained.
