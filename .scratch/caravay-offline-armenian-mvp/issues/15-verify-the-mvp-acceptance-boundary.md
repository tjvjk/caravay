# 15: Verify the MVP acceptance boundary

**What to build:** Provide and execute a reproducible acceptance procedure for the
complete `caravay run` workflow on the reference Mac, retaining machine-readable
measurements and a human-review record that together determine whether the MVP is
ready for implementation handoff.

**Blocked by:** 14 / Run the composed speech-to-English execution plan

**Status:** ready-for-agent

- [ ] Acceptance records the exact latest Python 3.13 patch release, PyTorch
      2.14.0, Transformers 5.16.1, dependency lock, pinned model revision, input,
      segmentation, and supported reference-Mac identity.
- [ ] The fixed five-minute conversational Source Armenian corpus is processed as
      30 ten-second segments through the packaged composed route with the network
      disabled and no other heavy workload.
- [ ] Three full runs occur in new processes without flushing the macOS filesystem
      cache, and the retained report distinguishes median inference RTF from worst
      application-cold load time and peak process RSS.
- [ ] Median composed inference RTF excluding model loading is at most 0.25, worst
      application-cold model loading is at most 15 seconds, and worst peak process
      RSS is at most 12 GiB.
- [ ] The ready snapshot is at most 10 GiB, download/replacement free-space behavior
      enforces the 20 GiB boundary, and successful publication retains no second
      complete model copy.
- [ ] Every run attempts all 30 segments with no failed outcome or unexpected
      termination; at least 24 yield useful completed/degraded English text, at
      most six are skipped, and no raw cyclic suffix reaches final output.
- [ ] All fixed-version runs produce identical segment outcomes and text.
- [ ] A reviewer fluent in Source Armenian and English compares every result with
      the accepted Large v2 prototype baseline and records name, date, per-segment
      decisions, and notes.
- [ ] Human review finds no new material loss of meaning or raw cyclic repetition;
      any unresolved segment prevents acceptance.
- [ ] The complete fast subprocess suite and typechecking pass before the real-model
      runs, and the acceptance report identifies every unmet criterion rather than
      claiming readiness prematurely.

