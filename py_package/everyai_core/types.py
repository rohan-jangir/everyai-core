"""Unified data structures and type definitions for everyai-core.

This module provides standard dataclasses for responses and model lists
so that all provider APIs return identical formats, maintaining consistency.
"""

from dataclasses import dataclass, field, asdict
from typing import TypedDict, Literal, Any


class Message(TypedDict):
    """Standard message representation for chat messages."""
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class UsageInfo:
    """Standard representation of token usage."""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the usage info to a standard Python dictionary."""
        return asdict(self)


@dataclass
class ChatCompletionChoice:
    """A single choice (response candidate) in the chat completion response."""
    index: int
    message: Message
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert choice to a standard Python dictionary."""
        return asdict(self)


@dataclass
class ChatCompletionResponse:
    """Standard unified structure for all LLM chat responses."""
    id: str | None
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo | None = None
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert response to a standard Python dictionary."""
        return asdict(self)


@dataclass
class ModelInfo:
    """Standard schema representing metadata of a model."""
    id: str
    name: str
    context_length: int | None = None
    owned_by: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert model metadata to a standard Python dictionary."""
        return asdict(self)
