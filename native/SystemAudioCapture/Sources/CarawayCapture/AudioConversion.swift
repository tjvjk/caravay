import AVFAudio
import CoreAudio
import CoreMedia
import Foundation

final class AudioConversion {
  private let target = AVAudioFormat(
    commonFormat: .pcmFormatFloat32,
    sampleRate: 16_000,
    channels: 1,
    interleaved: false
  )!
  private var converter: AVAudioConverter?
  private var source: AVAudioFormat?

  #if DEBUG
    func convertControlledBuffer(
      interleaved samples: [Float], sampleRate: Double, channels: Int
    ) throws -> Data {
      guard channels > 0, samples.count.isMultiple(of: channels) else {
        throw CaptureError.invalidAudio
      }
      let bytesPerFrame = channels * MemoryLayout<Float>.size
      let description = AudioStreamBasicDescription(
        mSampleRate: sampleRate,
        mFormatID: kAudioFormatLinearPCM,
        mFormatFlags: kAudioFormatFlagIsFloat | kAudioFormatFlagIsPacked,
        mBytesPerPacket: UInt32(bytesPerFrame),
        mFramesPerPacket: 1,
        mBytesPerFrame: UInt32(bytesPerFrame),
        mChannelsPerFrame: UInt32(channels),
        mBitsPerChannel: 32,
        mReserved: 0
      )
      let format = try CMAudioFormatDescription(audioStreamBasicDescription: description)
      let block = try CMBlockBuffer(length: samples.count * MemoryLayout<Float>.size)
      try samples.withUnsafeBytes { try block.replaceDataBytes(with: $0) }
      let timing = CMSampleTimingInfo(
        duration: CMTime(value: 1, timescale: CMTimeScale(sampleRate)),
        presentationTimeStamp: .zero,
        decodeTimeStamp: .invalid
      )
      let sampleBuffer = try CMSampleBuffer(
        dataBuffer: block,
        formatDescription: format,
        numSamples: samples.count / channels,
        sampleTimings: [timing],
        sampleSizes: [bytesPerFrame]
      )
      return try convert(sampleBuffer)
    }
  #endif

  func convert(_ sampleBuffer: CMSampleBuffer) throws -> Data {
    guard sampleBuffer.isValid,
      var description = sampleBuffer.formatDescription?.audioStreamBasicDescription,
      let format = AVAudioFormat(streamDescription: &description)
    else {
      throw CaptureError.invalidAudio
    }
    return try sampleBuffer.withAudioBufferList { buffers, _ in
      guard
        let input = AVAudioPCMBuffer(
          pcmFormat: format, bufferListNoCopy: buffers.unsafePointer
        )
      else {
        throw CaptureError.invalidAudio
      }
      return try convert(input, sourceFormat: format)
    }
  }

  private func convert(_ input: AVAudioPCMBuffer, sourceFormat format: AVAudioFormat) throws -> Data
  {
    var prefix = Data()
    if source != format {
      if converter != nil {
        prefix = try finish()
      }
      source = format
      converter = AVAudioConverter(from: format, to: target)
      converter?.downmix = true
    }
    guard let converter else {
      throw CaptureError.invalidAudio
    }
    let estimate = ceil(Double(input.frameLength) * 16_000 / format.sampleRate) + 32
    guard
      let output = AVAudioPCMBuffer(
        pcmFormat: target,
        frameCapacity: AVAudioFrameCount(estimate)
      )
    else {
      throw CaptureError.invalidAudio
    }
    var supplied = false
    var conversionError: NSError?
    let status = converter.convert(to: output, error: &conversionError) { _, state in
      if supplied {
        state.pointee = .noDataNow
        return nil
      }
      supplied = true
      state.pointee = .haveData
      return input
    }
    guard conversionError == nil, status != .error,
      let channel = output.floatChannelData?[0]
    else {
      throw conversionError ?? CaptureError.invalidAudio
    }
    prefix.append(
      Data(bytes: channel, count: Int(output.frameLength) * MemoryLayout<Float>.size)
    )
    return prefix
  }

  func finish() throws -> Data {
    guard let converter else { return Data() }
    guard let output = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: 64) else {
      throw CaptureError.invalidAudio
    }
    var conversionError: NSError?
    let status = converter.convert(to: output, error: &conversionError) { _, state in
      state.pointee = .endOfStream
      return nil
    }
    guard conversionError == nil, status != .error,
      let channel = output.floatChannelData?[0]
    else {
      throw conversionError ?? CaptureError.invalidAudio
    }
    return Data(bytes: channel, count: Int(output.frameLength) * MemoryLayout<Float>.size)
  }
}
