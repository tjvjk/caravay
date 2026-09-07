// swift-tools-version: 6.2

import PackageDescription

let package = Package(
  name: "SystemAudioCapture",
  platforms: [.macOS(.v13)],
  products: [
    .executable(name: "caraway-capture", targets: ["CarawayCapture"])
  ],
  targets: [
    .executableTarget(name: "CarawayCapture")
  ],
  swiftLanguageModes: [.v5]
)
