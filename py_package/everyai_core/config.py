"""Configuration module for everyai-core.

Provides helper methods to fetch keys and other settings from the 
environment or direct developer configuration.
"""

import os
from typing import ClassVar


class Config:
    """System configuration provider for EveryAI client settings and API keys."""

    # Map providers to their commonly used environment variables (in order of priority)
    PROVIDER_ENV_MAP: ClassVar[dict[str, list[str]]] = {
        "groq": ["GROQ_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_KEY"],
        "huggingface": ["HUGGINGFACE_API_KEY", "HF_TOKEN", "HF_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        "mistral": ["MISTRAL_API_KEY", "MISTRAL_APIKEY"],
        "cloudflare": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY", "CF_API_TOKEN"],
        "nvidia": ["NVIDIA_API_KEY"],
    }

    @classmethod
    def get_api_key(cls, provider: str, user_provided_key: str | None = None) -> str | None:
        """Resolve API key for a given provider.
        
        Checks user input first, then falls back to environment variables.
        """
        if user_provided_key:
            return user_provided_key

        provider_lower = provider.lower()
        env_keys = cls.PROVIDER_ENV_MAP.get(provider_lower, [f"{provider_lower.upper()}_API_KEY"])

        for var_name in env_keys:
            key = os.environ.get(var_name)
            if key:
                return key

        return None
