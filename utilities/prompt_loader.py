"""
Prompt Loader Utility for WebVox.
Loads LLM prompt templates from the agents/ folder and substitutes variables.
"""

import os
from typing import Dict, Any, Optional


# Project root is 1 level above the utilities/ directory
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AGENTS_DIR = os.path.join(_PROJECT_ROOT, "agents")


def load_prompt(
    agent_name: str,
    prompt_file: str,
    variables: Optional[Dict[str, Any]] = None
) -> str:
    """
    Load a prompt template from agents/<agent_name>/<prompt_file>
    and substitute variables using Python's str.format_map().

    Args:
        agent_name: Name of the agent folder (e.g., "intent_detector")
        prompt_file: Name of the prompt file (e.g., "classify_intent.prompt.txt")
        variables: Dictionary of variables to substitute into the template.

    Returns:
        The prompt string with all variables substituted.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        KeyError: If a required placeholder is missing from variables.
    """

    prompt_path = os.path.join(_AGENTS_DIR, agent_name, prompt_file)

    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    # ALWAYS read fresh from disk (no caching)
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Substitute variables if provided
    if variables:
        return template.format_map(variables)

    return template