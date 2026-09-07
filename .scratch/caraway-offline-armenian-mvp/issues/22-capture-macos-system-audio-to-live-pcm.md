# 22: Capture macOS system audio to live PCM

**What to build:** Add a small macOS capture producer that uses ScreenCaptureKit
to capture the complete system-audio mix and continuously writes Caraway's existing
live PCM format to standard output. Piping that output to `caraway live` must turn
audio played by meeting, browser, and media applications into English text without
a virtual audio device.

**Blocked by:** 18 / Translate a live PCM stream from stdin

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/8

_This ticket adds one macOS input adapter at the existing raw-PCM seam. Selecting
individual applications, capturing or mixing a microphone, partial translations,
speaker attribution, recording to a file, and support for Windows or Linux remain
outside its scope._

## Evidence

Issue 18 deliberately accepts paced raw little-endian Float32 mono PCM at 16 kHz
on stdin so an eventual system-audio producer can reuse the live segmentation and
translation pipeline. ScreenCaptureKit supplies system audio as `CMSampleBuffer`
values without a virtual loopback driver.

`sohzm/systemAudioDump` demonstrates the bounded native path in a dependency-free
Swift executable: acquire ScreenCaptureKit permission, select a display-wide
content filter, receive only `.audio` stream output, convert the native stream, and
write PCM bytes to stdout. It is evidence rather than a reusable dependency: its
current implementation mixes startup diagnostics into stdout, fixes a different
PCM format, exits directly from a signal handler, and does not provide Caraway's
failure and backpressure contracts.

- [x] The repository contains a native macOS capture executable with a documented
      development build and invocation path. Swift and Apple system frameworks are
      sufficient; the executable has no runtime dependency on a separately
      installed virtual audio device or third-party capture utility.
- [x] The initial command has one source policy: capture the complete audible
      system mix through ScreenCaptureKit while excluding its own process audio.
      It exposes no application selector and does not request or capture a
      microphone.
- [x] Successful capture writes only headerless little-endian Float32 mono PCM at
      exactly 16 kHz to stdout, matching `caraway live --input-format f32le -`
      directly and requiring no intermediate `ffmpeg` conversion.
- [x] Human-readable status, permission guidance, and diagnostics are written only
      to stderr. No startup text, container header, framing bytes, or terminal
      control sequence can enter the stdout PCM stream.
- [x] The producer discovers the native sample format from each accepted stream,
      performs explicit channel mixing and sample-rate conversion, and preserves
      sample ordering across successive ScreenCaptureKit buffers.
- [x] Screen and system-audio recording permission is checked and requested before
      capture starts. Denial and unavailable ScreenCaptureKit content produce a
      stable diagnostic, leave stdout empty, release acquired resources, and exit
      unsuccessfully.
- [x] Audio delivery is separated from stdout writes by a bounded queue so pipe
      backpressure cannot block the ScreenCaptureKit callback indefinitely. A full
      queue is an explicit fatal overload: the producer reports it and terminates
      rather than silently dropping, duplicating, or reordering samples.
- [x] EOF is represented by closing stdout after the ScreenCaptureKit stream has
      stopped. SIGINT stops capture, drains already accepted PCM in order, closes
      stdout, releases stream and conversion resources, and exits with status 130.
- [x] A downstream broken pipe stops capture promptly, reports no traceback or
      PCM-contaminating diagnostic, releases resources, and exits unsuccessfully.
- [x] The producer remains alive through periods of system silence without
      fabricating samples solely to keep the pipe active; subsequent audible audio
      resumes in the same capture session.
- [x] Fast tests exercise conversion, mono mixing, fragmented output writes,
      ordering, overload, permission denial, stream failure, interruption, and
      broken-pipe behavior through controlled buffers and adapters without needing
      real ScreenCaptureKit permission or playing audio through a speaker.
- [x] An opt-in acceptance test on the reference Mac plays a known Source Armenian
      fixture through a normal system-output application, pipes the native producer
      directly into `caraway live --input-format f32le -`, and obtains useful
      English before playback finishes.
- [x] The acceptance record includes the macOS version, output audio device,
      permission state, time from audible source start to first accepted PCM,
      capture-queue peak, producer termination reason, and the existing live
      translation latency and backlog measurements.
- [x] Capture adds no echo, muting, or audible routing change: the source remains
      audible through the selected macOS output device while its system mix is
      captured.

## Comments

Merged in [PR #8](https://github.com/tjvjk/caraway/pull/8) on 2026-09-07.
Automated CI and the controlled fast suite passed. The real ScreenCaptureKit
acceptance remains opt-in because it requires macOS privacy permission, audible
fixture playback, and the installed production model.
