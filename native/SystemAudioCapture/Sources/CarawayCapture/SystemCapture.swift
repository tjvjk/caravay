import CoreGraphics
import CoreMedia
import Foundation
import ScreenCaptureKit

final class SystemCapture: NSObject, SCStreamDelegate, SCStreamOutput {
  private let callbackQueue = DispatchQueue(label: "caraway.capture.audio")
  private let conversion = AudioConversion()
  private let pcm = PCMQueue(capacity: 64)
  private let lock = NSLock()
  private var continuation: CheckedContinuation<CaptureError, Never>?
  private var terminal: CaptureError?
  private var stream: SCStream?
  private var interruptSource: DispatchSourceSignal?
  private var recordedFirstPCM = false
  private lazy var writer = PCMWriter(queue: pcm) { [weak self] error in
    self?.terminate(error)
  }

  func run() async throws {
    guard CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess() else {
      throw CaptureError.permissionDenied
    }
    let content: SCShareableContent
    do {
      content = try await SCShareableContent.excludingDesktopWindows(
        false, onScreenWindowsOnly: false
      )
    } catch {
      throw map(error)
    }
    guard let display = content.displays.first else {
      throw CaptureError.contentUnavailable
    }

    let configuration = SCStreamConfiguration()
    configuration.capturesAudio = true
    configuration.sampleRate = 16_000
    configuration.channelCount = 1
    configuration.excludesCurrentProcessAudio = true
    let filter = SCContentFilter(
      display: display, excludingApplications: [], exceptingWindows: []
    )
    let stream = SCStream(filter: filter, configuration: configuration, delegate: self)
    self.stream = stream
    do {
      try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: callbackQueue)
    } catch {
      throw CaptureError.contentUnavailable
    }

    writer.start()
    installInterruptHandler()
    do {
      try await stream.startCapture()
    } catch {
      pcm.finish()
      try? writer.wait()
      throw map(error)
    }
    writeDiagnostic("capturing system audio; press Ctrl-C to stop")
    let ending = await withCheckedContinuation { continuation in
      lock.lock()
      if let terminal {
        lock.unlock()
        continuation.resume(returning: terminal)
      } else {
        self.continuation = continuation
        lock.unlock()
      }
    }
    throw ending
  }

  func stream(
    _ stream: SCStream,
    didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
    of outputType: SCStreamOutputType
  ) {
    guard outputType == .audio else { return }
    do {
      let data = try conversion.convert(sampleBuffer)
      if verbose, !data.isEmpty, !recordedFirstPCM {
        recordedFirstPCM = true
        writeDiagnostic("first_pcm: uptime_seconds=\(ProcessInfo.processInfo.systemUptime)")
      }
      guard pcm.enqueue(data) else {
        terminate(.overload)
        return
      }
    } catch {
      terminate(.invalidAudio)
    }
  }

  func stream(_ stream: SCStream, didStopWithError error: Error) {
    terminate(map(error))
  }

  private func installInterruptHandler() {
    signal(SIGINT, SIG_IGN)
    let source = DispatchSource.makeSignalSource(signal: SIGINT)
    source.setEventHandler { [weak self] in self?.terminate(.interrupted) }
    source.resume()
    interruptSource = source
  }

  private func terminate(_ reason: CaptureError) {
    lock.lock()
    guard terminal == nil else {
      lock.unlock()
      return
    }
    terminal = reason
    let stream = stream
    lock.unlock()
    if reason == .overload {
      pcm.finish()
    }
    Task {
      var ending = reason
      try? await stream?.stopCapture()
      callbackQueue.sync {
        if reason == .interrupted || reason == .streamFailure {
          do {
            let tail = try conversion.finish()
            if !pcm.enqueueWhileDraining(tail) {
              ending = .overload
            }
          } catch {
            ending = .invalidAudio
          }
        }
        pcm.finish()
      }
      do {
        try writer.wait()
      } catch let error as CaptureError {
        ending = error
      } catch {
        ending = .outputFailure
      }
      if verbose {
        writeDiagnostic("capture_stopped: reason=\(ending.code) capture_queue_peak=\(pcm.peak)")
      }
      takeContinuation()?.resume(returning: ending)
    }
  }

  private func takeContinuation() -> CheckedContinuation<CaptureError, Never>? {
    lock.lock()
    defer { lock.unlock() }
    let result = continuation
    continuation = nil
    return result
  }

  private func map(_ error: Error) -> CaptureError {
    let cocoa = error as NSError
    if cocoa.domain == SCStreamError.errorDomain,
      cocoa.code == SCStreamError.Code.userDeclined.rawValue
    {
      return .permissionDenied
    }
    return .streamFailure
  }
}

func runSystemCapture() throws {
  let completed = DispatchSemaphore(value: 0)
  let result = LockedResult()
  Task {
    do {
      try await SystemCapture().run()
    } catch {
      result.set(error)
    }
    completed.signal()
  }
  completed.wait()
  throw result.get() ?? CaptureError.streamFailure
}

private final class LockedResult {
  private let lock = NSLock()
  private var error: Error?

  func set(_ error: Error) {
    lock.lock()
    self.error = error
    lock.unlock()
  }

  func get() -> Error? {
    lock.lock()
    defer { lock.unlock() }
    return error
  }
}

func writeDiagnostic(_ message: String) {
  FileHandle.standardError.write(Data("\(message)\n".utf8))
}
