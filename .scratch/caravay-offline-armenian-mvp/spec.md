# Caravay offline Source Armenian translation MVP

Label: ready-for-agent

## Problem Statement

The user needs a small local command-line tool that turns Eastern Armenian audio
or text into useful English text without sending working inputs to a remote
service. The repository currently contains research, a representative corpus,
and throwaway model prototypes, but no durable `caravay` command that can be
used or tested as a Unix tool.

The MVP must preserve the distinction between speech recognition and translation
even though both stages use one model family. It must make partial loss and model
repetition observable, keep primary output safe for pipes, and fail clearly when
configuration, input, hardware, or the local model snapshot is unsuitable.

## Solution

Build a macOS command-line application named `caravay` with three processing
commands:

- `transcribe` converts one local Source Armenian audio file to Source Armenian
  text;
- `translate` converts Source Armenian UTF-8 text from a file or stdin to English
  text; and
- `run` performs the explicit composed speech-to-text then text-to-text plan on
  one local audio file and returns English text.

The packaged backend is `seamlessm4t-large-v2`, backed by one immutable
`facebook/seamless-m4t-v2-large` snapshot and the task-specific speech-to-text
and text-to-text interfaces. Models are downloaded explicitly into a managed
cache, then all processing commands operate locally and offline on MPS with
FP16. Results are available as plain UTF-8 text or versioned JSONL, with stable
exit statuses and failure codes.

The first implementation is intended to make the complete CLI behavior and real
model quality testable on the reference Mac. Distribution packaging, a polished
installer, and support for additional machines are deferred.

## User Stories

1. As an Armenian speaker, I want to transcribe a local Eastern Armenian audio
   file, so that I can read its spoken content as Source Armenian text.
2. As an Armenian speaker, I want to translate Source Armenian text into English,
   so that I can understand or share it in English.
3. As an Armenian speaker, I want one command to transcribe and translate an
   audio file, so that I do not need to connect commands manually.
4. As a privacy-conscious user, I want processing commands to work without a
   network connection, so that my audio and text stay local.
5. As a first-time user, I want model acquisition to be an explicit command, so
   that a processing command never starts an unexpected multi-gigabyte download.
6. As a returning user, I want an already installed model download to succeed
   without network access, so that the command is safe and idempotent.
7. As a user, I want to see whether the model is ready, missing, or invalid, so
   that I can repair setup before processing input.
8. As a shell user, I want final text alone on stdout, so that redirection and
   pipelines remain reliable.
9. As a shell user, I want progress, warnings, and diagnostics on stderr, so that
   they never corrupt redirected results.
10. As a shell user, I want translation to read stdin until EOF, so that I can
    pipe Source Armenian text into Caravay.
11. As a shell user, I want `-` to mean text stdin, so that explicit and implicit
    stdin usage behave consistently.
12. As a user, I want a missing operand on an interactive terminal to fail rather
    than hang, so that input mistakes are obvious.
13. As a user, I want invalid URLs, directories, unreadable files, and extra
    operands rejected before model loading, so that failures are fast and clear.
14. As a user, I want UTF-8 input and output with LF line endings, so that Armenian
    and English text are portable across tools.
15. As a user, I want Source Armenian and English to be the defaults, so that the
    common commands need no language flags.
16. As a future integrator, I want language options to use strict ISO 639-3 codes,
    so that later capabilities can be added without aliases or ambiguity.
17. As a user, I want malformed language codes distinguished from unsupported
    languages, so that I know whether the syntax or backend capability is wrong.
18. As a user, I want routing validated before loading the model, so that invalid
    backend combinations fail quickly.
19. As a user, I want no implicit backend, route, device, or CPU fallback, so that
    execution remains predictable.
20. As a developer, I want backends to declare language-qualified capabilities,
    so that pipeline stages can be composed without assuming one model per stage.
21. As a developer, I want every execution plan to bind capabilities to named
    backends explicitly, so that selected behavior can be inspected and validated.
22. As a user, I want the composed `run` plan to retain its Source Armenian
    transcript, so that recognition and translation failures remain distinguishable.
23. As a user, I want later segments attempted after bounded repetition damages
    one segment, so that one difficult passage does not lose the rest of the file.
24. As a user, I want useful text before a repeated suffix retained, so that
    partial model output is not discarded unnecessarily.
25. As a user, I want a segment with useful but damaged output marked `degraded`,
    so that I can distinguish it from a clean result.
26. As a user, I want a segment with no useful output marked `skipped`, so that
    absence is explicit in machine-readable output.
27. As a shell caller, I want distinct exit statuses for completed, failed,
    invalid, degraded, and skipped commands, so that scripts can react correctly.
28. As an interactive user, I want optional progress that disappears under
    `--quiet`, so that long model operations remain understandable without making
    automation noisy.
29. As an integrator, I want one JSON object per physical line, so that results can
    be consumed incrementally.
30. As an integrator, I want one JSONL record for every attempted segment, so that
    skipped and degraded portions remain visible.
31. As an integrator, I want an orderly command to end with a summary record, so
    that completeness and aggregate outcome are machine-readable.
32. As an integrator, I want stable JSON field meanings, enums, ordering, and
    reason codes under schema version 1, so that consumers do not silently break.
33. As an integrator, I want unknown optional fields and issue codes to be
    forward-compatible, so that additive improvements do not require a new schema.
34. As a user, I want configuration to come from one predictable macOS user file,
    so that behavior does not change with the working directory.
35. As a user, I want a global configuration-file override, so that I can test or
    isolate a configuration for one invocation.
36. As a user, I want CLI values to override configured values and packaged
    defaults, so that temporary changes are explicit and local.
37. As a user, I want unknown, mistyped, unreadable, and conflicting configuration
    rejected, so that mistakes never degrade into surprising defaults.
38. As a user, I want the exact model revision pinned, so that an upstream update
    cannot silently change results.
39. As a user, I want downloads verified before publication, so that incomplete or
    corrupted weights never appear ready.
40. As a user, I want concurrent model downloads rejected safely, so that they do
    not corrupt the cache.
41. As a user, I want interrupted downloads resumable, so that already transferred
    model data is not needlessly lost.
42. As a user, I want replacement of an invalid snapshot to be atomic and
    recoverable, so that repair never destroys the last cache state silently.
43. As a user, I want missing or invalid model state diagnosed before MPS loading,
    so that first-run remediation is obvious.
44. As a user, I want unsupported hardware or unavailable MPS reported explicitly,
    so that Caravay does not run unexpectedly slowly on CPU.
45. As the MVP owner, I want the implementation measured on the reference Mac, so
    that the support promise is based on evidence rather than inference.
46. As the MVP owner, I want all 30 acceptance segments attempted without a fatal
    failure, so that the pipeline demonstrates bounded recovery.
47. As the MVP owner, I want at least 24 acceptance segments to yield useful
    English text, so that implementation behavior does not regress below the
    accepted prototype boundary.
48. As the MVP owner, I want a bilingual human to compare results with the accepted
    Large v2 baseline, so that quality is judged by meaning rather than a misleading
    automatic score.
49. As the MVP owner, I want performance, memory, and disk limits checked by a
    repeatable procedure, so that handoff readiness is measurable.

## Implementation Decisions

- A backend advertises language-qualified `speech_to_text`, `text_to_text`, and/or
  `speech_to_text_translation` capabilities. Capabilities are operations rather
  than backend classes or assumptions about model count.
- An execution plan is an explicit ordered cascade of compatible capabilities,
  each bound to a named backend. The complete plan is validated before model
  loading. Caravay never infers a route or substitutes a backend at runtime.
- The MVP advertises Source Armenian (`hye`) as its only source and English
  (`eng`) as its only translation target.
- The packaged backend name is `seamlessm4t-large-v2`. It supplies Source Armenian
  speech-to-text and Source Armenian-to-English text-to-text using the task-specific
  SeamlessM4T Large v2 interfaces on MPS with FP16.
- The required `run` route is composed. Its transcript boundary remains observable
  even though both stages share a backend and model family. Direct fused
  speech-to-English is not the packaged route.
- The CLI forms are `caravay transcribe [OPTIONS] AUDIO_FILE`, `caravay translate
  [OPTIONS] [TEXT_FILE|-]`, and `caravay run [OPTIONS] AUDIO_FILE`.
- `transcribe` and `run` accept exactly one readable local regular audio file.
  They do not accept URLs, directories, stdin, or multiple operands.
- `translate` accepts at most one readable UTF-8 regular file. A missing operand or
  `-` reads stdin until EOF, except that missing input on an interactive terminal
  is a usage error. Empty text is valid and yields a skipped command without
  invoking the backend.
- `--source` and `--target` accept exactly three lowercase ASCII letters. Defaults
  are `hye` and `eng`; syntax and capability failures are distinct validation
  diagnostics.
- Backend and route resolution order is CLI option, configured value, then
  packaged default. Composed and fused route-specific options are mutually
  exclusive, and selecting a fused route requires an explicit fused backend.
- Segment outcomes are `completed`, `degraded`, `skipped`, and `failed`. A later
  successful stage cannot improve an earlier degraded outcome. A skipped stage
  without an artifact prevents dependent downstream invocation.
- Backend-specific guards detect cyclic generation and remove its repeating suffix.
  A useful remaining artifact is degraded with stable reason `repetition`; no
  useful artifact is skipped. Neither outcome prevents later segments from being
  attempted. A fatal failure stops the command.
- Aggregate outcome is completed only when every segment completes; degraded when
  useful final output exists but any segment degraded or skipped; skipped when no
  useful final output exists without a fatal failure; and failed after a fatal
  processing failure.
- Exit statuses are `0` completed, `1` failed or unexpected operational failure,
  `2` argument/input/configuration/capability/environment validation failure, `3`
  degraded, and `4` skipped.
- `--format text|jsonl` selects stdout representation; text is the default. All
  output is UTF-8 with LF endings. Progress and diagnostics go only to stderr;
  progress is interactive-only and `--quiet` suppresses progress but not warnings
  or errors.
- Text output contains only useful final text: Source Armenian for `transcribe`,
  English for `translate` and `run`. Each useful segment is trimmed only at its
  Unicode edges and ends with exactly one LF. Skipped and empty results emit
  nothing.
- JSONL schema version 1 emits one compact segment record per attempted segment in
  input order and one terminal summary after orderly processing. A pre-processing
  validation failure emits no JSONL. Valid empty translation emits only a skipped
  zero-count summary.
- A segment record includes schema version, type, zero-based index, outcome, text
  or null, and ordered issues. Degraded, skipped, and failed records have at least
  one issue containing stage, stable lower-snake-case code, and unstable human
  message.
- A composed `run` segment includes `source_transcript` when speech-to-text produced
  it. The field is omitted for `transcribe`, `translate`, unavailable fused
  transcripts, and stages with no transcript. Caravay never fabricates it.
- A summary includes command, aggregate outcome, languages, resolved backends,
  segment counts, and route for `run`. A failed summary repeats the fatal issue as
  `error`. Exit status remains authoritative if termination prevents a summary.
- Schema version 1 permits new optional fields, issue codes, and backend keys.
  Removing, renaming, retyping, changing meaning or record order, or adding an enum
  value requires a new explicitly selected schema version.
- The optional strict TOML configuration is at
  `~/Library/Application Support/caravay/config.toml`; `--config PATH` selects a
  different file. There is no project-local or XDG configuration search.
- The config permits an optional managed cache directory and optional per-command
  backend/route bindings. Backend names select packaged definitions; arbitrary
  model repositories and revisions cannot be configured.
- The packaged model is `facebook/seamless-m4t-v2-large` at immutable revision
  `5f8cc790b19fc3f67a61c105133b20b34e3dcb76`. A Caravay release, never an automatic
  refresh, changes this revision.
- The default managed cache root is `~/Library/Caches/caravay`. A shared Hugging
  Face cache entry is not by itself an installed Caravay snapshot.
- A ready snapshot has a manifest identifying the backend, repository, revision,
  expected files, byte sizes, and cryptographic digests. Download publication
  verifies full digests; normal startup verifies manifest identity, presence, and
  sizes without rehashing multi-gigabyte weights.
- `caravay models download` is the only operation allowed to fetch model data. It
  uses a per-snapshot lock, resumable temporary state on the destination filesystem,
  full verification, and atomic publication. It never damages an existing ready
  snapshot and recovers interrupted invalid-snapshot quarantine state.
- `models download` returns 0 with no stdout when successful. An already ready
  snapshot succeeds without network or the 20 GiB free-space prerequisite.
  Concurrent download and other download failures use stable codes
  `download_in_progress` and `download_failed` and return 1.
- `caravay models status` performs local startup verification and emits exactly
  `ready`, `missing`, or `invalid` plus LF. Ready returns 0; missing and invalid
  return 1. Model-management JSON is outside the MVP.
- Working commands resolve the model to an explicit managed local path, enable
  Hugging Face offline controls, and use local-files-only loading. They never
  download, update, probe a repository, repair a cache, fall back to CPU, or select
  another runtime.
- Before model loading, working commands validate in order: arguments/config file,
  input/complete plan, managed snapshot, then Apple-Silicon MPS availability. The
  first failure stops validation and leaves stdout empty.
- Stable setup reason codes are `invalid_config`, `model_not_installed`,
  `model_cache_invalid`, and `mps_unavailable`; they return 2. Missing-model help
  directs the user to `caravay models download`.
- The validated support target is MacBook Pro `Mac17,7`, Apple M5 Max, 36 GB
  unified memory, macOS 26.6.2, Python `>=3.13,<3.14`, PyTorch 2.14.0, and
  Transformers 5.16.1. Other environments are unvalidated rather than known
  incompatible.
- The current performance targets derive from prototype results on Python 3.11.16.
  They are not evidence that Python 3.13 has passed acceptance.

## Testing Decisions

- Tests assert externally observable behavior rather than internal functions,
  model classes, or collaborator calls. Refactoring internal modules must not
  require contract-test changes while CLI behavior remains the same.
- The single public test seam is invocation of `caravay` as a separate process.
  Tests observe arguments, stdin, stdout, stderr, exit status, local filesystem and
  network effects, resource measurements, and produced text/JSONL.
- Fast behavior tests invoke the CLI with a deterministic controlled test backend.
  This exercises validation, routing, outcome aggregation, repetition handling,
  serialization, configuration, and cache-state behavior without loading the
  multi-gigabyte production model.
- Full acceptance invokes the same CLI seam with the real pinned
  `seamlessm4t-large-v2` backend and the existing five-minute Source Armenian
  corpus split into 30 fixed ten-second segments. The network is disabled.
- Existing throwaway SeamlessM4T prototypes and their saved outputs are prior art
  for model invocation, segmentation, timing, peak RSS measurement, and the
  accepted quality baseline. They are evidence, not production modules or the
  test interface.
- Acceptance uses the latest Python 3.13 patch release and records its exact
  version and dependency lock. It runs three times in new processes with no other
  heavy workload. Filesystem caches are not flushed.
- Composed inference RTF excludes model loading and uses the median of three runs;
  it must be at most 0.25. Application-cold load time is the worst of three and
  must be at most 15 seconds. Application-cold means the process has not loaded
  the processor or model.
- Worst peak process RSS across the three runs must be at most 12 GiB. The ready
  snapshot must be at most 10 GiB. Starting/resuming a download or preparing a
  replacement requires at least 20 GiB free, and successful publication retains
  no second complete model copy.
- All 30 corpus segments must be attempted with no failed outcome or unexpected
  termination. At least 24 must produce useful final English text as completed or
  degraded, at most six may be skipped, and no raw cyclic suffix may reach final
  output.
- Fixed-version repeated runs must produce identical segment outcomes and text.
- A reviewer fluent in Source Armenian and English compares all 30 results with
  the accepted Large v2 prototype baseline. There may be no new material loss of
  meaning or raw cyclic repetition. Reviewer, date, per-segment decisions, and
  notes are retained; any unresolved judgment fails acceptance.
- Fast subprocess tests run regularly during implementation. The relevant single
  behavior test is run after every vertical slice, typechecking runs regularly,
  and the complete fast suite runs once at the end. The real-model acceptance suite
  is a handoff gate rather than a per-slice test.

## Out of Scope

- Distribution packaging, a polished installer, signing, notarization, Homebrew,
  standalone application bundling, automated updates, and uninstall behavior.
- Claiming that the MVP has passed Python 3.13 acceptance before that run occurs.
- Support promises for Macs other than the exact reference configuration, or for
  Windows, Linux, Intel Macs, CPU inference, CUDA, or non-MPS devices.
- Western Armenian, source languages other than `hye`, and required targets other
  than English.
- Russian output beyond opportunistic evaluation.
- Direct/fused speech-to-English as the packaged route or automatic route fallback.
- Arbitrary Hugging Face models, user-supplied repositories/revisions, multiple
  production backends, forced reinstall, cache removal, and automatic model update.
- Live microphone or system-audio capture, audio stdin, VAD, streaming, partial
  results, subtitles, TTS, timestamps, confidence scores, and batch directories.
- Project-local configuration, XDG configuration lookup, JSON model-management
  output, and machine-stable human diagnostics.
- Commercial use under the selected model's CC-BY-NC-4.0 license. Commercial use
  requires reopening model selection.
- Treating automatic subtitles as ground-truth quality labels or introducing an
  automatic quality score without a curated reference corpus.

## Further Notes

- The model route was chosen after comparing SeamlessM4T Medium, SeamlessM4T Large
  v2, generic Whisper Large v3 Turbo, and an Armenian Whisper Medium fine-tune.
  Large v2 was the most useful accepted route despite known bounded repetition.
- The Python 3.11.16 prototype measured composed RTF 0.157, peak RSS 8.99 GiB,
  application-cold model loading about 10.71 seconds, and a local model cache about
  8.6 GiB. Acceptance limits deliberately include headroom over those observations.
- The selected model license is acceptable only for the present personal/research,
  non-commercial MVP.
- This specification is ready to split into tracer-bullet implementation tickets.
  Packaging can be specified later without blocking hands-on CLI testing.
