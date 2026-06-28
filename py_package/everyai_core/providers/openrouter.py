"""OpenRouter provider implementation.

Queries OpenRouter's API directly using httpx REST endpoints.
"""

import json
from typing import Any, Generator
import httpx
from everyai_core.providers.base import BaseProvider
from everyai_core.exceptions import raise_for_status, NetworkError
from everyai_core.types import ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo


class OpenRouterProvider(BaseProvider):
    """Provider class for OpenRouter LLM API."""

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Send a chat completion request to OpenRouter API using direct HTTP REST."""
        base = (self.base_url or "https://openrouter.ai/api/v1").rstrip("/")
        endpoint = f"{base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rohan-jangir/everyai-core",
            "X-Title": "EveryAI-Core",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        # Merge optional custom parameter overrides
        payload.update(kwargs)

        # Resolve timeout — OpenRouter routes to many backends so default is generous (120s)
        timeout = kwargs.pop("timeout", self.extra_config.get("timeout", 120.0))

        if not stream:
            try:
                response = httpx.post(endpoint, headers=headers, json=payload, timeout=timeout)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                raise NetworkError(
                    f"OpenRouter request timed out or failed to connect after {timeout}s. "
                    f"The upstream model '{model}' may be slow or temporarily unavailable. "
                    f"Try increasing the timeout: client.chat(..., timeout=300) "
                    f"or try a different model. Original error: {type(e).__name__}: {e}"
                )

            if response.status_code != 200:
                raise_for_status("openrouter", response.status_code, response.text)
            
            data = response.json()

            # Guard against empty choices from OpenRouter
            raw_choices = data.get("choices", [])
            if not raw_choices:
                # OpenRouter may return an error in the response body without a non-200 status
                error_info = data.get("error")
                if error_info:
                    error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
                    raise_for_status("openrouter", error_info.get("code", 500) if isinstance(error_info, dict) else 500, json.dumps(data))

            choices = [
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=c.get("message", {}),
                    finish_reason=c.get("finish_reason")
                ) for c in raw_choices
            ]
            
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
                model=data.get("model", model),
                choices=choices,
                usage=usage,
                provider="openrouter"
            )

        # Streaming execution
        def stream_generator() -> Generator[ChatCompletionResponse, None, None]:
            with httpx.Client() as client:
                try:
                    with client.stream("POST", endpoint, headers=headers, json=payload, timeout=timeout) as r:
                        if r.status_code != 200:
                            # Read content to pass details to exception parser
                            r.read()
                            raise_for_status("openrouter", r.status_code, r.text)

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
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    raise NetworkError(
                        f"OpenRouter streaming request timed out or failed to connect. "
                        f"The upstream model '{model}' may be slow or temporarily unavailable. "
                        f"Original error: {type(e).__name__}: {e}"
                    )
                except Exception as e:
                    raise e

        return stream_generator()

    def _parse_chunk(self, chunk_data: dict[str, Any], model: str) -> ChatCompletionResponse:
        """Parse standard streaming JSON chunk into a ChatCompletionResponse."""
        choices = []
        for c in chunk_data.get("choices", []):
            delta = c.get("delta", {})
            content = delta.get("content", "") or ""
            if not content:
                # Handle reasoning tokens from reasoning models
                content = delta.get("reasoning", "") or delta.get("reasoning_content", "") or ""
            
            message_dict = {
                "role": delta.get("role", "assistant"),
                "content": content
            }
            choices.append(ChatCompletionChoice(
                index=c.get("index", 0),
                message=message_dict,
                finish_reason=c.get("finish_reason")
            ))

        usage = None
        if "usage" in chunk_data and chunk_data["usage"]:
            u = chunk_data["usage"]
            usage = UsageInfo(
                prompt_tokens=u.get("prompt_tokens"),
                completion_tokens=u.get("completion_tokens"),
                total_tokens=u.get("total_tokens")
            )

        return ChatCompletionResponse(
            id=chunk_data.get("id"),
            object=chunk_data.get("object", "chat.completion.chunk"),
            created=chunk_data.get("created", 0),
            model=chunk_data.get("model", model),
            choices=choices,
            usage=usage,
            provider="openrouter"
        )

    def list_models(self) -> list[ModelInfo]:
        """List models available for OpenRouter."""
        base = (self.base_url or "https://openrouter.ai/api/v1").rstrip("/")
        endpoint = f"{base}/models"

        response = httpx.get(endpoint, timeout=20.0)
        if response.status_code != 200:
            raise_for_status("openrouter", response.status_code, response.text)

        data = response.json()
        models = []
        for m in data.get("data", []):
            models.append(ModelInfo(
                id=m.get("id"),
                name=m.get("name", m.get("id")),
                context_length=m.get("context_length"),
                owned_by=m.get("owned_by")
            ))
        return models
