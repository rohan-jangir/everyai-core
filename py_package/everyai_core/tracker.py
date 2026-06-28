"""Usage and token tracking database module for everyai-core.

Stores telemetry details of API calls, including prompt/completion tokens,
error categories, and rate limit details in a local SQLite database.
"""

import sqlite3
from pathlib import Path
from typing import Any


class UsageTracker:
    """Handles logging and queries for provider API telemetry."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the database path and table structure."""
        if db_path is None:
            db_dir = Path.home() / ".everyai"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = db_dir / "usage.db"
        else:
            self.db_path = Path(db_path)
            
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Establish connection to SQLite."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Create telemetry tables if they don't already exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            conn.commit()

    def log_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Write a request log to the telemetry database.

        Args:
            provider: AI provider name (e.g. 'groq').
            model: Model name.
            prompt_tokens: Number of prompt/input tokens.
            completion_tokens: Number of completion/output tokens.
            status: Call status ('success', 'rate_limit', 'auth_error', etc.).
            error_message: Text details of any exception.
        """
        # Fallbacks for token sums
        p_tok = prompt_tokens or 0
        c_tok = completion_tokens or 0
        t_tok = p_tok + c_tok

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO request_logs 
                (provider, model, prompt_tokens, completion_tokens, total_tokens, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider.strip().lower(),
                    model,
                    prompt_tokens,
                    completion_tokens,
                    t_tok if (prompt_tokens is not None or completion_tokens is not None) else None,
                    status,
                    error_message,
                ),
            )
            conn.commit()

    def get_summary(self) -> dict[str, Any]:
        """Aggregate tracking data across providers.

        Returns:
            A dictionary containing aggregated metrics.
        """
        summary: dict[str, Any] = {
            "total_calls": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "rate_limits_total": 0,
            "cache_hits_total": 0,
            "tokens_saved_total": 0,
            "by_provider": {},
        }

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            
            # Get global totals
            global_row = conn.execute("""
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(COALESCE(prompt_tokens, 0)) as total_prompt,
                    SUM(COALESCE(completion_tokens, 0)) as total_completion,
                    SUM(COALESCE(total_tokens, 0)) as total_tokens
                FROM request_logs
            """).fetchone()

            if global_row and global_row["total_calls"] > 0:
                summary["total_calls"] = global_row["total_calls"]
                summary["total_prompt_tokens"] = global_row["total_prompt"]
                summary["total_completion_tokens"] = global_row["total_completion"]
                summary["total_tokens"] = global_row["total_tokens"]

            # Count total rate limits
            rate_limit_row = conn.execute("""
                SELECT COUNT(*) as rate_limits
                FROM request_logs
                WHERE status = 'rate_limit'
            """).fetchone()
            if rate_limit_row:
                summary["rate_limits_total"] = rate_limit_row["rate_limits"]

            # Count total cache hits
            cache_hit_row = conn.execute("""
                SELECT COUNT(*) as cache_hits
                FROM request_logs
                WHERE status = 'cache_hit'
            """).fetchone()
            if cache_hit_row:
                summary["cache_hits_total"] = cache_hit_row["cache_hits"]

            # Sum total tokens saved from cache hits
            saved_tokens_row = conn.execute("""
                SELECT SUM(CAST(COALESCE(error_message, '0') AS INTEGER)) as saved_tokens
                FROM request_logs
                WHERE status = 'cache_hit'
            """).fetchone()
            summary["tokens_saved_total"] = saved_tokens_row["saved_tokens"] if (saved_tokens_row and saved_tokens_row["saved_tokens"] is not None) else 0

            # Get stats broken down by provider
            provider_rows = conn.execute("""
                SELECT 
                    provider,
                    COUNT(*) as calls,
                    SUM(COALESCE(prompt_tokens, 0)) as prompt_tokens,
                    SUM(COALESCE(completion_tokens, 0)) as completion_tokens,
                    SUM(COALESCE(total_tokens, 0)) as total_tokens,
                    SUM(CASE WHEN status = 'rate_limit' THEN 1 ELSE 0 END) as rate_limits
                FROM request_logs
                GROUP BY provider
            """).fetchall()

            for row in provider_rows:
                summary["by_provider"][row["provider"]] = {
                    "calls": row["calls"],
                    "prompt_tokens": row["prompt_tokens"],
                    "completion_tokens": row["completion_tokens"],
                    "total_tokens": row["total_tokens"],
                    "rate_limits": row["rate_limits"],
                }

        return summary

    def get_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch chronological log history.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            A list of dictionary log rows.
        """
        logs = []
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, timestamp, provider, model, prompt_tokens, completion_tokens, total_tokens, status, error_message
                FROM request_logs
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                logs.append(dict(row))
        return logs

    def clear_logs(self) -> None:
        """Truncate the telemetry log table."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM request_logs")
            conn.commit()
