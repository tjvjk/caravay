import Darwin
import Foundation

let verbose = CommandLine.arguments.dropFirst() == ["--verbose"]

#if DEBUG
  private struct ScriptEvent: Decodable {
    enum Kind: String, Decodable {
      case audio
      case contentUnavailable = "content_unavailable"
      case eof
      case interruption
      case permissionDenied = "permission_denied"
      case silence
      case streamFailure = "stream_failure"
    }

    let type: Kind
    let sampleRate: Double?
    let channels: Int?
    let samples: [Float]?

    enum CodingKeys: String, CodingKey {
      case type
      case sampleRate = "sample_rate"
      case channels
      case samples
    }
  }
#endif

enum CaptureError: Error, Equatable {
  case brokenPipe
  case contentUnavailable
  case invalidArguments
  case invalidAudio
  case interrupted
  case outputFailure
  case overload
  case permissionDenied
  case streamFailure

  var diagnostic: String {
    switch self {
    case .brokenPipe:
      return "broken_pipe: downstream consumer closed the pipe"
    case .contentUnavailable:
      return "capture_unavailable: ScreenCaptureKit found no display to capture"
    case .invalidArguments:
      return "usage: caraway-capture"
    case .permissionDenied:
      return
        "permission_denied: allow Screen & System Audio Recording for caraway-capture in System Settings > Privacy & Security, then retry"
    case .streamFailure:
      return "stream_failed: system audio capture stopped unexpectedly"
    case .invalidAudio:
      return "conversion_failed: the captured audio format could not be converted"
    case .interrupted:
      return "interrupted: capture stopped by SIGINT"
    case .outputFailure:
      return "output_failed: PCM could not be written to stdout"
    case .overload:
      return "overload: stdout could not keep up with captured audio"
    }
  }

  var code: String {
    diagnostic.split(separator: ":", maxSplits: 1).first.map(String.init) ?? "capture_failed"
  }
}

#if DEBUG
  private func runScript(_ encoded: String) throws {
    let events = try JSONDecoder().decode([ScriptEvent].self, from: Data(encoded.utf8))
    if events.first?.type == .permissionDenied {
      throw CaptureError.permissionDenied
    }
    if events.first?.type == .contentUnavailable {
      throw CaptureError.contentUnavailable
    }
    let conversion = AudioConversion()
    let environment = ProcessInfo.processInfo.environment
    let capacity = Int(environment["CARAWAY_CAPTURE_TEST_QUEUE_CAPACITY"] ?? "8") ?? 8
    let delay = UInt32(environment["CARAWAY_CAPTURE_TEST_WRITE_DELAY_MS"] ?? "0") ?? 0
    let maximumWriteBytes =
      Int(environment["CARAWAY_CAPTURE_TEST_MAX_WRITE_BYTES"] ?? "") ?? .max
    let failAfterWrites = Int(environment["CARAWAY_CAPTURE_TEST_FAIL_AFTER_WRITES"] ?? "")
    let queue = PCMQueue(capacity: max(1, capacity))
    let writer = PCMWriter(
      queue: queue,
      delayMilliseconds: delay,
      maximumWriteBytes: maximumWriteBytes,
      failAfterWrites: failAfterWrites
    )
    writeDiagnostic("capturing system audio; press Ctrl-C to stop")
    writer.start()
    do {
      eventsLoop: for event in events {
        switch event.type {
        case .audio:
          guard let sampleRate = event.sampleRate,
            let channels = event.channels,
            let samples = event.samples
          else {
            throw CaptureError.invalidAudio
          }
          let converted = try conversion.convertControlledBuffer(
            interleaved: samples, sampleRate: sampleRate, channels: channels
          )
          guard queue.enqueue(converted) else { throw CaptureError.overload }
        case .streamFailure:
          throw CaptureError.streamFailure
        case .interruption:
          throw CaptureError.interrupted
        case .eof:
          break eventsLoop
        case .silence:
          Thread.sleep(forTimeInterval: 0.02)
        case .permissionDenied:
          throw CaptureError.permissionDenied
        case .contentUnavailable:
          throw CaptureError.contentUnavailable
        }
      }
      guard queue.enqueue(try conversion.finish()) else { throw CaptureError.overload }
    } catch {
      queue.finish()
      try? writer.wait()
      if verbose {
        let reason = (error as? CaptureError)?.code ?? "capture_failed"
        writeDiagnostic("capture_stopped: reason=\(reason) capture_queue_peak=\(queue.peak)")
      }
      throw error
    }
    queue.finish()
    try writer.wait()
  }
#endif

signal(SIGPIPE, SIG_IGN)

do {
  #if DEBUG
    if let script = ProcessInfo.processInfo.environment["CARAWAY_CAPTURE_TEST_EVENTS"] {
      try runScript(script)
      exit(0)
    }
  #endif
  guard CommandLine.arguments.count == 1 || verbose else {
    throw CaptureError.invalidArguments
  }
  try runSystemCapture()
} catch {
  let message = (error as? CaptureError)?.diagnostic ?? "capture_failed: \(error)"
  if (error as? CaptureError) != .interrupted || verbose {
    writeDiagnostic(message)
  }
  exit((error as? CaptureError) == .interrupted ? 130 : 1)
}
