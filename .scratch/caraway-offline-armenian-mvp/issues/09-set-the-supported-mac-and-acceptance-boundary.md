# Set the supported Mac and acceptance boundary

Type: grilling
Status: resolved
Blocked by: 04

## Question

Using the reference-Mac measurements and human judgments, what quality, reliability, latency, memory, disk, and hardware boundary must the implementation satisfy for the MVP specification to be considered ready for handoff?

## Answer

### Supported environment

The MVP has one validated hardware and operating-system target:

- MacBook Pro `Mac17,7`;
- Apple M5 Max;
- 36 GB unified memory;
- macOS 26.6.2;
- PyTorch 2.14.0 and Transformers 5.16.1 on MPS with FP16;
- Python `>=3.13,<3.14`.

Other Apple-Silicon Macs and other software versions are unvalidated, not known
to be incompatible. They are outside the support promise until the complete
acceptance run passes on them. Acceptance uses the latest available Python 3.13
patch release and records its exact version and dependency lock in the report.

The prototype measurements below were collected with Python 3.11.16. They set
the acceptance targets but do not demonstrate that the Python 3.13 runtime has
passed. A Python 3.13 acceptance run remains required before implementation
handoff; this ticket does not perform it.

### Fixed acceptance workload

Acceptance processes the existing five-minute conversational Source Armenian
corpus as 30 fixed ten-second segments through the required composed Source
Armenian speech-to-text then English text-to-text plan using the pinned
`facebook/seamless-m4t-v2-large` snapshot from issue 08. The installed model is
used locally with the network disabled.

Each performance result comes from three full runs in new processes with no
other heavy workload on the reference Mac. The input, segmentation, model
revision, and dependency lock remain identical. Reported composed real-time
factor is the median of the three runs. Application-cold model-load time and
peak process RSS are the worst observed values. Application-cold means that the
process has not loaded the processor or model; the procedure does not flush the
macOS filesystem cache.

### Quality and reliability

The implementation passes the corpus boundary when:

- all 30 segments are attempted and none has a `failed` outcome or terminates
  the process unexpectedly;
- at least 24 segments produce useful final English text with a `completed` or
  `degraded` outcome, so at most six are `skipped`;
- cyclic suffixes are removed from final text and exposed through the
  `repetition` outcome semantics defined in issue 05;
- repeated runs with the fixed versions produce the same segment outcomes and
  text; and
- a reviewer fluent in Source Armenian and English judges all 30 results to be
  no worse than the accepted Large v2 prototype baseline: there are no new
  material losses of meaning and no raw cyclic repetitions.

The reviewer name, date, per-segment decisions, and brief notes are retained in
the acceptance report. An unresolved judgment on any segment means acceptance
has not passed. Known recognition errors and bounded repetition remain allowed
when the result is still at least as useful as the accepted baseline and the
segment is classified according to issues 05–07.

### Resource and performance limits

The composed `run` command must satisfy all of these limits:

- median end-to-end inference RTF, excluding model loading: at most `0.25`;
- worst application-cold model-load time: at most 15 seconds;
- worst peak process RSS: at most 12 GiB;
- ready managed model snapshot: at most 10 GiB;
- free disk required before starting or resuming a download, or preparing a
  replacement publication: at least 20 GiB; the ready-snapshot idempotent path
  from issue 08 does not require this free space; and
- after successful publication, the managed cache retains no second complete
  copy of the model.

The limits include deliberate headroom over the Python 3.11.16 prototype, which
measured 0.157 composed RTF, 8.99 GiB peak RSS, and an 8.6 GiB local model cache.
They become evidence of implementation readiness only when the complete
procedure above passes under Python 3.13 on the supported environment.
