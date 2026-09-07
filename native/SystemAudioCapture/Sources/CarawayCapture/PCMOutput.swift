import Darwin
import Foundation

final class PCMQueue {
  private let capacity: Int
  private let condition = NSCondition()
  private var closed = false
  private var chunks: [Data] = []
  private var highWater = 0

  init(capacity: Int) {
    self.capacity = capacity
  }

  func enqueue(_ data: Data) -> Bool {
    guard !data.isEmpty else { return true }
    condition.lock()
    defer { condition.unlock() }
    guard !closed, chunks.count < capacity else { return false }
    append(data)
    return true
  }

  func next() -> Data? {
    condition.lock()
    defer { condition.unlock() }
    while chunks.isEmpty, !closed {
      condition.wait()
    }
    guard !chunks.isEmpty else { return nil }
    let chunk = chunks.removeFirst()
    condition.signal()
    return chunk
  }

  func enqueueWhileDraining(_ data: Data) -> Bool {
    guard !data.isEmpty else { return true }
    condition.lock()
    defer { condition.unlock() }
    while !closed, chunks.count >= capacity {
      condition.wait()
    }
    guard !closed else { return false }
    append(data)
    return true
  }

  private func append(_ data: Data) {
    chunks.append(data)
    highWater = max(highWater, chunks.count)
    condition.signal()
  }

  func finish() {
    condition.lock()
    closed = true
    condition.broadcast()
    condition.unlock()
  }

  var peak: Int {
    condition.lock()
    defer { condition.unlock() }
    return highWater
  }
}

final class PCMWriter {
  private let queue: PCMQueue
  private let descriptor: Int32
  private let delay: useconds_t
  private let failAfterWrites: Int?
  private let maximumWriteBytes: Int
  private let completed = DispatchSemaphore(value: 0)
  private let onFailure: (CaptureError) -> Void
  private let lock = NSLock()
  private var storedError: CaptureError?

  init(
    queue: PCMQueue,
    descriptor: Int32 = STDOUT_FILENO,
    delayMilliseconds: UInt32 = 0,
    maximumWriteBytes: Int = .max,
    failAfterWrites: Int? = nil,
    onFailure: @escaping (CaptureError) -> Void = { _ in }
  ) {
    self.queue = queue
    self.descriptor = descriptor
    delay = delayMilliseconds * 1_000
    self.maximumWriteBytes = maximumWriteBytes
    self.failAfterWrites = failAfterWrites
    self.onFailure = onFailure
  }

  func start() {
    Thread {
      defer { self.completed.signal() }
      while let data = self.queue.next() {
        if self.delay > 0 { usleep(self.delay) }
        guard self.writeAll(data) else { return }
      }
    }.start()
  }

  func wait() throws {
    completed.wait()
    lock.lock()
    defer { lock.unlock() }
    if let storedError { throw storedError }
  }

  private func writeAll(_ data: Data) -> Bool {
    data.withUnsafeBytes { bytes in
      var offset = 0
      var writes = 0
      while offset < bytes.count {
        if let failAfterWrites, writes >= failAfterWrites {
          store(.outputFailure)
          return false
        }
        let requested = min(maximumWriteBytes, bytes.count - offset)
        let written = Darwin.write(
          descriptor, bytes.baseAddress!.advanced(by: offset), requested
        )
        if written > 0 {
          offset += written
          writes += 1
        } else if written < 0, errno == EINTR {
          continue
        } else {
          store(errno == EPIPE ? .brokenPipe : .outputFailure)
          return false
        }
      }
      return true
    }
  }

  private func store(_ failure: CaptureError) {
    lock.lock()
    storedError = failure
    lock.unlock()
    onFailure(failure)
  }
}
