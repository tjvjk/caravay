"""Run the heavyweight SeamlessM4T text translation backend."""

from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import torch
from transformers import (
    AutoProcessor,
    SeamlessM4Tv2ForSpeechToText,
    SeamlessM4Tv2ForTextToText,
    logging,
)

from caraway import transcription
from caraway.repetition import trim
from caraway.translation import Issue, Result, ValidationError


@dataclass(frozen=True)
class Backend:
    """Hold the loaded processor and text translation model."""

    processor: Any
    model: Any


@dataclass(frozen=True)
class Speech:
    """Hold the loaded processor and speech recognition model."""

    processor: Any
    model: Any


def configure(verbose: bool) -> bool:
    """Select quiet default output or professional backend diagnostics."""
    logs = cast(Any, logging)
    if verbose:
        logs.set_verbosity_warning()
        logs.enable_progress_bar()
        return True
    logs.set_verbosity_error()
    logs.disable_progress_bar()
    return True


def validate(verbose: bool) -> bool:
    """Require the configured MPS runtime without allowing CPU fallback."""
    configure(verbose)
    if not torch.backends.mps.is_available():
        raise ValidationError(
            "mps_unavailable: Apple Metal acceleration is unavailable"
        )
    return True


def load(path: Path) -> Backend:
    """Load the pinned processor and FP16 text model onto MPS."""
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
    return Backend(processor, model)


def generate(backend: Backend, source: str, target: str, text: str) -> str:
    """Generate and decode one text translation on MPS."""
    inputs = backend.processor(text=text, src_lang=source, return_tensors="pt").to(
        "mps"
    )
    with torch.inference_mode():
        tokens = backend.model.generate(**inputs, tgt_lang=target)
    generated = backend.processor.decode(
        tokens[0],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    ).strip()
    return cast(str, generated)


def resolve(generated: str) -> Result:
    """Map generated text and repetition damage to a segment outcome."""
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


def translate(path: Path, source: str, target: str, text: str) -> Result:
    """Translate one text segment offline on MPS with FP16."""
    backend = load(path)
    generated = generate(backend, source, target, text)
    return resolve(generated)


def recognize(path: Path) -> Speech:
    """Load the pinned processor and FP16 speech model onto MPS."""
    processors = cast(Any, AutoProcessor)
    models = cast(Any, SeamlessM4Tv2ForSpeechToText)
    processor = processors.from_pretrained(path, local_files_only=True)
    model = (
        models.from_pretrained(path, local_files_only=True, dtype=torch.float16)
        .to("mps")
        .eval()
    )
    return Speech(processor, model)


def transcribe(
    backend: object, source: str, audio: array[float]
) -> transcription.Result:
    """Transcribe one audio segment offline on MPS with FP16."""
    speech = cast(Speech, backend)
    inputs = speech.processor(
        audio=list(audio), sampling_rate=16_000, return_tensors="pt"
    )
    values = {
        name: value.to(device="mps", dtype=torch.float16)
        for name, value in inputs.items()
    }
    with torch.inference_mode():
        tokens = speech.model.generate(**values, tgt_lang=source, max_new_tokens=256)
    generated = speech.processor.decode(
        tokens[0],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return transcription.resolve(cast(str, generated))
