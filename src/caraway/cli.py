"""Command-line entry point for Caraway."""

import argparse
import io
import sys
from pathlib import Path

from caraway.models import DownloadError, DownloadLockError, download, inspect
from caraway.settings import InvalidConfigError, Settings, load


def parser() -> argparse.ArgumentParser:
    """Build the development command parser."""
    result = argparse.ArgumentParser(prog="caraway")
    result.add_argument("--config", type=Path)
    result.add_argument("--quiet", action="store_true")
    commands = result.add_subparsers(dest="command", required=True)
    models = commands.add_parser("models")
    actions = models.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
    actions.add_parser("download")
    return result


def main() -> int:
    """Run the Caraway command-line interface."""
    arguments = parser().parse_args()
    try:
        config = (
            load(Settings.config_path, True)
            if arguments.config is None
            else load(arguments.config, False)
        )
    except InvalidConfigError as error:
        print(error, file=sys.stderr)
        return 2
    if arguments.action == "status":
        state = inspect(config.cache_dir)
        print(state)
        return 0 if state == "ready" else 1
    try:
        progress = io.StringIO() if arguments.quiet else sys.stderr
        download(config.cache_dir, progress)
    except DownloadLockError as error:
        print(f"download_in_progress: {error}", file=sys.stderr)
        return 1
    except DownloadError as error:
        print(f"download_failed: {error}", file=sys.stderr)
        return 1
    return 0
