# 11: Download and publish the pinned model snapshot safely

**What to build:** Make `caraway models download` acquire, verify, and atomically
publish the one pinned SeamlessM4T Large v2 snapshot into Caraway's managed cache,
while preserving usable partial downloads and never damaging an existing ready
snapshot.

**Blocked by:** 10 / Expose managed model status through a runnable CLI

**Status:** ready-for-agent

- [ ] `caraway [--config PATH] models download` accepts no model name and is the
      only command permitted to fetch model data.
- [ ] The command downloads the processor plus speech-to-text and text-to-text
      files for the exact packaged repository revision into temporary state on the
      destination filesystem.
- [ ] Publication requires a manifest with expected byte sizes and cryptographic
      digests, verifies every digest, and atomically makes the snapshot ready.
- [ ] Interrupted transfers retain resumable partial data without exposing an
      incomplete snapshot as ready.
- [ ] A per-snapshot lock rejects a concurrent downloader with
      `download_in_progress`, status 1, and no primary stdout.
- [ ] Starting or resuming a transfer, or preparing invalid-snapshot replacement,
      requires at least 20 GiB free; the ready idempotent path does not.
- [ ] An invalid snapshot is replaced through recoverable quarantine and atomic
      publication; failed publication restores it, and a later invocation recovers
      quarantine left by process interruption.
- [ ] A network, storage, or verification failure reports `download_failed`,
      returns 1, and neither publishes incomplete data nor damages a ready snapshot.
- [ ] An already ready snapshot returns 0 without a network request; all success
      paths keep stdout empty and send progress only to interactive stderr.
- [ ] Successful publication retains no second complete model copy in the managed
      cache and remains observable as `ready` through ticket 10's command.
- [ ] Subprocess tests exercise success, resume, locking, invalid replacement,
      recovery, insufficient space, failure safety, and idempotence through local
      controlled download fixtures.

