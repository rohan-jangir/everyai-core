# EveryAI-Core Library Architecture & Modules Reference

This document provides a comprehensive overview of the directory structure, modules, classes, and key functions in the `everyai-core` Python library. It acts as a developer guide to understand the purpose and usage of every component.

---

## Directory Structure

```text
everyai-core/
└── py_package/
    ├── everyai_core/
    │   ├── __init__.py           # Package exports & metadata
    │   ├── client.py             # Main entry point and orchestration client
    │   ├── config.py             # Configuration and API key resolver
    │   ├── types.py              # Standard dataclasses & TypedDict schemas
    │   ├── cache.py              # SQLite-based request caching
    │   ├── governor.py           # Pre-request rate limit throttle governor
    │   ├── routing.py            # Presets and resolver for smart auto-pilot routing
    │   ├── tracker.py            # Telemetry logger & db manager
    │   ├── dashboard.py          # Dashboard HTTP server & request handler
    │   ├── cli.py                # Command Line Interface (CLI) runner
    │   ├── exceptions.py         # Custom exception translation & definitions
    │   └── providers/            # Provider implementations directory
    │       ├── __init__.py       # Provider registry & plugin manager
    │       ├── base.py           # Base abstract class for all providers
    │       ├── groq.py           # Direct HTTP client for Groq APIs
    │       ├── openrouter.py     # Direct HTTP client for OpenRouter APIs
    │       └── huggingface.py    # Serverless Cloud REST & Local Transformers runner
    ├── tests/                    # Comprehensive unit tests suite
    ├── pyproject.toml            # Library packaging & optional extras definition
    └── README.md                 # Project entry document
```

---

## 1. Core Orchestration & Setup

### `everyai_core.__init__`
* **Purpose**: Serves as the main module package boundary. Exposes the primary developer API interface directly so import paths remain clean (e.g. `from everyai_core import EveryAI`).
* **Key Exports**:
  - `EveryAI` client class
  - `UsageTracker` class
  - Standard Dataclasses (`ChatCompletionResponse`, `UsageInfo`, `ModelInfo`, etc.)
  - Library-specific Exception classes (`EveryAIError`, `AuthenticationError`, etc.)

---

### `everyai_core.client`
* **Purpose**: The central coordinator of the library. It acts as the gateway interface that developers instantiate to execute chats, listing models, and booting dashboard metrics.
* **Classes**:
  - **`EveryAI`**: 
    - `__init__(api_keys, db_path, fallback_chain, cache, cache_path, max_requests_per_minute, max_tokens_per_minute, **kwargs)`: Initializes database paths, caching engines, rate governor settings, and custom base URL overrides.
    - `get_provider(provider_name, api_key_override)`: Lazily instantiates and caches provider client classes matching `(provider, api_key)` pairs to support multi-account credentials.
    - `chat(...)`: Main orchestration method supporting streaming and non-streaming request cycles. Manages local rate limit checks, intercepts cache hits, handles fallback transitions if a provider rate-limits or crashes, and logs all telemetry call data.
    - `list_models(provider)`: Resolves provider class instances and queries their supported models catalog.
    - `list_providers()`: Lists registered providers.
    - `show_dashboard(port)`: Boots the telemetry monitoring interface.

---

### `everyai_core.config`
* **Purpose**: Resolves provider access credentials case-insensitively.
* **Classes**:
  - **`Config`**:
    - `PROVIDER_ENV_MAP`: Maps provider names to common environment variables (e.g., `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`).
    - `get_api_key(provider, user_provided_key)`: Resolves API keys. Checks explicit arguments passed to the client first, falling back to matching environment variables.

---

### `everyai_core.types`
* **Purpose**: Defines standardized, strongly-typed data structures returned by the SDK to guarantee consistent access properties regardless of which underlying LLM API is queried.
* **Classes**:
  - **`Message` (TypedDict)**: Schema representing prompt message components (`role` of either `system`/`user`/`assistant`, and string `content`).
  - **`UsageInfo` (Dataclass)**: Captures input and output token counts (`prompt_tokens`, `completion_tokens`, `total_tokens`). Includes a `to_dict()` helper.
  - **`ChatCompletionChoice` (Dataclass)**: Holds candidate completion results including the choice index, `Message` dictionary, and `finish_reason`.
  - **`ChatCompletionResponse` (Dataclass)**: Root response schema matching standard OpenAI-like structures: carries response `id`, `object`, `created` timestamp, `model` name, `provider` key, choices list, and token `usage` metrics.
  - **`ModelInfo` (Dataclass)**: Structure containing model info returned when listing provider availability catalogs.

---

## 2. Advanced Free-Tier Optimizers

### `everyai_core.cache`
* **Purpose**: Local response caching system to avoid re-triggering API queries on duplicate inputs. Extremely useful to save tokens and avoid provider rate limit blocks during repetitive development loops.
* **Classes**:
  - **`RequestCache`**:
    - `__init__(db_path)`: Resolves SQLite caching DB filepath (defaults to `~/.everyai/cache.db`).
    - `_generate_hash(...)`: Computes a unique SHA-256 hash representation of the request parameters (messages structure, provider, model name, temperature, and token limits). Ensures message lists are sorted by keys to preserve consistency.
    - `get(...)`: Queries cache matching the hash signature. On a hit, reconstructs and returns a `ChatCompletionResponse` object; returns `None` on cache misses.
    - `set(...)`: Serializes successful response schemas to the cache database.

---

### `everyai_core.governor`
* **Purpose**: Controls client-side rate limits inside a sliding window. Ensures users do not hit provider rate limit bans by pacing outbound traffic.
* **Classes**:
  - **`RateLimitGovernor`**:
    - `__init__(max_requests_per_minute, max_tokens_per_minute)`: Defines throttling limits.
    - `throttle_if_needed(estimated_tokens)`: Examines recent sliding history. If triggering the current request will exceed configured limits, sleeps the thread and displays a clean ASCII notice in the terminal.
    - `record_request(tokens_used)`: Logs request timestamps and tokens inside a 60-second deque sliding window.

---

### `everyai_core.routing`
* **Purpose**: Preset configurations for smart routing and auto-pilot execution.
* **Key Components**:
  - **`ROUTING_PRESETS` (Dictionary)**: Prioritized fallbacks matching different user requirements:
    - `"fastest"`: Groq Llama3-8b -> OpenRouter Llama3-8b -> HF Llama3-8b.
    - `"smartest"`: Groq Llama3-70b -> OpenRouter Gemini Flash -> OpenRouter Claude Haiku.
    - `"balanced"`: Groq Llama3-70b -> Groq Llama3-8b -> OpenRouter Llama3-8b.
  - **`resolve_routing_chain(mode)`**: Matches string keys to routing chain lists, throwing a clean error if the mode is unrecognized.

---

## 3. Telemetry & Web Dashboard

### `everyai_core.tracker`
* **Purpose**: Persistently stores execution records in a local SQLite database for billing estimation, success rates, and token tracking.
* **Classes**:
  - **`UsageTracker`**:
    - `__init__(db_path)`: Initializes SQLite telemetry connection (defaults to `~/.everyai/usage.db`).
    - `log_call(provider, model, prompt_tokens, completion_tokens, status, error_message)`: Records call status (`success`, `rate_limit`, `auth_error`, `cache_hit`) and token numbers. Saves tokens count under cache hits.
    - `get_summary()`: Generates aggregated statistics (total requests, total tokens consumed, cache hits, rate limit count, and provider-specific breakdowns) for UI/CLI consumption.
    - `get_logs(limit)`: Retrieves chronological logs history sorted stably.
    - `clear_logs()`: Resets telemetry history.

---

### `everyai_core.dashboard`
* **Purpose**: Hosts a lightweight HTTP dashboard panel. Serves visual statistics and tabular transaction log entries to developer browsers.
* **Classes**:
  - **`DashboardHandler` (BaseHTTPRequestHandler)**: Implements custom routing to serve HTML/CSS dashboard pages and handle JSON telemetry API requests (`/api/summary`, `/api/logs`, `/api/clear`).
* **Functions**:
  - **`start_dashboard(port, db_path)`**: Boots the multi-threaded HTTP server and prints local access details to the console.

---

### `everyai_core.cli`
* **Purpose**: Command Line Interface utility for EveryAI core.
* **Functions**:
  - **`main()`**: Entrypoint parsing command line arguments. Exposes:
    - `everyai stats`: Prints formatted terminal ASCII summaries of token usage and error logs.
    - `everyai dashboard`: Launches the local HTTP server to monitor calls visually in real-time.

---

## 4. Providers & Platform Bridges

### `everyai_core.providers`
* **Purpose**: Resolves names to provider implementations and supports registering custom extensions.
* **Functions**:
  - `get_provider_class(name)`: Returns the provider class matching name keys (throws clean errors if not found).
  - `register_provider(name, provider_cls)`: Plugs custom classes subclassing `BaseProvider` into the global registry.
  - `list_providers()`: Returns all registered keys.

---

### `everyai_core.providers.base`
* **Purpose**: Contract specifying interface requirements for all LLM providers.
* **Classes**:
  - **`BaseProvider` (ABC)**:
    - `__init__(api_key, base_url, **kwargs)`: Saves configurations.
    - `chat(...)` (Abstract): Interface for LLM completions.
    - `list_models()` (Abstract): Interface for listing available models.

---

### `everyai_core.providers.groq`
* **Purpose**: Direct HTTP client to Groq's high-speed API endpoints.
* **Classes**:
  - **`GroqProvider` (BaseProvider)**:
    - `chat(...)`: Performs `httpx` POST completion requests. On non-streaming, parses the response JSON to return a unified `ChatCompletionResponse`. On streaming, processes chunk byte rows and yields parsed completion items generator blocks.
    - `list_models()`: Hits Groq list models endpoints to return metadata summaries.

---

### `everyai_core.providers.openrouter`
* **Purpose**: Direct HTTP client for OpenRouter model routers.
* **Classes**:
  - **`OpenRouterProvider` (BaseProvider)**:
    - `chat(...)`: Handles headers including referral settings and fires raw REST requests. Yields standard streaming structures or returns complete response packages.
    - `list_models()`: Downloads OpenRouter catalog details.

---

### `everyai_core.providers.huggingface`
* **Purpose**: Dual cloud serverless and local transformer inference provider.
* **Classes**:
  - **`HuggingFaceProvider` (BaseProvider)**:
    - `chat(...)`: Inspects `local` keyword switches to delegate calls to cloud serverless endpoints or local weights runner.
    - `_chat_cloud(...)`: REST client hitting Hugging Face Serverless Inference API endpoints with streaming token processing.
    - `_chat_local(...)`: Local PyTorch execution. Validates packages imports dynamically. Lazily downloads models and tokenizers to an in-memory cache, detects and configures system device targets (CUDA GPU, Apple Silicon MPS, or CPU), handles inputs via `apply_chat_template`, runs generation, and streams output chunks using a background thread `TextIteratorStreamer` class.
    - `list_models()`: Returns list of default supported models.

---

### `everyai_core.providers.cerebras`
* **Purpose**: Direct HTTP client to Cerebras's high-speed Inference API.
* **Classes**:
  - **`CerebrasProvider` (BaseProvider)**:
    - `chat(...)`: Performs `httpx` POST completion requests matching OpenAI payload structure. Supports streaming SSE responses.
    - `list_models()`: Queries Cerebras model listing catalog.

---

### `everyai_core.providers.mistral`
* **Purpose**: Direct HTTP client to Mistral's Inference API.
* **Classes**:
  - **`MistralProvider` (BaseProvider)**:
    - `chat(...)`: Queries Mistral completions endpoint. Supports SSE streaming delta parsing.
    - `list_models()`: Retrieves Mistral models catalog information.

---

### `everyai_core.providers.cloudflare`
* **Purpose**: Direct HTTP client to Cloudflare's direct AI Run REST API.
* **Classes**:
  - **`CloudflareProvider` (BaseProvider)**:
    - `chat(...)`: Performs POST completions using the user's Cloudflare Account ID and target model. Supports parsing Cloudflare's direct streaming `{"response": "..."}` JSON payloads.
    - `list_models()`: Exposes a preset lists of supported models on Cloudflare.

---

### `everyai_core.providers.nvidia`
* **Purpose**: Direct HTTP client to Nvidia's NIM Integrate API.
* **Classes**:
  - **`NvidiaProvider` (BaseProvider)**:
    - `chat(...)`: Performs NIM completions POST requests. Supports custom parameters such as `reasoning_budget` and streaming SSE chunks.
    - `list_models()`: Lists NIM models.

---

## 5. Exceptions Mapping

### `everyai_core.exceptions`
* **Purpose**: Maps provider raw HTTP errors to clean, standardized, and user-friendly SDK exceptions. Contains suggestion helper blocks.
* **Classes**:
  - **`EveryAIError`**: Base exception class.
  - **`ConfigurationError`**: Raised for wrong API configurations, empty keys, or missing local libraries. Appends diagnostic terminal install steps.
  - **`ModelNotFoundError`**: Raised for invalid model identifier mappings (HTTP 404).
  - **`NetworkError`**: Raised for connection timeouts and socket resolve errors.
  - **`ProviderError`**: Base wrapper for all remote API crashes (preserves exact raw error messages returned by endpoints).
  - **`AuthenticationError` (ProviderError)**: Raised on API key invalidation (HTTP 401).
  - **`RateLimitError` (ProviderError)**: Raised on remote rate limiting (HTTP 429).
  - **`ContextLengthExceededError` (ProviderError)**: Raised when prompts exceed model context lengths.
  - **`InvalidRequestError` (ProviderError)**: Raised on bad request configurations (HTTP 400).
  - **`ProviderServerError` (ProviderError)**: Raised on provider side downtime/crashes (HTTP 5xx).
* **Functions**:
  - **`raise_for_status(provider, status_code, response_text)`**: Inspects provider formats, parses error JSON payload structures, extracts details, and throws the correct exception subclass instance.
