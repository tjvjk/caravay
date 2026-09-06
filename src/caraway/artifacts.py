"""Remove recognizable generated error markers from useful text."""

import re
from typing import Final

from caraway.translation import ValidationError

MARKER: Final = re.compile(r"(?<![\w#])#(?:err|er)(?![\w#])")
HASHES: Final = 8


def remove(text: str, hashes: int = HASHES) -> str:
    """Replace error markers and bounded hash runs without joining nearby text."""
    cleaned = MARKER.sub(" ", text)
    return re.sub(rf"#{{{hashes},}}", " ", cleaned).strip()


def useful(text: str) -> bool:
    """Report whether cleaned text retains a word, number, or healthy hash."""
    return any(character.isalnum() or character == "#" for character in text)


def threshold(value: int) -> int:
    """Require a bounded hash-run threshold that preserves a single hash."""
    if value < 2 or value > 256:
        raise ValidationError(
            "invalid_generation_guard: artifact hash threshold must be 2 through 256"
        )
    return value
