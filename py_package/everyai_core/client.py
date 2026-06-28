"""Main EveryAI client orchestrator.

Defines the user-facing EveryAI class, acting as a gateway to all supported LLMs.
"""

from typing import Any, Generator
from everyai_core.config import Config
from everyai_core.exceptions import ConfigurationError
from everyai_core.types import ChatCompletionResponse, ModelInfo
from everyai_core.providers.base import BaseProvider
from everyai_core.providers.groq import GroqProvider
from everyai_core.providers.openrouter import OpenRouterProvider
from everyai_core.providers.huggingface import HuggingFaceProvider
from everyai_core.providers.cerebras import CerebrasProvider
from everyai_core.providers.mistral import MistralProvider
from everyai_core.providers.cloudflare import CloudflareProvider
from everyai_core.providers.nvidia import NvidiaProvider
from everyai_core.tracker import UsageTracker
from everyai_core.cache import RequestCache
from everyai_core.governor import RateLimitGovernor
from everyai_core.routing import resolve_routing_chain


class EveryAI:
    """The central client for everyai-core.
    
    Provides programmatic access to all supported AI model providers.
    Providers are loaded lazily upon property access and will lookup keys in 
    the system environment unless specified during client construction.
    """

    def __init__(
        self,
        api_keys: dict[str, str] | None = None,
        provider_config: dict[str, dict[str, Any]] | None = None,
        db_path: str | None = None,
        fallback_chain: list[dict[str, Any]] | None = None,
        routing_presets: dict[str, list[dict[str, Any]]] | None = None,
        cache: bool = False,
        cache_path: str | None = None,
        max_requests_per_minute: int | None = None,
        max_tokens_per_minute: int | None = None,
        **kwargs
    ):
        """Initialize the EveryAI client.

        Args:
            api_keys: Dictionary mapping provider keys (e.g. 'groq') to their API keys.
            provider_config: Dictionary mapping provider names to their extra configuration.
                Useful for providers that require additional settings beyond API keys.
                Example: {"cloudflare": {"account_id": "your_account_id"}}
            db_path: Optional custom path for the usage tracking SQLite database.
            fallback_chain: Optional default list of fallback configurations (dicts with provider, model, api_key).
            routing_presets: Optional dictionary of routing presets mapping mode names (e.g. 'fastest')
                to fallback chains. Example: {"fastest": [{"provider": "groq", "model": "llama-3.1-8b-instant"}]}
            cache: Whether prompt-response caching is enabled globally (default: False).
            cache_path: Optional custom path for the SQLite caching database.
            max_requests_per_minute: Local limit of requests per minute (default: None).
            max_tokens_per_minute: Local limit of prompt+completion tokens per minute (default: None).
            **kwargs: Default provider configurations (e.g. custom timeouts, retry limits).
        """
        self.api_keys = api_keys or {}
        self.provider_config = provider_config or {}
        self.fallback_chain = fallback_chain or []
        self.routing_presets = routing_presets or {}
        self.client_config = kwargs
        self._provider_instances: dict[tuple[str, str], BaseProvider] = {}
        self.tracker = UsageTracker(db_path=db_path)
        self.cache_enabled = cache
        self.cache = RequestCache(db_path=cache_path)
        self.governor = RateLimitGovernor(
            max_requests_per_minute=max_requests_per_minute,
            max_tokens_per_minute=max_tokens_per_minute
        )

    def get_provider(self, provider_name: str, api_key_override: str | None = None) -> BaseProvider:
        """Lazily initialize and fetch a provider instance.

        Args:
            provider_name: The name identifier of the provider.
            api_key_override: Optional custom API key to override default/environment configs.

        Returns:
            An instantiated provider class.

        Raises:
            ConfigurationError: If no API key can be resolved for the provider.
        """
        provider_name = provider_name.strip().lower()
        
        # Dynamically fetch the provider class first to validate if it's supported
        from everyai_core.providers import get_provider_class
        provider_cls = get_provider_class(provider_name)
        
        # Resolve the API key
        user_key = api_key_override or self.api_keys.get(provider_name)
        api_key = Config.get_api_key(provider_name, user_key)
        
        if not api_key:
            raise ConfigurationError(
                f"API Key for provider '{provider_name}' is not set. "
                f"Please pass it in during EveryAI initialization via: "
                f"EveryAI(api_keys={{'{provider_name}': 'your_key'}}) "
                f"or set the environment variable."
            )
            
        cache_key = (provider_name, api_key)
        
        if cache_key not in self._provider_instances:
            # Merge global client config with per-provider config
            merged_config = {**self.client_config}
            per_provider = self.provider_config.get(provider_name, {})
            merged_config.update(per_provider)
            
            self._provider_instances[cache_key] = provider_cls(
                api_key=api_key,
                **merged_config
            )
            
        return self._provider_instances[cache_key]

    # --- Property Getters for IDE Autocomplete & Easy Access ---

    @property
    def groq(self) -> GroqProvider:
        """Access the Groq provider client."""
        # Casting to actual provider class for static analysis type safety
        return self.get_provider("groq")  # type: ignore

    @property
    def openrouter(self) -> OpenRouterProvider:
        """Access the OpenRouter provider client."""
        return self.get_provider("openrouter")  # type: ignore

    @property
    def huggingface(self) -> HuggingFaceProvider:
        """Access the HuggingFace provider client."""
        return self.get_provider("huggingface")  # type: ignore

    @property
    def cerebras(self) -> CerebrasProvider:
        """Access the Cerebras provider client."""
        return self.get_provider("cerebras")  # type: ignore

    @property
    def mistral(self) -> MistralProvider:
        """Access the Mistral provider client."""
        return self.get_provider("mistral")  # type: ignore

    @property
    def cloudflare(self) -> CloudflareProvider:
        """Access the Cloudflare provider client."""
        return self.get_provider("cloudflare")  # type: ignore

    @property
    def nvidia(self) -> NvidiaProvider:
        """Access the Nvidia provider client."""
        return self.get_provider("nvidia")  # type: ignore

    # --- Generic Unified Methods ---

    def chat(
        self,
        provider: str | None = None,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        fallback_chain: list[dict[str, Any]] | None = None,
        max_passes: int = 2,
        mode: str | None = None,
        cache: bool | None = None,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Submit a chat completion request to a specific provider or fallback chain.

        Args:
            provider: Optional name identifier of the provider.
            model: Optional model identifier.
            messages: A list of messages (e.g. [{"role": "user", "content": "..."}]).
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.
            stream: Whether to stream the response.
            fallback_chain: Optional list of fallback dict configurations (dicts with provider, model, api_key).
            max_passes: Maximum passes to make over the fallback chain (default: 2).
            mode: Optional auto-pilot routing mode ('fastest', 'smartest', 'balanced').
            cache: Whether prompt-response caching is enabled for this call (overrides global setting).
            **kwargs: Extra parameters to forward to the provider.

        Returns:
            A ChatCompletionResponse instance or a generator.
        """
        if messages is None:
            messages = []

        # Resolve auto-pilot mode to fallback chain
        if mode:
            fallback_chain = resolve_routing_chain(mode, self.routing_presets)

        use_cache = cache if cache is not None else self.cache_enabled

        # 1. Perform cache lookup if caching is enabled
        if use_cache and messages:
            # Case A: Specific single provider and model
            if provider and model:
                cached_res = self.cache.get(
                    messages=messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                if cached_res:
                    saved_tokens = cached_res.usage.total_tokens if cached_res.usage else 0
                    self.tracker.log_call(
                        provider=provider,
                        model=model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        status="cache_hit",
                        error_message=str(saved_tokens)
                    )
                    if stream:
                        def cached_stream():
                            yield cached_res
                        return cached_stream()
                    return cached_res
            
            # Case B: Fallback chain (explicit or resolved from autopilot mode)
            else:
                target_chain = fallback_chain or self.fallback_chain
                if target_chain:
                    for config in target_chain:
                        c_prov = config.get("provider")
                        c_model = config.get("model")
                        if c_prov and c_model:
                            cached_res = self.cache.get(
                                messages=messages,
                                provider=c_prov,
                                model=c_model,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                **kwargs
                            )
                            if cached_res:
                                saved_tokens = cached_res.usage.total_tokens if cached_res.usage else 0
                                self.tracker.log_call(
                                    provider=c_prov,
                                    model=c_model,
                                    prompt_tokens=0,
                                    completion_tokens=0,
                                    status="cache_hit",
                                    error_message=str(saved_tokens)
                                )
                                if stream:
                                    def cached_stream():
                                        yield cached_res
                                    return cached_stream()
                                return cached_res

        # Determine if we should route using fallback
        actual_chain = fallback_chain or (self.fallback_chain if (provider is None and model is None) else None)

        if actual_chain:
            return self._chat_with_fallback(
                fallback_chain=actual_chain,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                max_passes=max_passes,
                cache=use_cache,
                **kwargs
            )

        if not provider or not model:
            raise ValueError(
                "You must specify both 'provider' and 'model', "
                "or configure/pass a 'fallback_chain' to execute a request."
            )

        return self._chat_single(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            cache=use_cache,
            **kwargs
        )

    def _chat_single(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        api_key_override: str | None = None,
        cache: bool | None = None,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Runs a single request execution to the specific provider/model config."""
        provider_instance = self.get_provider(provider, api_key_override)
        use_cache = cache if cache is not None else self.cache_enabled
        
        # Local Rate Limit Governor Throttling
        prompt_len = sum(len(msg.get("content", "") or "") for msg in messages)
        estimated_tokens = max(500, (prompt_len // 4) + (max_tokens or 150))
        self.governor.throttle_if_needed(estimated_tokens)

        from everyai_core.exceptions import (
            RateLimitError,
            AuthenticationError,
            ProviderError,
            ContextLengthExceededError,
            InvalidRequestError,
            ProviderServerError,
            NetworkError,
        )

        try:
            response = provider_instance.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
            
            if stream:
                # Wrap generator to intercept final usage/tokens and cache it
                return self._wrap_stream_telemetry(
                    generator=response,
                    provider=provider,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_cache=use_cache,
                    **kwargs
                )
            
            # Record non-streaming log
            p_tok = response.usage.prompt_tokens if response.usage else None
            c_tok = response.usage.completion_tokens if response.usage else None
            self.tracker.log_call(
                provider=provider,
                model=model,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                status="success"
            )
            
            # Record tokens in governor
            total_tok = response.usage.total_tokens if response.usage else 0
            self.governor.record_request(total_tok)
            
            # Write success to cache if caching is enabled
            if use_cache:
                self.cache.set(
                    messages=messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response=response,
                    **kwargs
                )
            return response

        except RateLimitError as e:
            self.tracker.log_call(provider=provider, model=model, status="rate_limit", error_message=str(e))
            raise
        except AuthenticationError as e:
            self.tracker.log_call(provider=provider, model=model, status="auth_error", error_message=str(e))
            raise
        except ContextLengthExceededError as e:
            self.tracker.log_call(provider=provider, model=model, status="context_exceeded", error_message=str(e))
            raise
        except InvalidRequestError as e:
            self.tracker.log_call(provider=provider, model=model, status="invalid_request", error_message=str(e))
            raise
        except ProviderServerError as e:
            self.tracker.log_call(provider=provider, model=model, status="server_error", error_message=str(e))
            raise
        except ProviderError as e:
            self.tracker.log_call(provider=provider, model=model, status="provider_error", error_message=str(e))
            raise
        except NetworkError as e:
            self.tracker.log_call(provider=provider, model=model, status="network_error", error_message=str(e))
            raise
        except Exception as e:
            self.tracker.log_call(provider=provider, model=model, status="error", error_message=str(e))
            raise

    def _chat_with_fallback(
        self,
        fallback_chain: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        max_passes: int = 2,
        cache: bool | None = None,
        **kwargs
    ) -> ChatCompletionResponse | Generator[ChatCompletionResponse, None, None]:
        """Automatically attempts request execution across a chain of configurations."""
        from everyai_core.exceptions import EveryAIError
        
        if not fallback_chain:
            raise ValueError("Fallback chain cannot be empty.")

        failures = []
        
        for pass_idx in range(1, max_passes + 1):
            for config_idx, config in enumerate(fallback_chain):
                prov = config.get("provider")
                model_name = config.get("model")
                api_key_override = config.get("api_key")
                
                if not prov or not model_name:
                    raise ValueError(
                        f"Each fallback configuration must define 'provider' and 'model'. "
                        f"Config index {config_idx} is invalid."
                    )
                
                try:
                    # Attempt standard execution
                    result = self._chat_single(
                        provider=prov,
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        api_key_override=api_key_override,
                        cache=cache,
                        **kwargs
                    )
                    
                    if pass_idx > 1:
                        print(f"[EveryAI Info] Succeeded on pass {pass_idx} using {prov}/{model_name}.")
                    return result
                    
                except Exception as e:
                    # Record the attempt failure
                    failures.append({
                        "pass": pass_idx,
                        "config_index": config_idx,
                        "provider": prov,
                        "model": model_name,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    })
                    
                    # Print warning to terminal for transparent failover tracing
                    print(
                        f"[EveryAI Failover Warning] Pass {pass_idx}/{max_passes}, "
                        f"Config {config_idx} ({prov}/{model_name}) failed due to: {type(e).__name__} ({e}). "
                        f"Routing to next alternate..."
                    )
                    
        # If we reached here, it means all fallback chain configurations failed across all retry passes
        # Raise master exception detailing all failures
        failures_summary = "\n".join(
            f"  - Pass {f['pass']} Config {f['config_index']} ({f['provider']}/{f['model']}): {f['error_type']} - {f['error_message']}"
            for f in failures
        )
        
        raise EveryAIError(
            f"Inference failed. All fallback configurations in the chain failed after {max_passes} passes.\n"
            f"Attempt Details:\n{failures_summary}"
        )

    def _wrap_stream_telemetry(
        self,
        generator,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int | None,
        use_cache: bool,
        **kwargs
    ):
        """Yields chunks from the stream and logs usage telemetry on completion or error."""
        from everyai_core.exceptions import (
            RateLimitError,
            AuthenticationError,
            ProviderError,
            ContextLengthExceededError,
            InvalidRequestError,
            ProviderServerError,
            NetworkError,
        )
        
        total_prompt = None
        total_completion = None
        accumulated_chunks = []
        
        try:
            for chunk in generator:
                if chunk.usage:
                    if chunk.usage.prompt_tokens is not None:
                        total_prompt = chunk.usage.prompt_tokens
                    if chunk.usage.completion_tokens is not None:
                        total_completion = chunk.usage.completion_tokens
                accumulated_chunks.append(chunk)
                yield chunk
                
            # Log successful stream completion
            self.tracker.log_call(
                provider=provider,
                model=model,
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                status="success"
            )
            
            # Record tokens in governor
            total_tok = (total_prompt or 0) + (total_completion or 0)
            self.governor.record_request(total_tok)
            
            # Write success to cache if caching is enabled
            if use_cache and accumulated_chunks:
                first_chunk = accumulated_chunks[0]
                
                # Combine choices content from chunks
                combined_content = ""
                for chunk in accumulated_chunks:
                    if chunk.choices and chunk.choices[0].message:
                        content_delta = chunk.choices[0].message.get("content", "")
                        if content_delta:
                            combined_content += content_delta
                
                from everyai_core.types import ChatCompletionChoice, UsageInfo
                reconstructed_choices = [
                    ChatCompletionChoice(
                        index=0,
                        message={"role": "assistant", "content": combined_content},
                        finish_reason=accumulated_chunks[-1].choices[0].finish_reason if (accumulated_chunks[-1].choices and accumulated_chunks[-1].choices[0]) else None
                    )
                ]
                
                reconstructed_usage = UsageInfo(
                    prompt_tokens=total_prompt,
                    completion_tokens=total_completion,
                    total_tokens=total_tok
                )
                
                reconstructed_res = ChatCompletionResponse(
                    id=first_chunk.id,
                    object=first_chunk.object or "chat.completion",
                    created=first_chunk.created,
                    model=model,
                    choices=reconstructed_choices,
                    usage=reconstructed_usage,
                    provider=provider
                )
                
                self.cache.set(
                    messages=messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response=reconstructed_res,
                    **kwargs
                )
        except RateLimitError as e:
            self.tracker.log_call(provider=provider, model=model, status="rate_limit", error_message=str(e))
            raise
        except AuthenticationError as e:
            self.tracker.log_call(provider=provider, model=model, status="auth_error", error_message=str(e))
            raise
        except ContextLengthExceededError as e:
            self.tracker.log_call(provider=provider, model=model, status="context_exceeded", error_message=str(e))
            raise
        except InvalidRequestError as e:
            self.tracker.log_call(provider=provider, model=model, status="invalid_request", error_message=str(e))
            raise
        except ProviderServerError as e:
            self.tracker.log_call(provider=provider, model=model, status="server_error", error_message=str(e))
            raise
        except ProviderError as e:
            self.tracker.log_call(provider=provider, model=model, status="provider_error", error_message=str(e))
            raise
        except NetworkError as e:
            self.tracker.log_call(provider=provider, model=model, status="network_error", error_message=str(e))
            raise
        except Exception as e:
            self.tracker.log_call(provider=provider, model=model, status="error", error_message=str(e))
            raise

    def list_models(self, provider: str) -> list[ModelInfo]:
        """List models available for a specified provider.

        Args:
            provider: The name identifier of the provider (e.g. 'groq').

        Returns:
            A list of ModelInfo details.
        """
        provider_instance = self.get_provider(provider)
        return provider_instance.list_models()

    def list_providers(self) -> list[str]:
        """List all supported/registered provider names.

        Returns:
            A list of strings.
        """
        from everyai_core.providers import list_providers
        return list_providers()

    def show_dashboard(self, port: int = 8080) -> None:
        """Start a local web server and open the telemetry dashboard in the browser.

        Args:
            port: Port to start the dashboard web server on.
        """
        from everyai_core.dashboard import start_dashboard
        start_dashboard(port=port, db_path=self.tracker.db_path)
