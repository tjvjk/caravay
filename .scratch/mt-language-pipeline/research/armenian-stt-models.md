# Armenian speech-to-text models for an offline Apple Silicon MVP

Research date: 2026-09-04

## Decision summary

For the next Caraway spike, benchmark these three routes on the **same Eastern Armenian corpus**:

1. **`ArthurYeghinyan/whisper-hy-am-asr-v2`** — best first challenger to the current pipeline: Armenian Whisper Medium fine-tune, ordinary Transformers checkpoint, and a reported ~17% WER. Its published evaluation is only 256 Common Voice dev samples and the repository does not declare a license, so it is an experimental quality signal, not a release-ready dependency.
2. **`Yeroyan/stt_arm_conformer_ctc_large`** — strongest Armenian-specific published number found: 15.0% WER / 12.44% without punctuation on Common Voice 17, with Eastern Armenian explicitly named. Benchmark it if the gated download and CC-BY-NC-4.0 license are acceptable. NeMo is a poor native-Mac product dependency, but the 487 MB checkpoint is realistic for a CPU proof of concept.
3. **OpenAI Whisper `small`, `medium`, and preferably `large-v3-turbo`/`large-v3`** — the safest engineering baseline. It has an MIT license and mature Apple Silicon runtimes (MLX and whisper.cpp), but there is no Armenian-specific quality claim in the official model materials. Benchmarking, not the multilingual label, must decide quality.

Keep **Meta MMS-1B-all (`hye`)** as a fourth experiment if time permits. It explicitly separates Eastern Armenian (`hye`) from Western Armenian (`hyw`), but is a 1B-parameter F32 model, non-commercially licensed, and its official card does not publish Armenian-specific WER. Do not spend more time on Vosk unless a third-party Armenian model appears: the official model catalog has no Armenian pack.

SeamlessM4T v2 remains useful when one checkpoint must also translate, but it is unnecessarily large for ASR-only use and already performed poorly enough in the local Caraway spike to justify testing specialist ASR models.

## Comparison

| Candidate | Armenian evidence | Architecture / size | License | Local runtime on Apple Silicon | Published evaluation | Main risks |
|---|---|---:|---|---|---|---|
| OpenAI Whisper multilingual (`small`, `medium`, `large-v3`, `turbo`) | Whisper's tokenizer contains `hy: armenian`; all non-`.en` checkpoints are multilingual. The official materials do not distinguish Eastern and Western Armenian. | Encoder-decoder Transformer; 244M, 769M, 1.55B, and 809M params respectively | MIT, code and weights | Excellent: OpenAI PyTorch; Apple MLX `mlx-whisper`; whisper.cpp with Metal, optional Core ML encoder, and quantized GGML models | Official repo publishes per-language plots for large-v3 on CV15/FLEURS, but no easily auditable Armenian scalar in its table; no Armenian-specific guarantee | Base multilingual training may underrepresent Armenian; autoregressive hallucination/repetition; large models need substantial unified memory |
| `ArthurYeghinyan/whisper-hy-am-asr-v2` | Card says Armenian (`hy`); trained on Common Voice 25 Armenian, Grqaser, and generated Armenian audio. It does **not** explicitly state Eastern Armenian. | Whisper Medium fine-tune, ~0.8B params, F32 safetensors | **Not specified in model card** | Good prototype path through Transformers/PyTorch MPS; conversion to MLX or whisper.cpp is not supplied and must be validated | Best observed ~17% WER on a fixed 256-sample CV25 Armenian dev subset | Tiny/nonstandard evaluation; synthetic-data bias; no license; only 11 monthly downloads at research time; no Mac measurements |
| `Yeroyan/stt_arm_conformer_ctc_large` | Card explicitly lists **Eastern Armenian** and fine-tuning on Common Voice 17 Armenian | Conformer CTC large; `.nemo` file ~487 MB; SentencePiece vocab 128 | CC-BY-NC-4.0 | NeMo/PyTorch; CPU inference is plausible at this size, but official path is NVIDIA-centric and there is no documented MLX/Metal/whisper.cpp export | 15.0% WER and 12.44% WER without punctuation on MCV17 test | Gated checkpoint; non-commercial; `եւ`→`և` post-processing required; heavyweight NeMo dependency; no Mac benchmark |
| Meta MMS-1B-all | Official adapter list contains both `hye` (Eastern Armenian ISO 639-3) and `hyw` (Western Armenian) | wav2vec2-style CTC with language adapters; 1B params, F32 | CC-BY-NC-4.0 | Transformers `Wav2Vec2ForCTC`; MPS/CPU may work, but no first-party Apple-optimized runtime or Armenian Mac benchmark was found | Official card gives aggregate/open-leaderboard values, not an Armenian-specific WER; do not reuse those numbers as Armenian quality | 1B base is heavy for ASR; non-commercial; CTC loses punctuation/casing unless restored; adapter/runtime behavior must be tested on MPS |
| Meta SeamlessM4T v2 Large | Official table lists `hye` Armenian as speech and text source and text target; dialect is not distinguished | UnitY2 multitask encoder-decoder, 2.3B params; checkpoint files roughly 9–11 GB | CC-BY-NC-4.0 | Transformers/PyTorch CPU or MPS; the existing Caraway prototype proves offline execution, but it is slow/heavy | Meta publishes aggregate FLEURS/CoVoST2/CVSS metrics, not an Armenian ASR scalar in the card | Non-commercial; over-sized for ASR-only; local output quality already questionable; complex generation path |
| `Center-of-Advanced-Software-Technologies/whisper-large-v3-mwa-hy` | Explicitly **Modern Western Armenian**, therefore mismatched to Caraway's Eastern Armenian target | Whisper Large v3 fine-tune; card reports 2B/F32; repository ~12.4 GB | CC-BY-4.0 | Transformers/PyTorch; example falls back to CPU on Mac; standard-format safetensors now exist, but large footprint | Only two qualitative example transcriptions; no WER/CER | Wrong dialect; huge; card example originally used unsafe pickle loading; no quantitative evaluation |
| `Chillarmo/whisper-small-hy-AM` | Armenian (`hy-AM`) trained on Common Voice 16.1; dialect not explicitly stated | Whisper Small fine-tune, ~244M params, F32 | Apache-2.0 | Transformers/PyTorch MPS/CPU; small enough for a practical Mac test | 38.116 WER on its evaluation set | Published WER is weak; old/limited training data; no external or Eastern-Armenian test |
| `alphaedge-ai/whisper-medium-hye-32768` | Armenian-targeted vocabulary trimming, tagged `hye`; this is a trimmed base, not evidence of Armenian acoustic fine-tuning | 2.56% vocabulary-trimmed Whisper Medium; encoder remains Medium-sized | Apache-2.0 per card metadata | Standard Transformers checkpoint; likely lower decoder/storage cost; MPS should be tested | No Armenian WER reported in the card found | Trimming does not create Armenian competence; quality unknown; no MLX/whisper.cpp artifact |
| Vosk/Kaldi official models | Official Vosk catalog lists 20+ language families but **no Armenian model** | Kaldi TDNN/HMM models vary from ~50 MB mobile to multi-GB server packs | Per model; commonly Apache-2.0 | Vosk itself is excellent offline and supports macOS/mobile | None for Armenian because no official pack exists | Would require finding/auditing a third-party pack or training one; not an MVP shortcut |

## Candidate notes

### 1. OpenAI Whisper family

The official repository describes Whisper as a multitask sequence-to-sequence Transformer and lists these useful size points: `small` 244M (~2 GB VRAM reference), `medium` 769M (~5 GB), `large` 1.55B (~10 GB), and `turbo` 809M (~6 GB). These are CUDA-oriented memory estimates, not Mac unified-memory measurements, but they give a reasonable ordering. The code and model weights are MIT licensed. The tokenizer source maps language code `hy` to `armenian`, which is explicit Armenian support but not an Eastern/Western dialect claim.

Apple Silicon has two mature offline paths:

- Apple's `ml-explore/mlx-examples` documents `pip install mlx-whisper` and local CLI/API transcription for Whisper. This is the lowest-friction Python benchmark path on Apple Silicon.
- `ggml-org/whisper.cpp` calls Apple Silicon a first-class target, uses ARM NEON, Accelerate and Metal, supports quantized models, and can offload the encoder to Core ML/ANE. This is the strongest eventual native/CLI deployment path.

The important gap is quality evidence. OpenAI says performance varies widely by language and publishes CV15/FLEURS plots, but does not make a clear Eastern Armenian claim. Therefore test at least `small`, `medium`, and `large-v3` or `turbo` on Caraway's conversational Eastern Armenian. Note that `turbo` is for transcription, not speech translation; that is fine for the intended STT→text-translation cascade.

Sources: [OpenAI Whisper repository and size table](https://github.com/openai/whisper), [official tokenizer language mapping](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py), [Whisper large-v3 model card](https://huggingface.co/openai/whisper-large-v3), [Apple MLX Whisper example](https://github.com/ml-explore/mlx-examples/tree/main/whisper), [whisper.cpp](https://github.com/ggml-org/whisper.cpp).

### 2. Armenian Whisper fine-tunes

`ArthurYeghinyan/whisper-hy-am-asr-v2` is the most promising current Whisper fine-tune found. Its card reports Armenian training from Common Voice 25, Grqaser, and generated audio, with ~17% best WER on a fixed 256-example Common Voice dev subset. It uses ordinary Whisper Medium safetensors, so Transformers on MPS is a direct prototype route. However, the evaluation is small, the dialect is not stated, and the card lacks a license. Treat it as a benchmark candidate only until provenance and licensing are clarified.

`Chillarmo/whisper-small-hy-AM` is smaller and Apache-2.0, but reports WER 38.116 on Common Voice 16.1, so it is unlikely to beat a strong generic checkpoint. `Center-of-Advanced-Software-Technologies/whisper-large-v3-mwa-hy` is explicitly Modern Western Armenian and hence unsuitable as the primary Eastern Armenian model; it has no WER. `alphaedge-ai/whisper-medium-hye-32768` is vocabulary-trimmed rather than acoustically fine-tuned and provides no quality metric; it is an optimization experiment, not a quality candidate.

Sources: [ArthurYeghinyan Whisper Medium Armenian card](https://huggingface.co/ArthurYeghinyan/whisper-hy-am-asr-v2), [Chillarmo Whisper Small Armenian card](https://huggingface.co/Chillarmo/whisper-small-hy-AM), [C-A-S-T Modern Western Armenian card](https://huggingface.co/Center-of-Advanced-Software-Technologies/whisper-large-v3-mwa-hy), [alphaedge trimmed Armenian checkpoint](https://huggingface.co/alphaedge-ai/whisper-medium-hye-32768).

### 3. Armenian NeMo Conformer

`Yeroyan/stt_arm_conformer_ctc_large` is the only specialist model found whose card both explicitly says Eastern Armenian and reports a held-out Common Voice test result. It is a Conformer CTC model with a 128-token SentencePiece vocabulary, fine-tuned for 100 epochs on Common Voice 17 Armenian. The stated WER is 15.0%, or 12.44% after punctuation removal. Audio must be 16 kHz mono; the card also requires replacing `եւ` with `և` after prediction.

The model file is about 487 MB, so CPU inference is physically realistic on a Mac. The problem is operational: the checkpoint is gated, licensed CC-BY-NC-4.0, and distributed only as a NeMo checkpoint. NVIDIA's NeMo stack is much less natural on macOS than MLX or whisper.cpp. A proof of concept should first try CPU inference; only investigate ONNX/Core ML conversion if its corpus quality clearly wins.

Source: [Yeroyan Armenian Conformer CTC model card](https://huggingface.co/Yeroyan/stt_arm_conformer_ctc_large).

### 4. Meta MMS

`facebook/mms-1b-all` is a 1B-parameter wav2vec2/CTC ASR checkpoint with language adapters. The official supported-language list includes `hye` and `hyw`, which is valuable because ISO 639-3 identifies them separately as Eastern and Western Armenian. Transformers supports swapping adapters with `load_adapter()` and `set_target_lang()`.

The model is F32 and CC-BY-NC-4.0. It should be possible to attempt PyTorch MPS or CPU inference, but no official Apple-optimized runtime or Armenian-on-Mac result was found. The model card's displayed aggregate/open-leaderboard metrics are not Armenian-specific and are not evidence that it beats specialist checkpoints on Caraway's data.

Sources: [MMS-1B-all model card and adapter list](https://huggingface.co/facebook/mms-1b-all), [MMS paper](https://arxiv.org/abs/2305.13516), [Transformers MMS documentation](https://huggingface.co/docs/transformers/model_doc/mms).

### 5. SeamlessM4T

The official SeamlessM4T v2 card lists Armenian (`hye`) for source speech, source text, and target text. Large v2 is a 2.3B-parameter UnitY2 multitask model under CC-BY-NC-4.0. It runs through Transformers, and Caraway already proved local CPU/MPS execution. It remains the only candidate here that natively combines ASR and translation, but that advantage is irrelevant if a cascade is chosen and its Armenian ASR is weak. It is also much larger than a specialist CTC model or Whisper Small/Medium.

Sources: [SeamlessM4T v2 Large model card](https://huggingface.co/facebook/seamless-m4t-v2-large), [Seamless paper](https://arxiv.org/abs/2312.05187).

### 6. Vosk/Kaldi and NVIDIA catalog status

The official Vosk model catalog does not contain Armenian. Vosk is attractive operationally—offline, streaming, small models, mobile support—but without a maintained Armenian model it is a training project, not an alternative checkpoint. The Armenian NeMo checkpoint above is community-published; no Armenian pretrained ASR model was found in NVIDIA's official catalog/model listings. Generic NVIDIA Parakeet/Canary checkpoints should not be assumed to support Armenian unless their own cards list it.

Sources: [Vosk official model catalog](https://alphacephei.com/vosk/models), [Vosk overview](https://alphacephei.com/vosk/), [NVIDIA NeMo ASR model documentation](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/models.html).

## Recommended benchmark protocol

Model-card WER values above are **not directly comparable**: they use different Common Voice versions, subsets, normalization, punctuation handling, and possibly synthetic data. The selection should use one local test harness and one frozen corpus:

1. Split the existing Eastern Armenian conversational recording into short utterances with manually corrected Armenian references.
2. Score normalized CER and WER, while retaining raw text for punctuation, repetition, hallucination, code-switching, names, and numerals review.
3. Record real-time factor and peak resident/unified memory on the reference Mac after a warm run.
4. Run in this order: generic Whisper Medium or turbo via MLX; ArthurYeghinyan Medium via Transformers MPS; Yeroyan Conformer via NeMo CPU; MMS `hye`; then generic Whisper Small/large-v3 depending on the speed/quality boundary.
5. Reject any candidate whose license does not meet the product boundary before integrating it. In particular, both Meta checkpoints and the Yeroyan checkpoint are non-commercial; ArthurYeghinyan currently has no declared license.

## Bottom line

For an open, distributable Mac MVP, generic MIT-licensed Whisper currently has the cleanest product path even if it does not win raw Armenian WER. For a research-quality benchmark, the Armenian Whisper Medium fine-tune and Eastern Armenian NeMo Conformer are the two highest-value additions. The next decision should be based on one controlled local bake-off, not cross-card WER.

## Local follow-up

Generic `whisper-large-v3-turbo` was subsequently tested through MLX on the
project's five-minute Eastern Armenian corpus. It ran at 0.146 RTF with 1.76
GiB peak RSS, but produced unusable mixed-script hallucinations and extensive
repetition both with and without previous-window text conditioning. The local
result rejects generic Turbo for this corpus and raises the priority of the
Armenian Whisper fine-tune; it does not establish the quality of generic Large
v3. See [`whisper-prototype-results.md`](../../caraway-offline-armenian-mvp/whisper-prototype-results.md).

The recommended Armenian fine-tune was also tested. It produced Armenian-only,
often recognizable text, but repeated a token four or more consecutive times
on 8 of 30 chunks, ran at 0.438 RTF, and used 4.67 GiB peak RSS. Together with
its missing license, this makes it a useful comparison source rather than the
current MVP choice. Seamless Large v2's ASR ran at 0.085 RTF and triggered the
same simple repetition detector on 6 of 30 chunks.
