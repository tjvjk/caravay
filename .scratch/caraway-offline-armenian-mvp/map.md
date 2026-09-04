# Caraway offline Armenian translation MVP

Label: wayfinder:map

## Destination

An implementation-ready MVP specification for `caraway`, validated by an acceptance prototype on the user's Apple-Silicon Mac: Eastern Armenian audio files and text become English text locally after model download through the `transcribe`, `translate`, and `run` commands.

## Notes

- Source idea: [`idea.md`](../../idea.md).
- Use `domain-modeling` throughout and keep [`CONTEXT.md`](../../CONTEXT.md) current.
- Use `grilling` with `domain-modeling` for human decisions and `prototype` for the model acceptance spike.
- The acceptance prototype is explicitly part of this planning effort; production CLI implementation is not.
- Optimize in this order: translation quality, reliable offline Apple-Silicon execution, speed, then model size.
- English is the required target. Evaluate Russian opportunistically as a secondary target, but do not let it block the MVP.
- Model licenses must be recorded but do not disqualify a candidate in this effort.
- MVP decisions must not intentionally prevent later input, output, or backend extensions, but those extensions are not designed here.

## Decisions so far

- [Establish the viable Armenian model routes](issues/01-establish-viable-armenian-model-routes.md): SeamlessM4T Medium is the first one-model candidate; its real Armenian quality and Apple-Silicon performance remain to be prototyped.

## Not yet specified

- Concrete performance and quality acceptance thresholds can be sharpened after the representative corpus exists and the first measurements reveal the useful scale.
- Installation, packaging, model-cache lifecycle, and minimum supported Mac constraints depend on the selected runtime path.
- The implementation handoff structure may need additional sections once the backend and capability contracts are settled.

## Out of scope

- Production implementation of the `caraway` CLI; this effort ends with its validated specification.
- Live microphone or system-audio capture, VAD, and streaming partial results.
- Subtitle generation, TTS, and directory-oriented batch processing.
- A promise that arbitrary Hugging Face models or multiple production backends work in the MVP.
- Windows, Linux, cloud inference, and offline use before the initial model download completes.

