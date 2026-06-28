"""EveryAI Core Python Package.

Provides a unified interface to interact with various LLM API provider platforms,
such as Groq, OpenRouter, and HuggingFace, with standardized structures.
"""

from everyai_core.client import EveryAI
from everyai_core.exceptions import (
    EveryAIError,
    ConfigurationError,
    ProviderError,
    AuthenticationError,
    RateLimitError,
    ModelNotFoundError,
)
from everyai_core.types import (
    ChatCompletionResponse,
    ChatCompletionChoice,
    UsageInfo,
    ModelInfo,
    Message,
)
from everyai_core.tracker import UsageTracker

__version__ = "1.1.1"
__author__ = "Rohan Jangir"

__all__ = [
    "EveryAI",
    "UsageTracker",
    "EveryAIError",
    "ConfigurationError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "ModelNotFoundError",
    "ChatCompletionResponse",
    "ChatCompletionChoice",
    "UsageInfo",
    "ModelInfo",
    "Message",
]