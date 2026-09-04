# Local Language Pipeline

This context describes `mt`, a local CLI for transforming spoken or written language through composable processing stages.

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

**Source Armenian**:
Eastern Armenian as commonly spoken in Yerevan, identified by the language code `hye`. Western Armenian is a distinct, unsupported source variant for the MVP.
_Avoid_: Armenian when the variant is ambiguous
