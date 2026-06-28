"""HuggingFace provider implementation.

Supports:
1. Cloud Serverless Inference API using direct httpx REST.
2. Local Model Inference using the optional transformers/torch library.
"""

import json
import time
from typing import Any, Generator
import httpx
from everyai_core.providers.base import BaseProvider
from everyai_core.exceptions import raise_for_status, ConfigurationError
from everyai_core.types import ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo


class HuggingFaceProvider(BaseProvider):
    """Provider class for HuggingFace LLM APIs (Serverless & Local)."""

    # In-memory dictionary to cache loaded models and tokenizers for local execution
    _local_cache: dict[str, tuple[Any, Any, str]] = {}

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Submit a request to Hugging Face (either Cloud API or Local execution)."""
        # Determine if we should run the model locally
        is_local = kwargs.pop("local", False) or self.extra_config.get("local", False)

        if is_local:
            return self._chat_local(model, messages, temperature, max_tokens, stream, **kwargs)
        else:
            return self._chat_cloud(model, messages, temperature, max_tokens, stream, **kwargs)

    def _chat_cloud(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Call Hugging Face Serverless Inference API via direct HTTP REST."""
        base = (self.base_url or "https://api-inference.huggingface.co/v1").rstrip("/")
        endpoint = f"{base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        # Merge custom configs
        payload.update(kwargs)

        if not stream:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=90.0)
            if response.status_code != 200:
                raise_for_status("huggingface", response.status_code, response.text)

            data = response.json()
            choices = [
                ChatCompletionChoice(
                    index=c.get("index", 0),
                    message=c.get("message", {}),
                    finish_reason=c.get("finish_reason")
                ) for c in data.get("choices", [])
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
                provider="huggingface"
            )

        # Cloud Streaming
        def cloud_stream_generator() -> Generator[ChatCompletionResponse, None, None]:
            with httpx.Client() as client:
                try:
                    with client.stream("POST", endpoint, headers=headers, json=payload, timeout=90.0) as r:
                        if r.status_code != 200:
                            r.read()
                            raise_for_status("huggingface", r.status_code, r.text)

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

        return cloud_stream_generator()

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
            provider="huggingface"
        )

    def _chat_local(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Load and run the model locally using transformers/torch library."""
        # 1. Dependency checks
        try:
            import torch
            import transformers
            from transformers import AutoTokenizer, AutoModelForCausalLM
        except ImportError:
            raise ConfigurationError(
                "Local inference requires 'transformers' and 'torch' packages.\n"
                "[Suggestion]: Please install them in your terminal via: pip install transformers torch"
            )

        # 2. Lazily load model & tokenizer with in-memory caching
        if model not in self._local_cache:
            print(f"[EveryAI] Downloading & loading model '{model}' in memory...")
            
            # Detect device (CUDA, MPS, or CPU)
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
                
            print(f"[EveryAI] Local inference device: {device.upper()}")
            
            tokenizer = AutoTokenizer.from_pretrained(model)
            
            # Load model with dynamic devices mapping fallback
            try:
                local_model = AutoModelForCausalLM.from_pretrained(
                    model,
                    torch_dtype=torch.float16 if device in ("cuda", "mps") else torch.float32,
                    device_map="auto" if device in ("cuda", "mps") else None
                )
            except Exception:
                local_model = AutoModelForCausalLM.from_pretrained(model)
                
            if device == "cpu" or not hasattr(local_model, "device"):
                try:
                    local_model = local_model.to(device)
                except Exception:
                    pass
            self._local_cache[model] = (tokenizer, local_model, device)

        tokenizer, local_model, device = self._local_cache[model]

        # 3. Formulate Prompt
        try:
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            prompt = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            prompt += "<|im_start|>assistant\n"

        target_device = local_model.device if hasattr(local_model, "device") else device
        inputs = tokenizer(prompt, return_tensors="pt").to(target_device)
        prompt_tokens = inputs.input_ids.shape[1]

        # 4. Local Execution
        if not stream:
            gen_kwargs = {
                "max_new_tokens": max_tokens or 512,
                "temperature": temperature if temperature > 0 else 0.001,
                "do_sample": temperature > 0,
            }
            gen_kwargs.update(kwargs)
            
            outputs = local_model.generate(**inputs, **gen_kwargs)
            generated_ids = outputs[0][prompt_tokens:]
            response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
            completion_tokens = len(generated_ids)

            return ChatCompletionResponse(
                id="chatcmpl-local-hf",
                object="chat.completion",
                created=int(time.time()),
                model=model,
                choices=[ChatCompletionChoice(
                    index=0,
                    message={"role": "assistant", "content": response_text},
                    finish_reason="stop"
                )],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                ),
                provider="huggingface"
            )

        # Local Streaming Execution (TextIteratorStreamer)
        from transformers import TextIteratorStreamer
        from threading import Thread

        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        gen_kwargs = dict(
            inputs,
            streamer=streamer,
            max_new_tokens=max_tokens or 512,
            temperature=temperature if temperature > 0 else 0.001,
            do_sample=temperature > 0,
            **kwargs
        )

        thread = Thread(target=local_model.generate, kwargs=gen_kwargs)
        thread.start()

        def local_stream_generator() -> Generator[ChatCompletionResponse, None, None]:
            combined_content = ""
            for new_text in streamer:
                combined_content += new_text
                completion_tokens = len(tokenizer.encode(combined_content))
                
                yield ChatCompletionResponse(
                    id="chatcmpl-local-hf-stream",
                    object="chat.completion.chunk",
                    created=int(time.time()),
                    model=model,
                    choices=[ChatCompletionChoice(
                        index=0,
                        message={"role": "assistant", "content": new_text},
                        finish_reason=None
                    )],
                    usage=UsageInfo(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens
                    ),
                    provider="huggingface"
                )

        return local_stream_generator()

    def list_models(self) -> list[ModelInfo]:
        """List standard models available on HuggingFace Hub via API."""
        endpoint = "https://huggingface.co/api/models"
        params = {
            "pipeline_tag": "text-generation",
            "limit": 100,
            "sort": "downloads",
            "direction": -1
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.get(endpoint, params=params, headers=headers, timeout=20.0)
        if response.status_code != 200:
            raise_for_status("huggingface", response.status_code, response.text)

        data = response.json()
        models = []
        for m in data:
            models.append(ModelInfo(
                id=m.get("modelId", m.get("id", "")),
                name=m.get("modelId", m.get("id", "")),
                owned_by="huggingface",
                downloads=m.get("downloads", 0),
                likes=m.get("likes", 0)
            ))
        return models
