"""
Prompt Loader Utility for WebVox.
Loads LLM prompt templates from the agents/ folder and substitutes variables.
"""

import os
import re
from string import Template
from typing import Dict, Any, Optional


# Project root is 1 level above the utilities/ directory
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AGENTS_DIR = os.path.join(_PROJECT_ROOT, "agents")


class _SafeTemplate(Template):
    """
    A Template subclass that uses $variable / ${variable} delimiters.
    Completely immune to curly-brace content in variable values because
    $ is the delimiter — { and } in substituted values are never re-parsed.
    """
    delimiter = "$"


def load_prompt(
    agent_name: str,
    prompt_file: str,
    variables: Optional[Dict[str, Any]] = None
) -> str:
    """
    Load a prompt template from agents/<agent_name>/<prompt_file>
    and substitute variables.

    Template syntax: use {variable_name} in prompt files (converted internally
    to ${variable_name} for safe substitution). Curly braces that appear inside
    variable *values* (e.g. a user query like "What's in {the} pizza?") are
    passed through verbatim without causing KeyError or mis-substitution.

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
        template_text = f.read()

    if not variables:
        return template_text

    # Convert {variable} placeholders in the template to ${variable} so we can
    # use string.Template, which never re-parses substituted values.
    # Only convert tokens that match a key in `variables` to avoid touching
    # intentional curly braces in the prompt body (e.g. JSON examples).
    def _replace_placeholder(match: re.Match) -> str:
        name = match.group(1)
        if name in variables:
            return f"${{{name}}}"   # {foo} -> ${foo}
        # Not a known variable — leave the original {name} intact
        return match.group(0)

    converted = re.sub(r"\{(\w+)\}", _replace_placeholder, template_text)

    # Substitute using Template — values are never re-scanned for $ or {}
    safe_vars = {k: str(v) for k, v in variables.items()}
    return _SafeTemplate(converted).substitute(safe_vars)
