# Armenian speech translation models for a local Apple-Silicon MVP

Research date: 2026-09-04

## Decision summary

For an MVP constrained to **one model**, the best-supported candidate is **Meta SeamlessM4T Medium (v1)**. It is one 1.2B-parameter multitask model that exposes ASR, speech-to-text translation (S2TT), and text-to-text translation (T2TT). Meta lists Armenian (`hye`) as a speech/text source and Russian (`rus`) and English (`eng`) as text targets, so both Armenian speech → English text and Armenian speech → Russian text are native model routes rather than an ASR-plus-MT cascade. Meta also publishes an Apple-Silicon-compatible Python dependency path and a CPU-oriented GGML implementation for S2TT/ASR/T2TT. [Medium model card](https://huggingface.co/facebook/seamless-m4t-medium) · [language matrix](https://huggingface.co/facebook/seamless-m4t-v2-large/blob/c2a72919bca47fb9bfbe0e2fed242389c4e97830/README.md#supported-languages) · [official repository](https://github.com/facebookresearch/seamless_communication)

This is a **candidate to prototype, not yet a safe final selection**. The official sources establish task and language coverage, but do not publish Armenian→English/Russian direction-specific quality or Apple-Silicon latency figures. A short acceptance benchmark on the target Mac and representative Armenian recordings is therefore the next decision gate.

There is also a material product constraint: SeamlessM4T code and weights are **CC-BY-NC 4.0**, so the candidate is suitable for personal/research prototyping but not an unrestricted commercial distribution choice. [Meta model card, License](https://huggingface.co/facebook/seamless-m4t-medium#license)

## Candidate comparison

| Candidate | Pipeline | Armenian speech | English output | Russian output | Apple-Silicon path | License | Verdict |
|---|---|---:|---:|---:|---|---|---|
| **SeamlessM4T Medium v1** | One model; ASR, S2TT, T2TT | Explicit `hye` speech source | Direct S2TT | **Direct S2TT** | fairseq2 arm64 macOS package; GGML CPU path; Transformers API | CC-BY-NC 4.0 | Best one-model MVP candidate; benchmark it first |
| **SeamlessM4T Large v2** | One model; ASR, S2TT, T2TT | Explicit `hye` speech source | Direct S2TT | **Direct S2TT** | Transformers/PyTorch or fairseq2; much larger footprint | CC-BY-NC 4.0 | Quality-oriented comparison candidate, not default |
| **Whisper large-v3** | One model; ASR or speech→English | Multilingual model, but no Armenian-specific guarantee/score in its model card | Direct speech translation to English | **No**; `translate` targets English only | Mature `whisper.cpp` Apple path, Metal/Core ML and quantization | Apache-2.0 weights | Attractive English-only control; fails Russian requirement |
| **MMS-1B-All + NLLB-200 distilled 600M** | Two-model Armenian ASR → text MT | Explicit `hye` ASR adapter | Text MT | Text MT | Both are PyTorch/Transformers; needs integration validation | Both CC-BY-NC 4.0 | Useful cascade baseline/fallback, but violates one-model preference |

## Why SeamlessM4T fits the requested composition

“One model” need not mean one CLI operation. SeamlessM4T is explicitly a single multitask model supporting S2TT, ASR, and T2TT. The CLI can therefore preserve composable user-facing commands while sharing one loaded checkpoint:

- `transcribe`: Armenian audio → Armenian text (ASR)
- `translate`: Armenian text → English or Russian text (T2TT)
- fused route: Armenian audio → English or Russian text (S2TT)

Meta describes Medium as enabling all these tasks “without relying on multiple separate models”; its Transformers example uses the same model for audio/text inputs and translated text/audio outputs. [Official Medium model card, task and API sections](https://huggingface.co/facebook/seamless-m4t-medium#seamlessm4t-medium)

The official language matrix says Armenian (`hye`) accepts both speech and text sources, while English (`eng`) and Russian (`rus`) accept text (and speech) targets. Consequently, Russian is a native requested target, not a Whisper-style intermediate English translation. [Official language matrix](https://huggingface.co/facebook/seamless-m4t-v2-large/blob/c2a72919bca47fb9bfbe0e2fed242389c4e97830/README.md#supported-languages)

### Medium versus Large v2

- Medium v1 is 1.2B parameters; Large v2 is 2.3B. [Meta model table](https://huggingface.co/facebook/seamless-m4t-medium#seamlessm4t-models)
- The Large v2 Transformers weights are split into approximately 5.0 GB and 4.24 GB safetensor shards; the repository totals 29.9 GB because it also contains alternate checkpoint formats and a vocoder. This makes Large v2 materially less comfortable on lower-memory Macs. [Large v2 files](https://huggingface.co/facebook/seamless-m4t-v2-large/tree/main)
- Meta says v2 improves quality and inference speed specifically in **speech generation** tasks; that does not by itself establish a better Armenian S2TT latency/quality tradeoff. [Large v2 model card](https://huggingface.co/facebook/seamless-m4t-v2-large)

Therefore Medium is the lower-risk first feasibility target; Large v2 should enter only as a benchmark challenger if Medium's Armenian translation quality is insufficient.

## Apple Silicon feasibility

There are three plausible execution paths, with different confidence levels:

1. **Official `seamless_communication` / fairseq2 on CPU.** Meta states that fairseq2 has prebuilt packages for Apple-Silicon Macs. Its examples are CUDA-oriented, however, so this establishes installability, not GPU acceleration or real-time performance. [Meta repository installation notes](https://github.com/facebookresearch/seamless_communication#installation)
2. **Official unity.cpp / GGML on CPU.** Meta's `unity.cpp` supports SeamlessM4T S2TT, ASR, and T2TT, publishes a converted Medium model, and recommends OpenBLAS after observing an 8× speedup on its test machine. The documentation does not claim Metal acceleration, so treat this as a CPU path. [unity.cpp README](https://github.com/facebookresearch/seamless_communication/tree/main/ggml#unitycpp)
3. **Transformers + PyTorch MPS.** PyTorch supports moving models to the `mps` device for Metal-backed execution on macOS, and Hugging Face exposes SeamlessM4T through Transformers. Neither cited source guarantees that every SeamlessM4T operation is implemented and stable on MPS, so actual end-to-end inference must be tested before choosing this path. [PyTorch MPS documentation](https://docs.pytorch.org/docs/stable/notes/mps.html) · [Medium Transformers example](https://huggingface.co/facebook/seamless-m4t-medium#transformers-usage)

Practical implication: specify **Apple-Silicon local execution**, but do not promise “real-time” or MPS acceleration yet. Record model load time, peak unified memory, real-time factor, and output quality on the actual target machine.

## Other credible paths

### Whisper: strong English-only control, not the requested universal model

Whisper large-v3 is a 1.55B-parameter multilingual model under Apache-2.0. Its official usage documentation is unambiguous: transcription produces source-language text, while `task="translate"` produces **English** text. It therefore can fuse Armenian speech → English if Armenian quality proves acceptable, but it cannot directly produce Russian. The model card also warns that quality is uneven for low-resource languages and says robust evaluation is needed for a specific context. [OpenAI Whisper large-v3 model card](https://huggingface.co/openai/whisper-large-v3)

Its deployment story on Mac is stronger: the author-maintained `whisper.cpp` supports quantization, Metal, and Apple Neural Engine encoder execution via Core ML. [whisper.cpp repository](https://github.com/ggml-org/whisper.cpp)

Use Whisper as an English-output benchmark, especially if SeamlessM4T is too slow. Do not treat it as the sole model when Russian output is required.

### MMS + NLLB: explicit Armenian cascade baseline

Meta's MMS-1B-All is a 1B-parameter ASR checkpoint with adapters for 1,100+ languages; its supported adapter list explicitly includes Eastern Armenian (`hye`) and Western Armenian (`hyw`). [MMS model card and supported languages](https://huggingface.co/facebook/mms-1b-all)

NLLB-200 distilled 600M is a text translation model intended for sentence translation among 200 languages. The published FLORES/NLLB language set includes Armenian and Russian, making it a suitable second stage after MMS. Its model card limits intended use to research, warns against production deployment and long/document translation, and applies CC-BY-NC. [NLLB model card](https://huggingface.co/facebook/nllb-200-distilled-600M)

This pipeline gives an inspectable Armenian transcript and allows either target language, but loads and coordinates two models. It is a valuable quality/debugging baseline rather than the requested one-model MVP.

## Recommended acceptance spike before locking the specification

Run the same small corpus through SeamlessM4T Medium's three routes:

- direct `hye` speech → `eng` text;
- direct `hye` speech → `rus` text;
- `hye` ASR, then the same model's `hye` → `eng`/`rus` T2TT route.

Include clean speech, ordinary room noise, code-switching, names/numbers, and both Eastern and (if relevant) Western Armenian. Capture:

- human preference for meaning preservation in English and Russian;
- Armenian transcript usefulness and whether it helps diagnose errors;
- real-time factor and time-to-first-output;
- peak unified memory and checkpoint disk footprint;
- CPU GGML versus PyTorch CPU/MPS reliability.

The decision rule should be: adopt Medium if both target directions meet the human quality threshold and it fits the target Mac; compare Large v2 only if quality fails; compare Whisper for English and MMS+NLLB for both targets if Seamless fails operationally.

## Remaining uncertainties

- No official Armenian→English or Armenian→Russian per-direction metric was found in the model cards; “supported” is not evidence of acceptable quality.
- No official SeamlessM4T benchmark on Apple Silicon was found.
- The model cards do not distinguish Eastern versus Western Armenian for SeamlessM4T; MMS does expose separate `hye` and `hyw` adapters.
- CC-BY-NC blocks an uncomplicated commercial path. If commercial distribution becomes part of the destination, licensing must become a separate decision ticket.
- Context7's PyTorch library-resolution command returned no result in this session; current PyTorch MPS facts were therefore checked directly against the official PyTorch documentation rather than inferred from memory.

## Primary sources

- Meta, [SeamlessM4T Medium model card](https://huggingface.co/facebook/seamless-m4t-medium)
- Meta, [SeamlessM4T v2 Large model card and language matrix](https://huggingface.co/facebook/seamless-m4t-v2-large)
- Meta, [Seamless Communication repository](https://github.com/facebookresearch/seamless_communication)
- Meta, [unity.cpp README](https://github.com/facebookresearch/seamless_communication/tree/main/ggml#unitycpp)
- OpenAI, [Whisper large-v3 model card](https://huggingface.co/openai/whisper-large-v3)
- ggml-org, [whisper.cpp repository](https://github.com/ggml-org/whisper.cpp)
- Meta, [MMS-1B-All model card](https://huggingface.co/facebook/mms-1b-all)
- Meta, [NLLB-200 distilled 600M model card](https://huggingface.co/facebook/nllb-200-distilled-600M)
- PyTorch, [MPS backend documentation](https://docs.pytorch.org/docs/stable/notes/mps.html)
