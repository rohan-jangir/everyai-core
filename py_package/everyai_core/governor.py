"""Local rate limit governor for everyai-core.

Tracks API requests and token counts locally inside a sliding window,
automatically throttling outgoing calls to avoid provider rate limit blocks.
"""

import time
from collections import deque
from typing import Any


class RateLimitGovernor:
    """Locally tracks request history to govern and throttle API request rates."""

    def __init__(self, max_requests_per_minute: int | None = None, max_tokens_per_minute: int | None = None):
        """Initialize the rate governor.

        Args:
            max_requests_per_minute: Maximum requests allowed per 60-second window.
            max_tokens_per_minute: Maximum tokens allowed per 60-second window.
        """
        self.max_rpm = max_requests_per_minute
        self.max_tpm = max_tokens_per_minute
        
        # Double-ended queue holding tuples of (timestamp, tokens_consumed)
        self.history: deque[tuple[float, int]] = deque()

    def throttle_if_needed(self, estimated_tokens: int = 500) -> None:
        """Throttle execution by sleeping if sending the request would exceed configured limits."""
        if not self.max_rpm and not self.max_tpm:
            return

        while True:
            current_time = time.time()
            self._clean_old_records(current_time)

            # Check if request count exceeds RPM threshold
            rpm_exceeded = self.max_rpm is not None and (len(self.history) >= self.max_rpm)

            # Check if token count exceeds TPM threshold
            current_tokens = sum(tokens for _, tokens in self.history)
            tpm_exceeded = self.max_tpm is not None and (current_tokens + estimated_tokens > self.max_tpm)

            if not rpm_exceeded and not tpm_exceeded:
                break

            # Calculate wait time until the oldest request falls out of the sliding window
            if self.history:
                oldest_time, _ = self.history[0]
                sleep_time = (oldest_time + 60.0) - current_time
                if sleep_time > 0:
                    # Clean ASCII printing to prevent UnicodeEncodeErrors on Windows terminals
                    print(
                        f"[EveryAI Governor] Approaching rate limits. "
                        f"Throttling request, sleeping for {sleep_time:.2f} seconds..."
                    )
                    time.sleep(sleep_time)
            else:
                # Safeguard sleep to prevent CPU locks
                time.sleep(0.5)
                break

    def record_request(self, tokens_used: int) -> None:
        """Log a successful request in the governor's sliding window history.

        Args:
            tokens_used: Exact count of prompt + completion tokens consumed by the call.
        """
        if not self.max_rpm and not self.max_tpm:
            return
        self.history.append((time.time(), tokens_used))

    def _clean_old_records(self, current_time: float) -> None:
        """Purge sliding-window requests older than 60 seconds."""
        cutoff = current_time - 60.0
        while self.history and self.history[0][0] <= cutoff:
            self.history.popleft()
