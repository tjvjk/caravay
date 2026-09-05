"""Run the heavyweight SeamlessM4T text translation backend."""

from pathlib import Path
from typing import Any, cast

import torch
from transformers import AutoProcessor, SeamlessM4Tv2ForTextToText

from caraway.translation import Issue, Result, ValidationError, trim


def validate() -> bool:
    """Require the configured MPS runtime without allowing CPU fallback."""
    if not torch.backends.mps.is_available():
        raise ValidationError(
            "mps_unavailable: Apple Metal acceleration is unavailable"
        )
    return True


def translate(path: Path, source: str, target: str, text: str) -> Result:
    """Translate one text segment offline on MPS with FP16."""
    processors = cast(Any, AutoProcessor)
    models = cast(Any, SeamlessM4Tv2ForTextToText)
    processor = processors.from_pretrained(path, local_files_only=True)
    model = (
        models.from_pretrained(
            path,
            local_files_only=True,
            dtype=torch.float16,
        )
        .to("mps")
        .eval()
    )
    inputs = processor(text=text, src_lang=source, return_tensors="pt").to("mps")
    with torch.inference_mode():
        tokens = model.generate(**inputs, tgt_lang=target)
    generated = processor.decode(tokens[0], skip_special_tokens=True).strip()
    output = trim(generated)
    if output != generated:
        issue = Issue(
            "text_to_text", "repetition", "repeating translation suffix was removed"
        )
        if output:
            return Result("degraded", output, (issue,))
        return Result("skipped", "", (issue,))
    if not output:
        issue = Issue(
            "text_to_text", "empty_output", "translation produced no useful text"
        )
        return Result("skipped", "", (issue,))
    return Result("completed", output, ())
