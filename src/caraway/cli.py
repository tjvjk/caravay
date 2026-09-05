"""Command-line entry point for Caraway."""

import argparse
import sys
from pathlib import Path

from caraway.models import inspect
from caraway.settings import InvalidConfigError, Settings, load


def parser() -> argparse.ArgumentParser:
    """Build the development command parser."""
    result = argparse.ArgumentParser(prog="caraway")
    result.add_argument("--config", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    models = commands.add_parser("models")
    actions = models.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
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
    state = inspect(config.cache_dir)
    print(state)
    return 0 if state == "ready" else 1
