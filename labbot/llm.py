"""LLM client: natural language -> tool calls (Anthropic tool use).

Set ANTHROPIC_API_KEY in your environment. The model can be changed with the
LABBOT_MODEL environment variable (default below).
"""

import json
import os

from .tools import SYSTEM_PROMPT, TOOLS

DEFAULT_MODEL = "claude-sonnet-5-5"


def _ask(user_message, model=None):
    import anthropic  # imported lazily so the rest of the package works without it

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or os.environ.get("LABBOT_MODEL", DEFAULT_MODEL),
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": user_message}],
    )
    calls, text = [], []
    for block in response.content:
        if block.type == "tool_use":
            calls.append({"tool": block.name, **block.input})
        elif block.type == "text":
            text.append(block.text)
    return calls, "\n".join(text).strip()


def instruction_to_calls(instruction, model=None):
    """Return (calls, assistant_text). calls is a list of {'tool': name, **args}."""
    return _ask(instruction, model)


def retry_with_feedback(instruction, calls, errors, model=None):
    """Second attempt: show the model its own calls and the validator's errors."""
    message = (
        f"{instruction}\n\n---\n"
        "A first attempt at this request made these tool calls:\n"
        f"{json.dumps(calls)}\n\n"
        "A checker that tracks the liquid in every well rejected them:\n"
        + "\n".join(f"- {e}" for e in errors)
        + "\n\nIf the request can be done safely as asked, make corrected tool calls for the "
        "whole request. If it cannot, make no tool calls and explain why."
    )
    return _ask(message, model)
