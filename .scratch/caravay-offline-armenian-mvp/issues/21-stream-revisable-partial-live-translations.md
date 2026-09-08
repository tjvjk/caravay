# 21: Stream revisable partial live translations

**What to build:** Add an opt-in live presentation mode that emits revisable
partial Source Armenian transcripts and English translations while an utterance is
still open, then replaces them with one authoritative final result after the
utterance closes. Preserve the longer audio context needed for final quality rather
than forcing short final segments to obtain faster output.

**Blocked by:** 18 / Translate a live PCM stream from stdin; 19 / Mark damaged
composed segments

**Status:** needs-triage
**State:** open

_This ticket changes the current live output contract, under which stdout contains
only immutable final results. Implementation requires an explicit decision about
interactive terminal rendering and a machine-readable partial-event contract._

## Evidence

With the first five minutes of `I2Iivo9wSew`, reducing the live maximum segment
duration from eight seconds to three seconds made output arrive more frequently but
materially reduced usefulness. Observed failures included split sentences,
`Yang Yang`, repeated `Armenian Armenian`, implausible short phrases, and additional
generation artifacts. A streaming mode should therefore obtain responsiveness from
revisable hypotheses while retaining approximately six to eight seconds of context
for the final pass.

The packaged SeamlessM4T backend currently invokes blocking `generate()` calls on a
fixed audio candidate. Transformers text streamers can expose decoder output after
generation begins, but they do not turn this backend into an online audio encoder.
The bounded initial design is repeated inference over snapshots of the growing
utterance; a genuinely chunk-stateful speech backend remains a separate capability.

- [ ] `caravay live` exposes an explicit partial-results option; the default mode
      retains its current immutable LF-delimited text and JSONL contracts.
- [ ] An open speech candidate is snapshotted at a configurable interval whose
      initial default is between 750 and 1,000 ms, without closing or shortening
      the candidate solely to produce a partial result.
- [ ] One inference worker serializes MPS work. Its pending queue coalesces obsolete
      snapshots and keeps only the newest partial request, while the capture queue
      retains the existing rule that audio samples are never silently dropped.
- [ ] Every partial inference runs the composed Source Armenian ASR and
      Armenian-to-English route over the current utterance snapshot; a partial
      result is explicitly provisional and may revise any previously displayed
      word from that utterance.
- [ ] Silence, maximum duration, EOF, interruption, overload, and fatal failure
      retain deterministic finalization semantics. A closing utterance receives
      one authoritative final inference over its complete accepted audio before a
      later utterance is finalized.
- [ ] Interactive text presentation updates one provisional terminal line in
      place and commits exactly one LF-terminated final English result. Terminal
      control bytes are emitted only when the partial presentation mode is
      explicitly selected on a compatible interactive output.
- [ ] Machine-readable output represents partial and final events separately and
      gives each utterance a stable identifier plus a monotonically increasing
      revision. Consumers can deterministically replace an earlier revision and
      identify the single authoritative final event.
- [ ] Partial ASR and translation generation artifacts are filtered before display
      using the existing guards. A damaged partial remains provisional; final
      outcome, issues, summary counts, and exit status are derived only from the
      authoritative final attempt.
- [ ] Backpressure policy distinguishes expendable partial snapshots from source
      audio and final work. Slow inference may reduce partial update frequency but
      cannot reorder final results, conceal accumulated audio backlog, or prevent
      the existing overload failure.
- [ ] Partial inference is skipped until enough voiced audio exists to produce a
      useful hypothesis, and identical consecutive visible hypotheses are not
      emitted as new revisions.
- [ ] Fast tests use controlled audio frames, clocks, and backends to cover periodic
      snapshots, snapshot coalescing, hypothesis replacement, stable revision
      ordering, duplicate suppression, finalization during in-flight partial work,
      artifacts, EOF, overload, failure, and non-interactive output rejection.
- [ ] An opt-in acceptance run on the first five minutes of `I2Iivo9wSew` records
      time to first useful partial, partial update intervals, final-result latency,
      maximum audio backlog, partial inference count, coalesced snapshot count, and
      final output for bilingual review.
- [ ] On the reference Mac, median time to first useful partial is at most two
      seconds and sustained processing completes without overload. If inference is
      slower than the configured update interval, measurements demonstrate bounded
      coalescing rather than an unbounded work queue.
- [ ] The same accepted final audio boundaries processed with partial mode enabled
      and disabled produce equivalent final outcomes and materially equivalent
      English according to bilingual review; transient partial mistakes do not
      replace or degrade the authoritative final result.
- [ ] Supporting a chunk-stateful realtime speech model is represented as a new
      backend capability or adapter at the streaming seam, rather than adding
      model-specific state management to the CLI or live presentation code.

