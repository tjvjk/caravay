"""Remove bounded cyclic-generation suffixes without rewriting retained text."""

import re
import unicodedata


def normalize(token: str) -> str:
    """Normalize one generated token solely for repetition comparison."""
    value = unicodedata.normalize("NFKC", token).casefold()
    return "".join(
        character
        for character in value
        if not unicodedata.category(character).startswith("P")
    )


def trim(text: str) -> str:
    """Remove a suffix made from three or more equivalent generated phrases."""
    matches = tuple(re.finditer(r"\S+", text))
    tokens = tuple(normalize(match.group()) for match in matches)
    for start in range(len(tokens)):
        length = len(tokens) - start
        for size in range(1, (length - 1) // 2 + 1):
            if all(
                tokens[index] == tokens[start + (index - start) % size]
                for index in range(start + size, len(tokens))
            ):
                return text[: matches[start].start()].rstrip()
    return text
