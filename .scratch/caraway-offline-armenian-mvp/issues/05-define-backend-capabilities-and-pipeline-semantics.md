# Define backend capabilities and pipeline semantics

Type: grilling
Status: resolved

## Question

How should `caraway` represent ASR, text translation, and fused speech translation capabilities so `transcribe`, `translate`, and `run` compose predictably without assuming either one model per stage or an intermediate transcript?

## Answer

### Capabilities and backend bindings

A backend declares any combination of these language-qualified capabilities:

- `speech_to_text(source=hye)`
- `text_to_text(source=hye, target=eng)`
- `speech_to_text_translation(source=hye, target=eng)`

These are operations, not backend classes or model-count assumptions. One backend
may provide multiple capabilities and may share a loaded model or other resources
between them. The MVP advertises only Source Armenian (`hye`) as input and English
(`eng`) as the translation target.

An execution plan is an explicit ordered cascade of capability invocations, each
bound to a named backend. Before loading models or processing input, the pipeline
validates that every backend declares its assigned capability and that adjacent
artifact types and languages match. An invalid plan is a configuration error;
there is no implicit route selection, runtime fallback, or automatic substitution.

### Command semantics

- `transcribe` requires `speech_to_text` and produces a source transcript.
- `translate` requires `text_to_text` and produces target text.
- `run` accepts either an explicit `speech_to_text` → `text_to_text` cascade or
  one explicit `speech_to_text_translation` invocation and produces target text.

The MVP `run` plan is the two-step SeamlessM4T Large v2 cascade selected in issue
04. Even though both steps use the same backend and model family, the backend must
not collapse them: the transcript is an observable artifact at the declared plan
boundary.

A fused capability does not imply a transcript. It declares transcript availability
as `optional` or `unavailable`; `speech_to_text` declares it `required`. The pipeline
never invents a transcript and does not require one from a fused `run` plan.

### Outcomes and failures

Processing reports one outcome per independently recoverable segment:

- `completed`: the requested transformation completed without known loss;
- `degraded`: useful output exists, but some input or generated output was lost;
- `skipped`: no useful output exists, but processing may continue;
- `failed`: execution cannot continue.

Backend-specific generation guards detect cyclic repetition. They remove the
repeating suffix and report the segment as `degraded` with reason `repetition` when
useful text remains. In a composed `run`, that useful transcript is still passed to
translation. If nothing useful remains, the segment is `skipped`. Neither outcome
triggers fallback or prevents later segments from being attempted; a `failed`
outcome stops the command. If an earlier stage succeeded before a later failure,
its artifact remains available for diagnostics.

Within one segment, a later successful stage cannot improve an earlier outcome:
translation of a `degraded` transcript leaves the segment `degraded`. A `skipped`
speech-to-text stage has no artifact to translate, so the pipeline does not invoke
the downstream text-to-text stage for that segment.

For input containing multiple segments, the command outcome is:

- `completed` when every segment completes;
- `degraded` when useful final output exists but any segment was degraded or skipped;
- `skipped` when no useful final output exists and no fatal failure occurred;
- `failed` when execution was stopped by a fatal failure.

Output serialization and presentation of artifacts, reasons, and diagnostics belong
to issue 07. Segmentation, VAD, live input, streaming, and partial-result APIs remain
outside the MVP; these outcome semantics merely avoid preventing those extensions.
