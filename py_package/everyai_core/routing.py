"""Smart Auto-Pilot Routing for everyai-core.

Provides user-defined routing presets for speed, intelligence, and balanced
operation across any combination of providers and models.
"""


# Prioritized fallbacks matching different user requirements
ROUTING_PRESETS = {
    "fastest": [
        {"provider": "groq", "model": "llama3-8b-8192"},
        {"provider": "openrouter", "model": "meta-llama/llama-3-8b-instruct"},
        {"provider": "huggingface", "model": "meta-llama/Meta-Llama-3-8B-Instruct"},
    ],
    "smartest": [
        {"provider": "groq", "model": "llama3-70b-8192"},
        {"provider": "openrouter", "model": "google/gemini-flash-1.5"},
        {"provider": "openrouter", "model": "anthropic/claude-3-haiku"},
    ],
    "balanced": [
        {"provider": "groq", "model": "llama3-70b-8192"},
        {"provider": "groq", "model": "llama3-8b-8192"},
        {"provider": "openrouter", "model": "meta-llama/llama-3-8b-instruct"},
    ],
}

# Valid mode names that users can configure
VALID_MODES = tuple(ROUTING_PRESETS.keys())


def resolve_routing_chain(mode: str, user_presets: dict[str, list[dict[str, str]]] | None = None) -> list[dict[str, str]]:
    """Resolve a prioritized list of provider/model dictionaries based on the requested mode.

    Args:
        mode: The requested auto-pilot mode ('fastest', 'smartest', 'balanced').
        user_presets: User-defined routing presets mapping mode names to fallback chains.

    Returns:
        A list of fallback configuration dictionaries.

    Raises:
        ValueError: If the requested mode is not recognized or not configured.
    """
    mode_key = mode.strip().lower()

    if mode_key not in VALID_MODES:
        raise ValueError(
            f"Unsupported routing mode: '{mode}'. "
            f"Supported options: {list(VALID_MODES)}"
        )

    # Resolve chain from user presets if exists, otherwise fall back to defaults
    if user_presets and mode_key in user_presets:
        chain = user_presets[mode_key]
    elif mode_key in ROUTING_PRESETS:
        chain = ROUTING_PRESETS[mode_key]
    else:
        raise ValueError(
            f"Routing mode '{mode}' is not configured. "
            f"Please define it when initializing EveryAI:\n"
            f"  EveryAI(routing_presets={{\n"
            f"      '{mode_key}': [\n"
            f"          {{'provider': 'groq', 'model': 'llama-3.1-8b-instant'}},\n"
            f"          {{'provider': 'openrouter', 'model': 'google/gemini-2.5-flash'}},\n"
            f"      ]\n"
            f"  }})"
        )

    if not chain:
        raise ValueError(
            f"Routing mode '{mode}' has an empty chain. "
            f"Please add at least one {{'provider': '...', 'model': '...'}} entry."
        )

    return chain
