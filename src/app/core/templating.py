"""Jinja2 environment for prompt templates. Autoescape is off on purpose:
these render plain text for a model, not HTML. Anything untrusted is
wrapped by the guardrails before it reaches a template variable."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_ROOT = Path(__file__).resolve().parents[1] / "modules"


def environment(module: str) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_ROOT / module / "templates")),
        autoescape=False,  # noqa: S701 - plain-text prompts, not HTML
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
