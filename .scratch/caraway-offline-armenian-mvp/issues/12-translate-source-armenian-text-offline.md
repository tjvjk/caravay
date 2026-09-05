# 12: Translate Source Armenian text offline

**What to build:** Let a user pass Source Armenian UTF-8 text from a local file or
stdin to `caraway translate` and receive English text through the installed pinned
SeamlessM4T Large v2 backend, with predictable validation, offline execution,
output formats, and process outcomes.

**Blocked by:** 10 / Expose managed model status through a runnable CLI; 11 /
Download and publish the pinned model snapshot safely

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/3

- [x] `caraway translate [OPTIONS] [TEXT_FILE|-]` accepts at most one operand;
      omission and `-` read stdin to EOF, while omission on an interactive terminal
      is a usage error rather than a wait.
- [x] Named input must be a readable regular UTF-8 file; invalid operands fail
      before model loading with status 2 and empty stdout.
- [x] Empty input invokes no backend and returns the specified skipped text or JSONL
      result with status 4.
- [x] `--source` and `--target` use strict lowercase ISO 639-3 syntax, default to
      `hye` and `eng`, and distinguish malformed syntax from unsupported capability.
- [x] The named backend declares and validates its language-qualified text-to-text
      capability before the model is loaded; there is no implicit substitution.
- [x] The processor and text-to-text model load only from the explicit verified
      managed snapshot, with offline controls, MPS, and FP16; no working invocation
      performs network access or CPU fallback.
- [x] Missing/invalid snapshots and unavailable Apple-Silicon MPS produce the
      specified stable reason codes, status 2, stderr diagnostic, and empty stdout
      in validation order.
- [x] Default text output contains only edge-trimmed useful English text followed
      by exactly one LF; diagnostics and interactive-only progress remain on stderr,
      and `--quiet` suppresses progress only.
- [x] JSONL schema version 1 emits the specified segment and summary records,
      including ordered issue objects, aggregate counts, languages, and resolved
      backend, with status 0/1/2/3/4 matching command outcome.
- [x] Subprocess tests use a deterministic controlled backend to cover input,
      validation, offline behavior, output bytes, stderr isolation, and exits; one
      opt-in real-model smoke test demonstrates useful Armenian-to-English output.
