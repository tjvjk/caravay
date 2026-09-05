# 10: Expose managed model status through a runnable CLI

**What to build:** Establish a runnable development version of `caraway` and make
`caraway models status` report whether the pinned managed model snapshot is ready,
missing, or invalid. The slice includes strict macOS user configuration and the
subprocess boundary used by later behavior tests, but does not download or load
the model.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent
**State:** closed
**Closed by:** https://github.com/tjvjk/caraway/pull/1

- [x] The development environment uses Python `>=3.13,<3.14`, pins PyTorch 2.14.0
      and Transformers 5.16.1, and exposes a runnable `caraway` command without
      claiming distribution packaging.
- [x] `caraway [--config PATH] models status` accepts no model name and writes
      exactly `ready`, `missing`, or `invalid` plus LF to stdout.
- [x] Ready returns status 0; missing and invalid return status 1; human detail may
      appear only on stderr.
- [x] The optional default TOML configuration is read from the specified macOS
      application-support location, while `--config` replaces that source.
- [x] An absent default config uses packaged defaults; a missing explicit file,
      unreadable or invalid TOML, unknown key, wrong type, or conflicting route
      configuration produces `invalid_config`, status 2, and empty stdout.
- [x] Configuration values resolve in CLI, configured, then packaged-default
      order, and no project-local or XDG config is consulted.
- [x] The packaged backend identity, immutable repository revision, default managed
      cache root, and manifest contract match the specification.
- [x] Normal status verification checks manifest shape, identity, required file
      presence, and byte sizes without hashing multi-gigabyte weights.
- [x] Subprocess tests cover observable stdout, stderr, status, config selection,
      and ready/missing/invalid cache states using isolated local fixtures.
