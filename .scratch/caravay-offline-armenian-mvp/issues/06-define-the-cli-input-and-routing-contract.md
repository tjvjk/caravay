# Define the CLI input and routing contract

Type: grilling
Status: resolved
Blocked by: 05

## Question

What exact operands, stdin behavior, language arguments, defaults, capability checks, exit behavior, and stdout-versus-stderr rules should `caravay transcribe`, `caravay translate`, and `caravay run` expose for audio files and text streams?

## Answer

### Command forms and input

The MVP exposes these forms:

```text
caravay transcribe [OPTIONS] AUDIO_FILE
caravay translate  [OPTIONS] [TEXT_FILE|-]
caravay run        [OPTIONS] AUDIO_FILE
```

- `transcribe` and `run` require exactly one local audio-file operand. The operand
  must resolve to a readable regular file. They reject a missing operand, multiple
  operands, directories, URLs, and `-`; audio stdin, capture, and streaming are not
  part of the MVP.
- `translate` accepts at most one text-file operand. With no operand, or with `-`,
  it reads UTF-8 text from stdin until EOF. If stdin is an interactive terminal and
  no operand was supplied, it fails with a usage error instead of appearing to
  hang. A named file must be a readable regular UTF-8 file. An empty input is valid
  and yields a `skipped` command outcome rather than invoking the backend.
- Commands process one operand per invocation. Globs are expanded by the shell, so
  a glob matching multiple files is rejected. Directory and batch processing stay
  outside the MVP.

These input rules deliberately make text composable in a Unix pipeline while
keeping the first audio contract seekable and unambiguous. Supporting audio stdin
later can add `-` without changing the meaning of any accepted MVP invocation.

### Languages

All commands use named options rather than a positional `source:target` pair:

```text
--source LANGUAGE
--target LANGUAGE
```

Language values are case-sensitive canonical ISO 639-3 codes: exactly three
lowercase ASCII letters, with no aliases or normalization. A malformed value is an
argument error. `transcribe` accepts `--source` and rejects `--target`; `translate`
and `run` accept both. For the MVP, `--source` defaults to Source Armenian (`hye`)
and `--target` defaults to English (`eng`). A well-formed code other than `hye` for
the source or `eng` for the target passes argument parsing but fails capability
validation before a model is loaded. Both failures exit with status `2`, but their
diagnostics distinguish malformed syntax from an unsupported capability. This
keeps the interface extensible without advertising unsupported languages.

### Explicit routing

The packaged MVP backend is named `seamlessm4t-large-v2` and uses the
`facebook/seamless-m4t-v2-large` model selected in issue 04. The resulting
execution plan is always explicit before processing:

- `transcribe --backend NAME` binds `speech_to_text(source)` to `NAME`;
- `translate --backend NAME` binds `text_to_text(source, target)` to `NAME`;
- `run --route composed` binds `speech_to_text(source)` through
  `--speech-backend NAME` and `text_to_text(source, target)` through
  `--translation-backend NAME`;
- `run --route fused` binds
  `speech_to_text_translation(source, target)` through `--backend NAME`.

For every route or backend setting, resolution order is CLI option, configured
value, then packaged default. The packaged route is `composed`; its speech and
translation bindings are both `seamlessm4t-large-v2`, while preserving the
transcript boundary required by issue 05. The packaged defaults therefore make all
three commands runnable without routing flags. Selecting `fused` requires an
explicit or configured fused `--backend`, because the MVP supplies no packaged
fused binding.

Route-specific options are mutually exclusive: `--backend` is invalid with a
composed route, and `--speech-backend` or `--translation-backend` is invalid with a
fused route. A CLI binding overrides only the corresponding configured binding; it
never causes route inference or fallback. Issue 08 defines where configuration is
stored and how these names map to model and runtime settings, not this precedence.

After arguments and configuration are resolved, each command validates the entire
execution plan, language compatibility, and input before loading any model or
emitting primary output. Missing backends, unsupported capabilities or languages,
incompatible adjacent stages, and invalid route-option combinations are
configuration errors. The command never substitutes a backend or switches between
composed and fused routes at runtime.

### Exit status

The process exit status reflects the command outcome from issue 05:

| Status | Meaning |
| --- | --- |
| `0` | `completed` |
| `1` | `failed` after processing began, or an unexpected operational failure |
| `2` | command-line, input, configuration, or capability validation error |
| `3` | `degraded`; useful final output was emitted |
| `4` | `skipped`; no useful final output exists and no fatal failure occurred |

For multi-segment input, this is the aggregate command outcome defined in issue 05.
The stable nonzero statuses let callers distinguish partial or absent results from
success even when a text pipeline still forwards useful degraded output.

### Output channels

`stdout` contains only the selected primary result representation. For `text`
output this is source text from `transcribe` and target text from `translate` or
`run`; the exact `text` and `jsonl` serialization belongs to issue 07. No progress,
model-loading messages, warnings, labels, or diagnostics are written to stdout.

Human-readable progress and diagnostics go to `stderr`. Progress is enabled only
when stderr is an interactive terminal and can be disabled with `--quiet`;
warnings and errors remain visible with `--quiet`. Diagnostics must not contain a
second copy of successful primary output. Before-processing validation failures
write no stdout. Processing failures may leave already emitted segment results on
stdout; stderr and the exit status indicate that the result is incomplete.
