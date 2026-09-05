# Caraway

Caraway is a development CLI for offline Source Armenian language processing on
macOS. The current slice reports whether its pinned managed model is installed.

## Development setup

Install the locked Python 3.13 environment and run the command through `uv`:

```console
uv sync --python 3.13
uv run caraway models status
```

The status command prints exactly one value:

- `ready` with exit status `0` when the managed snapshot is usable;
- `missing` with exit status `1` when it has not been installed; or
- `invalid` with exit status `1` when its manifest or files are inconsistent.

The default optional configuration file is:

```text
~/Library/Application Support/caraway/config.toml
```

Without that file, Caraway uses `~/Library/Caches/caraway` as its managed cache.
To select another configuration file for one invocation, place `--config` before
the command:

```console
uv run caraway --config /path/to/config.toml models status
```

A minimal configuration can change the managed cache location:

```toml
cache_dir = "~/Library/Caches/caraway"
```

Configuration errors leave stdout empty, write an `invalid_config` diagnostic to
stderr, and exit with status `2`. The current development slice only inspects a
local snapshot; model downloading and language-processing commands are not yet
available.
