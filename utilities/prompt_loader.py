"""
Prompt Loader Utility for WebVox.
Loads LLM prompt templates from the agents/ folder and substitutes variables.
"""

import os
from typing import Dict, Any, Optional


# Project root is 1 level above the utilities/ directory
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AGENTS_DIR = os.path.join(_PROJECT_ROOT, "agents")

# Cache loaded prompt templates to avoid repeated disk reads
_prompt_cache: Dict[str, str] = {}


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
                   Keys should match {placeholder} names in the prompt file.

    Returns:
        The prompt string with all variables substituted.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        KeyError: If a required placeholder is missing from variables.
    """
    cache_key = f"{agent_name}/{prompt_file}"

    # Load template from cache or disk
    if cache_key not in _prompt_cache:
        prompt_path = os.path.join(_AGENTS_DIR, agent_name, prompt_file)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}"
            )
        with open(prompt_path, "r", encoding="utf-8") as f:
            _prompt_cache[cache_key] = f.read()

    template = _prompt_cache[cache_key]

    # Substitute variables if provided
    if variables:
        return template.format_map(variables)

    return template


def clear_prompt_cache():
    """Clear the prompt template cache (useful for development/hot-reload)."""
    _prompt_cache.clear()
