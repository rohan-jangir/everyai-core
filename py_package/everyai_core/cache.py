"""Local response caching system for everyai-core.

Stores prompt-response history in a local SQLite database, allowing duplicate
requests to be resolved instantly without using tokens or triggering rate limits.
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from everyai_core.types import ChatCompletionResponse, ChatCompletionChoice, UsageInfo


class RequestCache:
    """Handles local response caching to prevent duplicate API execution."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the database connection and cache table."""
        if db_path is None:
            db_dir = Path.home() / ".everyai"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = db_dir / "cache.db"
        else:
            self.db_path = Path(db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Establish connection to SQLite."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Initialize caching table schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS response_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    messages_json TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    response_json TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _generate_hash(
        self,
        messages: list[dict[str, Any]],
        provider: str | None,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any
    ) -> str:
        """Generate a unique SHA-256 signature for the request inputs."""
        # Ensure message dictionaries are ordered consistently for hashing
        normalized_messages = []
        for msg in messages:
            normalized_messages.append({k: msg[k] for k in sorted(msg.keys())})

        payload = {
            "messages": normalized_messages,
            "provider": provider.strip().lower() if provider else None,
            "model": model.strip().lower() if model else None,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_kwargs": {k: kwargs[k] for k in sorted(kwargs.keys())}
        }
        
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def get(
        self,
        messages: list[dict[str, Any]],
        provider: str | None,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any
    ) -> ChatCompletionResponse | None:
        """Query the cache for a matching response.

        Returns:
            A ChatCompletionResponse instance if found, or None.
        """
        prompt_hash = self._generate_hash(messages, provider, model, temperature, max_tokens, **kwargs)

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT response_json FROM response_cache WHERE prompt_hash = ?",
                (prompt_hash,)
            ).fetchone()

            if not row:
                return None

            try:
                data = json.loads(row[0])
                
                # Reconstruct choices dataclass items
                choices = [
                    ChatCompletionChoice(
                        index=c["index"],
                        message=c["message"],
                        finish_reason=c.get("finish_reason")
                    ) for c in data.get("choices", [])
                ]
                
                # Reconstruct token usage stats
                usage = None
                if "usage" in data and data["usage"]:
                    u = data["usage"]
                    usage = UsageInfo(
                        prompt_tokens=u.get("prompt_tokens"),
                        completion_tokens=u.get("completion_tokens"),
                        total_tokens=u.get("total_tokens")
                    )

                return ChatCompletionResponse(
                    id=data.get("id"),
                    object=data.get("object", "chat.completion"),
                    created=data.get("created", 0),
                    model=data.get("model", ""),
                    choices=choices,
                    usage=usage,
                    provider=data.get("provider")
                )
            except Exception:
                # If cache is malformed, treat it as a miss
                return None

    def set(
        self,
        messages: list[dict[str, Any]],
        provider: str | None,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        response: ChatCompletionResponse,
        **kwargs: Any
    ) -> None:
        """Write a request/response entry to the database cache."""
        prompt_hash = self._generate_hash(messages, provider, model, temperature, max_tokens, **kwargs)
        
        # Serialize standard completion dataclass
        response_dict = response.to_dict()
        response_json = json.dumps(response_dict)
        messages_json = json.dumps(messages)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO response_cache 
                (prompt_hash, messages_json, provider, model, response_json, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (prompt_hash, messages_json, provider, model, response_json)
            )
            conn.commit()

    def clear(self) -> None:
        """Empty the database cache."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM response_cache")
            conn.commit()
