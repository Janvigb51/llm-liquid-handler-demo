"""LLM client: natural language -> tool calls (Anthropic tool use).

Set ANTHROPIC_API_KEY in your environment. The model can be changed with the
LABBOT_MODEL environment variable (default below).
"""

import os

from .tools import SYSTEM_PROMPT, TOOLS

DEFAULT_MODEL = "claude-sonnet-5-5"


def instruction_to_calls(instruction, model=None):
    """Return (calls, assistant_text). calls is a list of {'tool': name, **args}."""
    import anthropic  # imported lazily so the rest of the package works without it

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model or os.environ.get("LABBOT_MODEL", DEFAULT_MODEL),
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": instruction}],
    )
    calls, text = [], []
    for block in response.content:
        if block.type == "tool_use":
            calls.append({"tool": block.name, **block.input})
        elif block.type == "text":
            text.append(block.text)
    return calls, "\n".join(text).strip()
