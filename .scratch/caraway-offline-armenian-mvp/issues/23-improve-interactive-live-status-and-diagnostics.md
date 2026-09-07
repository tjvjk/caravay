# 23: Improve interactive live status and diagnostics

**What to build:** Make the system-audio-to-live-transcription command visibly
alive while it waits for speech or generates a result, without mixing status text
into the transcript. Replace routine implementation diagnostics with concise
human-facing lifecycle output, and reserve detailed capture and transcript-cleanup
information for verbose diagnostics.

**Blocked by:** 18 / Translate a live PCM stream from stdin; 22 / Capture macOS
system audio to live PCM

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/9

_This ticket changes presentation only. It does not add partial transcripts,
change segmentation or generation behavior, or change the machine-readable result
schema and outcome classification._

## Current behavior

A typical interactive invocation is:

```console
native/SystemAudioCapture/.build/release/caraway-capture \
    | uv run caraway live --input-format f32le -
```

After startup, the terminal can remain unchanged for several seconds while audio
is being accepted and a segment is being formed or processed. The user cannot
distinguish healthy listening from a stalled pipeline. Routine internals are also
printed alongside the transcript, for example:

```text
first_pcm: uptime_seconds=122205.59130404168
generation_artifact: generation artifact was removed from transcript
capture_stopped: reason=interrupted capture_queue_peak=23
interrupted: capture stopped by SIGINT
```

The first-PCM timestamp and queue peak are acceptance/debug measurements rather
than useful interactive messages. A removed generation artifact is a successful
automatic cleanup and normally requires no user action. On interruption, both
pipeline processes currently report the same event.

## Acceptance criteria

- [x] On a compatible interactive terminal, `caraway live` presents one transient
      status line that makes the current phase visible. It distinguishes at least
      listening for/collecting audio from transcribing a finalized segment and
      includes elapsed session time while listening (for example,
      `Listening... 00:07` and `Transcribing...`).
- [x] The transient status is updated in place at a restrained cadence rather than
      appending heartbeat lines. It is cleared before a transcript segment,
      actionable diagnostic, or final lifecycle message is written, then restored
      if live processing continues. Output remains legible when a segment arrives
      during a status update.
- [x] Interactive status is enabled only when the diagnostics stream is a TTY and
      normal quiet-mode rules allow it. Non-TTY stderr receives no spinner,
      carriage returns, ANSI control sequences, periodic heartbeat, or other
      unbounded status output.
- [x] Plain transcript stdout remains byte-compatible with the existing immutable
      LF-delimited contract. JSONL output and PCM stdout from `caraway-capture`
      likewise receive no presentation text or terminal control bytes.
- [x] Successfully removed generation artifacts and repetition suffixes do not
      produce a per-segment warning in the default interactive experience. The
      segment retains its existing degraded/skipped outcome, issue metadata,
      aggregate accounting, and exit-status semantics.
- [x] Verbose mode exposes automatic cleanup in plain language, for example
      `cleanup: omitted non-speech model output`, without relying on the internal
      `generation_artifact` identifier as the user-facing explanation. Structured
      issue codes remain stable wherever they are part of a machine-readable
      contract.
- [x] `first_pcm` uptime, capture queue peak, and native termination codes are
      hidden during a normal interactive run and remain available through an
      explicit verbose or diagnostic mode used by acceptance measurements.
- [x] A normal Ctrl-C shutdown produces one concise human-facing completion, such
      as `Stopped. 5 segments transcribed, 1 cleaned up.` It does not print
      duplicate producer/consumer interruption messages. Shell-standard SIGINT
      exit behavior and resource cleanup remain unchanged.
- [x] Startup and terminal rendering do not assume that the native capture
      producer is present: `caraway live` provides useful status when fed by any
      valid paced PCM producer, and `caraway-capture` remains independently usable.
- [x] Quiet mode suppresses progress and routine lifecycle presentation but not
      fatal, actionable diagnostics. Verbose mode can coexist with transient
      status without overwriting or visually corrupting diagnostic lines.
- [x] Fast tests use controlled streams, clocks, TTY capability, and terminal
      widths to cover idle listening, phase transitions, multiple segments,
      cleanup, quiet mode, verbose mode, non-TTY output, narrow terminals, EOF,
      SIGINT, overload, and fatal input/model failure.

## Example interactive session

The status lines below represent successive in-place states; they should not all
remain in terminal history:

```text
Capturing system audio -- press Ctrl-C to stop
Listening... 00:04
Hi, you're watching Seoul Business...
Listening... 00:12
Aram Mkhitaryan, hello...
^C
Stopped. 5 segments transcribed, 1 cleaned up.
```

## Comments
