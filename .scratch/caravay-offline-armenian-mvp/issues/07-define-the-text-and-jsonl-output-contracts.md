# Define the text and JSONL output contracts

Type: grilling
Status: resolved
Blocked by: 05

## Question

What information and stability guarantees belong in the MVP's final-result `text` and `jsonl` outputs, including optional source transcripts from fused backends and machine-readable errors or metadata?

## Answer

### Format selection and common rules

All three commands accept `--format text|jsonl`; `text` is the packaged default.
The option changes only stdout. The stderr and exit-status contract from issue 06
is the same for both formats, so progress and human-readable diagnostics never
make either stdout representation invalid.

Both formats are UTF-8 and use LF (`U+000A`) line endings regardless of the host
locale. Segments appear in input order. A command may emit completed segment
results before a later segment fails; consumers must use the exit status, and the
terminal JSONL record where available, to decide whether the result is complete.
Pre-processing validation failures emit no stdout in either format.

### `text`

`text` is for direct reading, redirection, and Unix pipelines. It contains only
useful final text: a source transcript for `transcribe`, and target text for
`translate` and `run`. It never contains labels, source transcripts from `run`,
metadata, warnings, placeholders for skipped segments, or error messages.

For each completed or degraded segment with useful final text, the serializer
removes only leading and trailing Unicode whitespace and writes the remaining text
followed by exactly one LF. It does not otherwise normalize Unicode, punctuation,
case, or whitespace inside the text. Empty results and skipped segments write
nothing; a value containing only Unicode whitespace is empty after trimming and
also writes nothing. Consequently, a wholly skipped command has empty stdout; a
successful or degraded command with useful output ends in one LF; and adjacent
useful segments are separated by one LF.

This deliberately makes `text` lossy with respect to segment boundaries, outcomes,
source transcripts, and diagnostics. Callers that need those distinctions must
select `jsonl`.

### `jsonl`

`jsonl` is the machine-readable contract. Each physical line is one complete,
compact JSON object followed by LF. Strings use normal JSON escaping, so generated
newlines never split a record. Records use these shapes, shown expanded only for
readability:

```json
{"schema_version":1,"type":"segment","index":0,"outcome":"completed","text":"Hello.","source_transcript":"Բարեւ։","issues":[]}
{"schema_version":1,"type":"summary","command":"run","outcome":"completed","source_language":"hye","target_language":"eng","route":"composed","backends":{"speech_to_text":"seamlessm4t-large-v2","text_to_text":"seamlessm4t-large-v2"},"segments":{"total":1,"completed":1,"degraded":0,"skipped":0,"failed":0}}
```

There is one `segment` record for every attempted segment, including skipped
segments, followed by exactly one `summary` record when command processing reaches
an orderly end. A fatal processing error uses a final summary whose `outcome` is
`failed`. An unexpected process termination may prevent that summary from being
written; the nonzero exit status remains authoritative. A command rejected before
processing has no JSONL records, as required by issue 06.

Valid empty `translate` input attempts no segments. Its JSONL output is one summary
record with outcome `"skipped"` and all five segment counts, including `total`, set
to zero. This is distinct from a non-empty segment that a backend attempts but
skips, which produces a segment record and increments `total` and `skipped`.

A segment record has these stable fields:

- `schema_version`: the integer `1`;
- `type`: `"segment"`;
- `index`: the zero-based segment index;
- `outcome`: `"completed"`, `"degraded"`, `"skipped"`, or `"failed"`;
- `text`: the useful final artifact as a string, or `null` when none exists;
- `issues`: an array of zero or more issue objects in occurrence order.

An issue object is
`{"stage": CAPABILITY, "code": CODE, "message": MESSAGE}`. `stage` is one of
`speech_to_text`, `text_to_text`, or `speech_to_text_translation`; `code` is a
stable lower-snake-case identifier such as `repetition`; and `message` is a
human-readable, non-stable explanation. A degraded, skipped, or failed record must
contain at least one issue. For a failed segment, that array contains the fatal
issue and the final summary's `error` field repeats the same issue object so both
the segment and command failure are independently machine-readable. Backend
exceptions, stack traces, local paths, prompts, token IDs, and raw generation
diagnostics are not part of stdout; implementations may report them on stderr
without changing this contract.

`source_transcript` is an optional segment field and is never a fabricated value:

- `transcribe` omits it because `text` is already the source transcript;
- composed `run` includes it as a string when the declared speech-to-text stage
  produced an artifact, including when a later stage was skipped;
- fused `run` includes it only when the selected capability declares transcript
  availability as `optional` and the backend actually returns one;
- `translate`, fused capabilities declaring transcripts `unavailable`, and stages
  that produced no transcript omit it.

The summary record has these stable fields:

- `schema_version`: the integer `1`;
- `type`: `"summary"`;
- `command`: `"transcribe"`, `"translate"`, or `"run"`;
- `outcome`: the aggregate `"completed"`, `"degraded"`, `"skipped"`, or
  `"failed"` outcome from issue 05;
- `source_language` and, for `translate` and `run`, `target_language`;
- `route`: `"composed"` or `"fused"` for `run`, omitted otherwise;
- `backends`: an object mapping every capability in the execution plan to its
  resolved backend name;
- `segments`: counts for `total`, `completed`, `degraded`, `skipped`, and
  `failed`.

A failed summary additionally includes an `error` issue object identifying the
stage and stable failure code. It describes the fatal processing failure without
repeating any successful primary text. Non-fatal segment issues remain on their
segment records and are reflected in the aggregate outcome.

### Stability and evolution

Within schema version 1, field meanings, required fields, enum values, record
ordering, zero-based indexing, and the distinction between absent, `null`, empty,
and non-empty text are stable. Implementations may add optional fields, new issue
codes, and new keys inside `backends`; consumers must ignore unknown fields and
issue codes. They must not treat the free-form `message` text as stable.

Removing or renaming a field, changing its type or meaning, changing record order,
or adding an enum value requires a new integer `schema_version`. A new version is
selected by a future explicit interface change rather than silently emitted by an
MVP update. JSON object key order is not significant, and byte-for-byte output is
not promised across model or backend versions.

The MVP intentionally does not include timestamps, durations, confidence scores,
model-internal token data, audio offsets, or a copy of the input. Their semantics
are not yet reliable enough to stabilize, and optional additive fields can carry
them later without weakening the version-1 contract.
