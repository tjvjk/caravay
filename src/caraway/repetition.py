"""Remove bounded cyclic-generation suffixes without rewriting retained text."""

import re
import unicodedata


def normalize(token: str) -> str:
    """Normalize one generated token solely for repetition comparison."""
    start = 0
    end = len(token)
    while start < end and unicodedata.category(token[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(token[end - 1]).startswith("P"):
        end -= 1
    return token[start:end]


def trim(text: str, limited: bool) -> str:
    """Remove a suffix made from three or more equivalent generated phrases."""
    matches = tuple(re.finditer(r"\S+", text))
    tokens = tuple(normalize(match.group()) for match in matches)
    for start in range(len(tokens)):
        length = len(tokens) - start
        for size in range(1, (length - 1) // 2 + 1):
            bounded = length >= size * 3 or limited
            if bounded and all(
                tokens[index] == tokens[start + (index - start) % size]
                for index in range(start + size, len(tokens))
            ):
                return text[: matches[start].start()].rstrip()
    return text
