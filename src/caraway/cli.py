"""Command-line entry point for Caraway."""

import argparse
import sys
from pathlib import Path

from caraway.config import InvalidConfigError, load
from caraway.models import inspect


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
    default = (
        Path.home() / "Library" / "Application Support" / "caraway" / "config.toml"
    )
    try:
        config = (
            load(default, True)
            if arguments.config is None
            else load(arguments.config, False)
        )
    except InvalidConfigError as error:
        print(error, file=sys.stderr)
        return 2
    state = inspect(config.cache)
    print(state)
    return 0 if state == "ready" else 1
