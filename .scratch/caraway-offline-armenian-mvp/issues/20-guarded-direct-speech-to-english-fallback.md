# 20: Recover damaged segments with guarded direct translation

**What to build:** Optionally retry a composed live segment damaged by generation
artifacts through direct speech-to-English, validate that candidate, and select it
only when it is structurally usable. Retain the Armenian transcript and declare
which route supplied the selected English text.

**Blocked by:** 19 / Mark damaged composed segments

**Status:** needs-triage

_This ticket reopens the MVP decision that the packaged route is exclusively
composed and direct speech-to-English is out of scope. Implementation requires an
explicit product decision allowing direct inference as a bounded recovery path._

## Evidence

On the same 39 `I2Iivo9wSew` segment boundaries, direct speech-to-English reduced
`#err` from 29 markers across 20 segments to 10 markers across eight segments and
materially improved the introduction. It also generated one 256-character hash run
and one cyclic sentence. Against imperfect YouTube English captions, direct won 18
pairwise comparisons, composed won 16, and four were effectively tied; unconditional
replacement is therefore unsupported.

- [ ] Direct recovery is an explicit configurable live policy and never runs for a
      healthy composed segment.
- [ ] A damaged segment is retried at most once using its exact source sample range
      and the already loaded speech model; recovery does not load a duplicate model.
- [ ] Direct output passes the generation-artifact and repetition guards from issue
      19 before it can be selected.
- [ ] The selection rule is deterministic and structural: usable direct English is
      selected over damaged composed English, while a rejected direct candidate
      falls back to useful marker-free composed English or no output.
- [ ] Recovery cannot improve the segment outcome above `degraded`, because its
      retained Source Armenian transcript remains damaged.
- [ ] A recovery failure is bounded and nonfatal unless the primary composed route
      has already failed fatally; later segments remain ordered and are attempted.
- [ ] Text output exposes only the selected useful English and no rejected direct
      candidate or artifact marker.
- [ ] JSONL retains `source_transcript` and adds optional schema-version-one fields
      for recovery attempt outcome, selected route, and stable selection reason.
- [ ] Diagnostics identify rejected recovery on stderr without contaminating
      stdout; summary counts and exit status retain the degraded segment outcome.
- [ ] Fast subprocess tests cover no retry for healthy output, successful recovery,
      rejected markers, rejected hash runs, rejected cycles, both candidates
      unusable, recovery failure, ordered continuation, JSONL provenance, and text
      output.
- [ ] A deterministic comparison tool replays identical stored segment boundaries
      through composed and direct routes and reports candidate damage and selection
      without treating automatic YouTube captions as ground truth.
- [ ] Opt-in acceptance on all 39 `I2Iivo9wSew` boundaries records both candidates
      and the selected output. No marker, long hash run, or detected cycle reaches
      text output, no segment fails fatally, and a bilingual reviewer records every
      material gain or loss against composed output.

