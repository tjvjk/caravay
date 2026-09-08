# Homebrew distribution

The formula lives in
[`tjvjk/homebrew-tap`](https://github.com/tjvjk/homebrew-tap/blob/main/Formula/caravay.rb).
It installs the release wheel and the runtime dependency wheels into Homebrew's
isolated Python 3.13 environment. It supports Apple Silicon and macOS 14 or newer.
The model is downloaded separately by the user; it is not a release asset.

## Preparing a release

Build the wheel from the exact source commit being released, with a new version
in `pyproject.toml` for each subsequent release:

```sh
python3.13 -m pip wheel --no-deps --wheel-dir dist .
shasum -a 256 dist/caravay-*.whl
```

Use a clean output directory so only the intended version is uploaded. Attach
the wheel to the matching GitHub release (`v<version>`), and update the formula's
`url`, `version`, and `sha256`. Never overwrite an existing release asset with
different bytes.

The formula's resource URLs and SHA-256 hashes come from `uv.lock`. When
dependencies change, include the complete runtime dependency closure, evaluating
environment markers for CPython 3.13 on macOS arm64 and excluding development
dependencies. Choose wheels compatible with the minimum supported macOS version,
including universal wheels where applicable. Native wheels are intentional:
installation must not compile PyTorch or require a Rust toolchain.

Each resource is staged without unpacking and installed with dependency
resolution disabled. Homebrew fetches and verifies every wheel before the
installation begins. The formula test runs `pip check` to catch missing or
incompatible dependencies and imports the model runtime without downloading it.

## Validation

Before publication, test the formula with a local `file://` URL for the release
wheel and its real checksum. Restore the GitHub release URL before committing:

```sh
brew install --build-from-source tjvjk/tap/caravay
brew test tjvjk/tap/caravay
brew style tjvjk/tap/caravay
```

Use `brew reinstall` if a previous version is already installed. After publishing
the release asset, verify `brew fetch tjvjk/tap/caravay` against the public URL,
then publish the formula update in the tap.

`caravay-audio` has its own formula and release process in the same tap.
