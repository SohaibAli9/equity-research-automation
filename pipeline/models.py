"""LLM router — model-per-task, with structured-output extraction and prose narration.

Extraction goes to a fast/cheap model (Gemini) with a Pydantic response schema so the
output is structurally guaranteed. Narration goes to a premium reasoning model (Claude).
No model is ever asked to do arithmetic that flows downstream.
"""
from __future__ import annotations

from typing import Optional, Type, TypeVar

from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from . import config
from .logger import usage

T = TypeVar("T", bound=BaseModel)


def load_prompt(name: str, **fmt: object) -> str:
    """Load a prompt file from prompts/ and optionally .format() it. Loaded lazily
    so prompts never live inline in code (project convention)."""
    text = (config.PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    return text.format(**fmt) if fmt else text


# ── Extraction (Gemini, structured output) ────────────────────────────────
@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def extract_structured(
    prompt: str,
    response_schema: Type[T],
    *,
    model: str = config.EXTRACT_MODEL,
    images: Optional[list[bytes]] = None,
    temperature: float = 0.0,
) -> T:
    """Return a validated Pydantic instance of `response_schema`. `images` (PNG bytes)
    are passed alongside the text prompt for vision cross-checks when needed."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    parts: list = [prompt]
    for img in images or []:
        parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))

    resp = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        ),
    )
    if getattr(resp, "usage_metadata", None):
        um = resp.usage_metadata
        usage.add(model, um.prompt_token_count or 0, um.candidates_token_count or 0)
    parsed = resp.parsed
    if parsed is None:  # fall back to manual validation from text
        parsed = response_schema.model_validate_json(resp.text)
    return parsed  # type: ignore[return-value]


# ── Narration (Claude, prose) ─────────────────────────────────────────────
@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
def narrate(
    prompt: str,
    *,
    model: str = config.NARRATIVE_MODEL,
    system: Optional[str] = None,
    max_tokens: int = 2000,
) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    msg = client.messages.create(**kwargs)
    if getattr(msg, "usage", None):
        usage.add(model, msg.usage.input_tokens, msg.usage.output_tokens)
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
