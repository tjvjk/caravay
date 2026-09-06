# 18: Translate a live PCM stream from stdin

**What to build:** Add an explicit live mode that continuously accepts Source
Armenian raw PCM audio on stdin, segments speech while it arrives, and emits each
useful English translation as soon as the composed speech-to-English pipeline
finishes it. A local recording paced by `ffmpeg -re` must exercise the same input
seam that a future microphone or system-audio capture producer will use.

**Blocked by:** 14 / Run the composed speech-to-English execution plan; 16 /
Strengthen cyclic generation detection

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/7

- [x] The CLI exposes an explicit command such as
      `caraway live --input-format f32le -`; it does not change the finite-file
      behavior or input contract of `caraway run` and `caraway transcribe`.
- [x] The initial live input contract requires raw little-endian Float32 mono PCM
      at 16 kHz on non-interactive stdin. It rejects an omitted `-`, an interactive
      terminal, unsupported formats, files, URLs, and extra operands before model
      loading.
- [x] The documented local-file simulation uses an equivalent of
      `ffmpeg -re -i INPUT -f f32le -ac 1 -ar 16000 pipe:1 | caraway live --input-format f32le -`,
      so audio reaches Caraway at approximately capture speed rather than being
      decoded as a complete file first.
- [x] Input is consumed incrementally in short frames and drained independently
      of model inference into a bounded buffer, so speech recognition or
      translation cannot silently throttle the producer and disguise accumulated
      end-to-end latency.
- [x] Segment timestamps are derived from the monotonic PCM sample position, not
      wall-clock scheduling, and every segment retains explicit source start and
      end positions through transcription and translation.
- [x] Hybrid segmentation starts a candidate on speech, closes it after a
      configurable bounded silence interval, enforces a configurable maximum
      speech duration, and combines or defers fragments below a configurable
      minimum duration without losing samples at boundaries.
- [x] Initial defaults are documented and covered by tests: 16 kHz input, a
      silence interval in the 400–800 ms range, and a maximum segment duration in
      the 5–10 second range. Changing these values does not alter the model or
      language routing contract.
- [x] End of stdin is orderly stream completion: any remaining speech is finalized
      and attempted once, buffered silence is discarded, pending useful results
      are emitted, and all reader and inference resources terminate cleanly.
- [x] Each completed or degraded useful Source Armenian segment is passed through
      the existing composed Armenian-to-English route. Skipped speech segments
      produce no fabricated English text, fatal failures terminate the stream,
      and repetition guards run before either transcript or translation is
      exposed.
- [x] Default text output contains only ordered English utterances, writes each
      utterance on its own LF-terminated line, and flushes immediately. Progress,
      VAD events, latency reporting, and human diagnostics never contaminate
      stdout.
- [x] JSONL output identifies live mode and includes, per result, the source audio
      start/end positions, source transcript when available, English text,
      outcome, and measured end-to-end latency from the segment end to emission.
      A terminal record distinguishes clean EOF, interruption, overload, and
      failure.
- [x] The bounded-buffer overload policy is explicit and deterministic. It never
      silently drops or reorders speech; when sustained inference falls behind
      the input beyond the configured bound, the command reports the backlog and
      terminates non-successfully rather than pretending to remain live.
- [x] SIGINT and a broken input pipe stop capture, settle or cancel in-flight work
      according to one documented policy, release resources, and preserve the
      stdout/stderr and exit-status contracts.
- [x] Fast tests use a controlled PCM producer, clock, VAD boundary, and speech and
      translation backends to cover frame fragmentation, speech/silence
      boundaries, minimum and maximum segment lengths, EOF tail flushing, ordered
      emission, immediate flushing, slow inference, overload, fatal failure, and
      interruption without real audio devices or sleeps.
- [x] An opt-in acceptance test paces a short conversational Source Armenian
      recording through `ffmpeg -re`, produces useful English utterances while
      ffmpeg is still running, and records time to first English output, per-result
      end-to-end latency, maximum backlog, total wall time, and operator notes on
      segmentation and translation usefulness on the reference Mac.
- [x] Microphone and macOS system-audio capture remain separate producers outside
      this ticket; the live pipeline has no source-specific assumptions beyond the
      documented PCM stdin contract, so those producers can connect without a
      second segmentation or translation implementation.

## Comments

### 2026-09-06 implementation verification

Paced the full five-minute reference recording
`corpus/WncDNZDeWr0/WncDNZDeWr0_15m30s-20m30s.m4a` through `ffmpeg -re` as
Float32 mono 16 kHz PCM. English results appeared while ffmpeg was still running.
The clean-EOF run attempted 38 segments: 33 completed, 3 degraded, 2 skipped,
and 0 failed. Measured segment latency ranged from 643 ms to 2918 ms with a
1115 ms average; maximum backlog was 255 20-ms frames (about 5.1 seconds).
