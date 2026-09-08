# Local Language Pipeline

This context describes `caravay`, a local CLI for transforming spoken or written language through composable processing stages.

## Language

**Pipeline**:
A composition of optional input, speech recognition, translation, and output stages. A pipeline describes observable transformations, not how many models implement them.
_Avoid_: Live translator, meeting translator

**Backend**:
A replaceable implementation that performs one or more adjacent pipeline stages. A backend may use a stage-specific model or a fused model that translates speech directly.
_Avoid_: Engine, adapter, model

**Fused backend**:
A backend that performs speech recognition and translation as one operation, without exposing an intermediate transcript as a required boundary.
_Avoid_: One-stage pipeline, live model

**Capability**:
A language-qualified transformation a backend declares it can perform: speech to text, text to text, or fused speech to translated text. A fused capability also declares whether a source transcript is optional or unavailable; speech to text always provides one.
_Avoid_: Backend type, model type

**Execution plan**:
An explicit ordered cascade of capabilities, each bound to a backend, whose adjacent inputs, outputs, and languages are compatible. Its boundaries determine which intermediate artifacts are observable.
_Avoid_: Automatic route, implicit fallback

**Segment outcome**:
The result of processing one independently recoverable portion of input: completed, degraded with useful output, skipped without useful output, or failed. A degraded or skipped outcome does not by itself prevent later portions from being processed.
_Avoid_: Chunk status, generation status

**Source Armenian**:
Eastern Armenian as commonly spoken in Yerevan, identified by the language code `hye`. Western Armenian is a distinct, unsupported source variant for the MVP.
_Avoid_: Armenian when the variant is ambiguous
