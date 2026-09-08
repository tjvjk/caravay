# Define configuration and model lifecycle

Type: grilling
Status: resolved
Blocked by: 04, 05

## Question

How should CLI overrides, the user configuration file, model download and cache behavior, offline enforcement, device selection, and first-run failures work for the chosen model/runtime on macOS?

## Answer

### Configuration source and precedence

The optional user configuration file is TOML at
`~/Library/Application Support/caravay/config.toml`. Caravay does not search the
working directory or XDG paths for configuration in the macOS-only MVP. A global
`--config PATH` selects a different file for the current invocation; it changes the
file source, not the precedence rules.

An absent default file is valid and uses packaged defaults. A missing explicitly
selected file, unreadable file, invalid TOML, unknown key, wrong value type, or
conflicting route configuration is an `invalid_config` validation error. The
diagnostic identifies the offending dotted key where possible, such as
`commands.run.backend`.

For every configurable routing value, resolution remains CLI option, configured
value, then packaged default, as defined in issue 06. A CLI option overrides only
its corresponding value. The MVP has no project-local configuration or CLI
override for the cache root.

The accepted configuration shape is:

```toml
cache_dir = "~/Library/Caches/caravay"

[commands.transcribe]
backend = "seamlessm4t-large-v2"

[commands.translate]
backend = "seamlessm4t-large-v2"

[commands.run]
route = "composed"
speech_backend = "seamlessm4t-large-v2"
translation_backend = "seamlessm4t-large-v2"
```

Every table and key is optional. For a fused route, `commands.run.backend` replaces
the two composed backend keys; the route-specific keys cannot coexist. The shown
values are the packaged defaults. Route-specific conflicts are rejected according
to issue 06. Backend names resolve to packaged backend definitions: users cannot
set a model repository or revision in this file.

### Packaged model and cache

The packaged backend `seamlessm4t-large-v2` resolves to:

- model repository `facebook/seamless-m4t-v2-large`;
- immutable revision `5f8cc790b19fc3f67a61c105133b20b34e3dcb76`,
  observed on 2026-09-04;
- the processor, speech-to-text weights, and text-to-text weights required by the
  composed pipeline from issues 04 and 05.

Changing that revision is a packaged Caravay update, never an automatic cache
refresh. The default managed cache root is `~/Library/Caches/caravay`; model
snapshots live below it by backend name and revision. Caravay does not treat an
arbitrary entry in the shared Hugging Face cache as an installed model.

A ready snapshot has a Caravay manifest containing the backend name, repository,
revision, and expected files with their byte sizes and cryptographic digests. After
download, Caravay verifies every expected file and its digest before publishing the
snapshot. At normal command startup it verifies the manifest, identity, file
presence, and sizes but does not rehash the multi-gigabyte weights. A missing
snapshot is `model_not_installed`; a malformed manifest, identity mismatch,
missing file, or size mismatch is `model_cache_invalid`.

### Model-management commands

The MVP provides:

```text
caravay [--config PATH] models download
caravay [--config PATH] models status
```

There is one packaged model snapshot, so neither command accepts a model name.
Removal, forced reinstall, selecting arbitrary Hugging Face models, and automatic
updates are outside the MVP.

`models download` is the only operation allowed to fetch model data. It acquires a
lock for the target backend and revision. If another downloader holds the lock, it
fails with `download_in_progress` rather than writing concurrently. It downloads
into a temporary directory on the same filesystem as the final snapshot, retains
usable partial data after an interruption so a later invocation can resume, and
atomically renames the verified directory into place. A network, storage, or
verification failure is `download_failed`, returns status `1`, and never publishes
an incomplete snapshot or damages an existing ready snapshot.

If the target path contains an invalid snapshot, the downloader first verifies a
complete replacement in its temporary directory. While holding the lock, it
renames the invalid directory to a quarantine path, atomically renames the verified
replacement to the target path, and then removes the quarantine. If publication
fails, it restores the quarantined directory; a later invocation also recovers any
quarantine left by process interruption before proceeding. A ready snapshot is
never displaced: the idempotent success path below applies instead.

When the pinned snapshot is already ready, `models download` succeeds without a
network request. Progress goes only to stderr. A normal successful download also
returns status `0`; it emits no primary result on stdout.

`models status` performs the normal startup verification without network access.
It writes exactly one of `ready`, `missing`, or `invalid`, followed by LF, to stdout.
`ready` returns status `0`; `missing` and `invalid` return status `1`. Human detail
may be written to stderr. JSON output for model-management commands is outside the
MVP.

### Offline execution and device

`transcribe`, `translate`, and `run` never download, update, or probe a remote
model repository. They resolve the packaged snapshot to an explicit local path,
enable the Hugging Face offline controls, and load every processor and model with
local-files-only behavior. The local snapshot path is the primary enforcement
boundary; library offline flags are defense in depth against incidental requests.
Once `models download` has succeeded, ordinary processing therefore requires no
network access.

The MVP supports the selected runtime only on a supported Apple-Silicon Mac using
PyTorch MPS and FP16. There is no device option, automatic device selection, CPU
mode, or runtime fallback. Before loading the model, a working command checks the
host and MPS availability. Failure is `mps_unavailable`, a validation/environment
error with status `2`. Issue 09 owns the exact supported Mac and runtime versions.

### Validation order and first-run failures

Before model loading or primary output, a working command validates, in order:

1. arguments and the selected configuration file;
2. input and the complete execution plan from issue 06;
3. the required managed model snapshot;
4. the Apple-Silicon MPS runtime.

The first failure stops validation. `invalid_config`, `model_not_installed`,
`model_cache_invalid`, and `mps_unavailable` return status `2`, write no stdout,
and produce a human-readable stderr diagnostic containing the stable code. A
missing-model diagnostic tells the user to run `caravay models download`.

Model-management failures use `download_in_progress` or `download_failed` and
return status `1`. These six reason codes are stable; their human-readable messages
are not. No failure triggers a backend substitution, CPU fallback, network access
from a working command, or implicit repair. Processing-time outcomes and their
exit statuses remain those defined in issues 05–07.
