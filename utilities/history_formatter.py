"""
History Formatter Utility for WebVox.

Converts the chat_history list of dicts into a clean, human-readable block
that can be injected into any LLM prompt template via {chat_history_block}.
"""

from typing import List, Dict, Optional


def format_history_for_prompt(
    chat_history: Optional[List[Dict[str, str]]],
    max_turns: int = 6,
) -> str:
    """
    Render the last `max_turns` conversation turns as a readable block.

    Each turn is formatted as:
        User: <message>
        Assistant: <message>

    Args:
        chat_history: List of {"role": "user"|"assistant", "content": "..."} dicts,
                      ordered oldest-first (as stored in GraphState).
        max_turns:    How many complete turns (user + assistant pairs) to include.
                      Defaults to 6 turns (12 messages) — enough context without
                      bloating the prompt.

    Returns:
        A formatted string ready for prompt injection, or a placeholder string
        if there is no prior history.
    """
    if not chat_history:
        return "(No prior conversation history)"

    # Take only the most recent messages (2 messages per turn)
    recent = chat_history[-(max_turns * 2):]

    lines = []
    for msg in recent:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")

    if not lines:
        return "(No prior conversation history)"

    return "\n".join(lines)
