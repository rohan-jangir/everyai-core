"""Custom exceptions for everyai-core.

Defines standard error classes thrown by the package, including helper methods
to map HTTP error responses from LLM providers into structured custom exceptions.
"""

import json
from typing import Any


class EveryAIError(Exception):
    """Base exception for all errors raised by everyai-core."""
    pass


class ConfigurationError(EveryAIError):
    """Raised when there is a configuration error (e.g., missing API key)."""
    
    def __str__(self) -> str:
        return (
            f"[Configuration Error] {super().__str__()}\n"
            f"[Suggestion]: Please verify that you have passed the correct API keys when initializing "
            f"EveryAI(api_keys={{...}}) or that you have set the corresponding environment variables (e.g. GROQ_API_KEY)."
        )


class ModelNotFoundError(EveryAIError):
    """Raised when the requested model is not found or unsupported on the client side."""
    
    def __str__(self) -> str:
        return (
            f"[Model Not Found] {super().__str__()}\n"
            f"[Suggestion]: Double-check the spelling of the model identifier. You can retrieve a list of supported "
            f"models by calling `EveryAI.list_models(provider)` or query the provider's official model catalog."
        )


class NetworkError(EveryAIError):
    """Raised when a connection to an AI provider's server fails or times out on the client side."""
    
    def __str__(self) -> str:
        return (
            f"[Network Connection Error] {super().__str__()}\n"
            f"[Suggestion]: Check your local internet connectivity, DNS configuration, proxy settings, or firewall."
        )


class ProviderError(EveryAIError):
    """Base exception for errors returned by LLM providers' APIs.
    
    Preserves the raw error message from the provider without client-side suggestions
    to ensure developers see the exact error context from the remote server.
    """
    
    def __init__(self, message: str, provider: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        base_msg = f"[{self.provider.upper()} API Error]"
        if self.status_code:
            base_msg += f" (Status {self.status_code})"
        return f"{base_msg}: {super().__str__()}"


class AuthenticationError(ProviderError):
    """Raised when authentication with a provider fails (e.g., invalid API key)."""
    pass


class RateLimitError(ProviderError):
    """Raised when a provider's rate limits are exceeded or too many requests are hit."""
    pass


class ContextLengthExceededError(ProviderError):
    """Raised when the input context length is too long for the selected model."""
    pass


class InvalidRequestError(ProviderError):
    """Raised when the API request parameters are invalid (e.g., bad model inputs)."""
    pass


class ProviderServerError(ProviderError):
    """Raised when the remote provider server experiences an internal failure (HTTP 500/503)."""
    pass


def raise_for_status(provider: str, status_code: int, response_text: str) -> None:
    """Parses HTTP error response from a provider, extracts the message, and raises the correct custom exception.

    Args:
        provider: Name of the provider (e.g., 'groq').
        status_code: The HTTP status code returned.
        response_text: The raw HTTP response body.

    Raises:
        AuthenticationError: On HTTP 401.
        RateLimitError: On HTTP 429.
        ContextLengthExceededError: On HTTP 400/422 when input tokens exceed window.
        InvalidRequestError: On general HTTP 400/422.
        ProviderServerError: On HTTP 5xx.
        ProviderError: Default fallback for other HTTP error codes.
    """
    provider_key = provider.strip().lower()
    error_msg = response_text

    # Parse JSON error body formats dynamically based on provider specs
    try:
        data = json.loads(response_text)
        if provider_key in ("groq", "openrouter"):
            # Groq & OpenRouter standard OpenAI-like error json format
            if isinstance(data, dict) and "error" in data:
                err_info = data["error"]
                if isinstance(err_info, dict):
                    error_msg = err_info.get("message", error_msg)
                else:
                    error_msg = str(err_info)
        elif provider_key == "huggingface":
            # HuggingFace formats: {"error": "..."} or {"error": ["..."]} or {"error": {"message": "..."}}
            if isinstance(data, dict):
                err_val = data.get("error")
                if isinstance(err_val, list):
                    error_msg = ", ".join(err_val)
                elif isinstance(err_val, dict):
                    error_msg = err_val.get("message", error_msg)
                elif err_val:
                    error_msg = str(err_val)
            elif isinstance(data, list) and data:
                error_msg = str(data[0])
    except Exception:
        # Fall back to raw HTTP response_text if JSON parsing fails
        pass

    # Map status codes & messages to clean custom exceptions
    if status_code == 401:
        raise AuthenticationError(error_msg, provider, status_code, response_text)
    elif status_code == 429:
        raise RateLimitError(error_msg, provider, status_code, response_text)
    elif status_code == 404:
        raise ModelNotFoundError(f"Model not found or provider endpoint error: {error_msg}")
    elif status_code in (400, 422):
        # Look for context length limits in error message
        msg_lower = error_msg.lower()
        if any(term in msg_lower for term in ("context length", "context window", "max tokens", "too large")):
            raise ContextLengthExceededError(error_msg, provider, status_code, response_text)
        else:
            raise InvalidRequestError(error_msg, provider, status_code, response_text)
    elif status_code >= 500:
        raise ProviderServerError(error_msg, provider, status_code, response_text)
    else:
        raise ProviderError(error_msg, provider, status_code, response_text)
