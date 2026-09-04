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
- [Assemble a representative Eastern Armenian corpus](issues/02-assemble-representative-eastern-armenian-corpus.md): start the acceptance prototype with one five-minute conversational Eastern Armenian excerpt and expand the corpus only if the first results are inconclusive.
- [Prototype SeamlessM4T on the reference Mac](issues/03-prototype-seamlessm4t-on-the-reference-mac.md): Medium and Large v2 task-specific Transformers models run reliably and faster than real time on MPS. Large v2 improves some Armenian segments but still repeats on difficult chunks, so model/route acceptance requires human review.
- [Test generic Whisper Large v3 Turbo](whisper-prototype-results.md): MLX is operationally excellent (0.146 RTF, 1.76 GiB peak RSS), but Turbo's Eastern Armenian transcript is unusable due to mixed-script hallucinations and repetition; an Armenian fine-tune remains a separate candidate.
- [Test Armenian Whisper Medium fine-tune](whisper-prototype-results.md#armenian-medium-fine-tune-follow-up): Armenian-specific tuning restores recognizable Armenian output, but 8/30 chunks loop, ASR is slower than Seamless Large v2, and the checkpoint has no declared license.
- [Choose the MVP model route](issues/04-choose-the-mvp-model-route.md): require SeamlessM4T Large v2 as a composed Source Armenian speech → transcript → English pipeline; accept current repetition as a known limitation, CC-BY-NC-4.0 for non-commercial use, and do not require another fallback comparison.
- [Define backend capabilities and pipeline semantics](issues/05-define-backend-capabilities-and-pipeline-semantics.md): describe backends by language-qualified operations, bind them in explicit prevalidated execution plans without implicit fallback, preserve declared transcript boundaries, and continue past repeated generation through degraded or skipped segment outcomes.
- [Define the CLI input and routing contract](issues/06-define-the-cli-input-and-routing-contract.md): accept one local audio file for speech commands and a UTF-8 file or stdin for text translation, use `hye`/`eng` language defaults, validate an explicit composed or fused plan before loading, reserve stdout for results, and distinguish completed, failed, invalid, degraded, and skipped exits.
- [Define the text and JSONL output contracts](issues/07-define-the-text-and-jsonl-output-contracts.md): default to final-text-only UTF-8 output, offer versioned ordered JSONL segment and summary records for outcomes and metadata, expose source transcripts only when a plan actually produces them, and keep stable codes separate from human diagnostics.
- [Define configuration and model lifecycle](issues/08-define-configuration-and-model-lifecycle.md): resolve strict TOML configuration from a macOS user file, install one pinned SeamlessM4T snapshot explicitly and atomically into a managed cache, keep working commands offline and MPS-only, and make missing or invalid first-run state fail before model loading.

## Not yet specified

- Concrete performance and quality acceptance thresholds can be sharpened after the representative corpus exists and the first measurements reveal the useful scale.
- Installation, packaging, and minimum supported Mac constraints depend on the selected runtime path.
- The implementation handoff structure may need additional sections once the backend and capability contracts are settled.

## Out of scope

- Production implementation of the `caraway` CLI; this effort ends with its validated specification.
- Live microphone or system-audio capture, VAD, and streaming partial results.
- Subtitle generation, TTS, and directory-oriented batch processing.
- A promise that arbitrary Hugging Face models or multiple production backends work in the MVP.
- Windows, Linux, cloud inference, and offline use before the initial model download completes.
