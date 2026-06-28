"""Cloudflare AI provider implementation.

Queries Cloudflare's direct AI Run REST endpoints.
"""

import os
import json
from typing import Any, Generator
import httpx
from everyai_core.providers.base import BaseProvider
from everyai_core.exceptions import raise_for_status, ConfigurationError
from everyai_core.types import ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo


class CloudflareProvider(BaseProvider):
    """Provider class for Cloudflare AI API."""

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Send a chat completion request to Cloudflare direct AI Run endpoint."""
        # Resolve Account ID
        account_id = kwargs.pop("account_id", None) or self.extra_config.get("account_id") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not account_id:
            raise ConfigurationError(
                "Cloudflare AI requires 'account_id'. Please pass it via "
                "EveryAI(provider_config={'cloudflare': {'account_id': 'your_id'}}), "
                "or set the environment variable 'CLOUDFLARE_ACCOUNT_ID'."
            )

        base = (self.base_url or f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run").rstrip("/")
        # Model identifier needs to be stripped/passed directly
        endpoint = f"{base}/{model.lstrip('/')}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Build payload for Cloudflare AI Run Chat
        payload = {
            "messages": messages,
            "stream": stream,
        }
        # Add temperature if supported by payload schema
        if temperature != 0.7:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        # Merge other parameter overrides
        payload.update(kwargs)

        timeout = kwargs.pop("timeout", self.extra_config.get("timeout", 20.0))

        if not stream:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if response.status_code != 200:
                raise_for_status("cloudflare", response.status_code, response.text)
            
            data = response.json()
            if not data.get("success"):
                errors = data.get("errors", [])
                err_msg = errors[0].get("message") if (errors and isinstance(errors[0], dict)) else "Cloudflare query failed"
                raise_for_status("cloudflare", 400, err_msg)

            result = data.get("result", {})
            content = result.get("response", "")

            choices = [
                ChatCompletionChoice(
                    index=0,
                    message={"role": "assistant", "content": content},
                    finish_reason="stop"
                )
            ]

            return ChatCompletionResponse(
                id=None,
                object="chat.completion",
                created=0,
                model=model,
                choices=choices,
                usage=UsageInfo(None, None, None),
                provider="cloudflare"
            )

        # Streaming execution
        def stream_generator() -> Generator[ChatCompletionResponse, None, None]:
            with httpx.Client() as client:
                try:
                    with client.stream("POST", endpoint, headers=headers, json=payload, timeout=timeout) as r:
                        if r.status_code != 200:
                            r.read()
                            raise_for_status("cloudflare", r.status_code, r.text)

                        for line in r.iter_lines():
                            if isinstance(line, bytes):
                                line = line.decode("utf-8")
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("data: "):
                                data_str = line[len("data: "):]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk_data = json.loads(data_str)
                                    yield self._parse_chunk(chunk_data, model)
                                except Exception:
                                    continue
                except Exception as e:
                    raise e

        return stream_generator()

    def _parse_chunk(self, chunk_data: dict[str, Any], model: str) -> ChatCompletionResponse:
        """Parse Cloudflare SSE JSON chunk into a ChatCompletionResponse."""
        content = chunk_data.get("response", "")
        choices = [
            ChatCompletionChoice(
                index=0,
                message={"role": "assistant", "content": content},
                finish_reason=None
            )
        ]

        return ChatCompletionResponse(
            id=None,
            object="chat.completion.chunk",
            created=0,
            model=model,
            choices=choices,
            usage=None,
            provider="cloudflare"
        )

    def list_models(self) -> list[ModelInfo]:
        """List models available for Cloudflare AI."""
        # Cloudflare has standard model presets since listing requires pagination search APIs
        presets = [
            "@cf/meta/llama-3-8b-instruct",
            "@cf/meta/llama-3-70b-instruct",
            "@cf/mistral/mistral-7b-instruct-v0.1",
            "@cf/meta/llama-2-7b-chat-int8"
        ]
        return [ModelInfo(id=p, name=p.split("/")[-1], context_length=2048, owned_by="cloudflare") for p in presets]
