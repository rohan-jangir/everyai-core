# EveryAI Core

## Table of Contents
- [What is it?](#what-is-it)
- [Main Features](#main-features)
- [Supported Providers](#supported-providers)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Detailed Module & Feature Guide](#detailed-module--feature-guide)
  - [1. Provider-Specific Direct Clients](#1-provider-specific-direct-clients)
  - [2. Streaming Response Tokens](#2-streaming-response-tokens)
  - [3. Fallback Failover](#3-fallback-failover)
  - [4. Autopilot Routing (mode)](#4-autopilot-routing-mode)
  - [5. Client-Side Throttling (Rate Governor)](#5-client-side-throttling-rate-governor)
  - [6. Local Query Cache](#6-local-query-cache)
  - [7. Local Offline Models](#7-local-offline-models)
  - [8. Telemetry & Web Dashboard](#8-telemetry--web-dashboard)
- [Error Handling](#error-handling)
- [Security & Packaging Safety](#security--packaging-safety)
- [License](#license)

---

## What is it?
**EveryAI Core** is a Python package providing a unified, unified, and highly resilient interface to query multiple free and premium AI providers with zero developer setup. It aims to be the fundamental high-level building block for building robust, production-grade LLM applications in Python without vendor lock-in. It handles rate limit governance, response caching, fallback orchestration, and telemetry tracking entirely on the client side, ensuring privacy and reliability.

---

## Main Features
Here are the core capabilities that EveryAI Core does well:
- **Unified SDK Wrapper**: Speak to 7+ major AI platforms (Groq, OpenRouter, Cerebras, Mistral, Cloudflare, Nvidia, Hugging Face) using one single syntax.
- **Failover & Fallback Chains**: Automatically route requests to backup models or providers if an API fails, has downtime, or hits rate limits.
- **Smart Autopilot Routing**: Define custom presets (like speed or quality priorities) at client start-up and execute them using simple mode parameters.
- **Client-Side Rate Governor**: Prevent rate limit bans by pacing your requests automatically based on RPM (Requests Per Minute) and TPM (Tokens Per Minute) caps.
- **Local Response Caching**: Save tokens and achieve near-zero latency for identical prompts using a local SQLite cache.
- **Offline Local Model Support**: Seamlessly load and execute open-weights models locally via PyTorch and Transformers through the same interface.
- **Web Telemetry Dashboard**: Run a local HTTP dashboard to analyze query performance, cost, token counts, and API health in real-time.

---

## Supported Providers

Use the exact provider names listed below when querying models or configuring presets:

| Provider Name (Exact Key) | Environment Variable | Key Features |
| :--- | :--- | :--- |
| `groq` | `GROQ_API_KEY` | Ultra-fast LPU inference, native token usage logging |
| `openrouter` | `OPENROUTER_API_KEY` | Aggregated model catalog, free tier routes |
| `huggingface` | `HF_TOKEN` or `HUGGINGFACE_API_KEY` | Serverless API execution of open-weights models |
| `cerebras` | `CEREBRAS_API_KEY` | High-speed wafer-scale engine inference |
| `mistral` | `MISTRAL_API_KEY` | European flagship models, native streaming |
| `cloudflare` | `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` | Workers AI serverless endpoints |
| `nvidia` | `NVIDIA_API_KEY` | GPU-optimized microservice inference |

---

## Installation

Install the core library via pip:

```bash
pip install everyai-core
```

To enable local model inference capabilities (requires PyTorch and Transformers):

```bash
pip install everyai-core[local]
```

---

## Quick Start

### 1. Set Your Environment Variables
EveryAI searches your environment for keys. Add them to your shell or `.env` file:

```bash
export GROQ_API_KEY="gsk_..."
export OPENROUTER_API_KEY="sk-or-..."
```

### 2. Basic Non-Streaming Request
```python
from everyai_core import EveryAI

# Initialize client (uses environment keys by default)
client = EveryAI()

# Run a completion
response = client.chat(
    provider="groq",
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "user", "content": "Explain quantum computing in one sentence."}
    ],
    temperature=0.7
)

print(f"[{response.provider.upper()}] {response.choices[0].message['content']}")
print(f"Tokens Used: {response.usage.total_tokens}")
```

---

## Detailed Module & Feature Guide

### 1. Provider-Specific Direct Clients
You can access provider SDK wrappers directly through client attributes for full autocomplete and static typing support:

```python
from everyai_core import EveryAI

client = EveryAI(api_keys={"groq": "your_custom_key_here"})

# Access Groq direct instance
response = client.groq.chat(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Hi!"}]
)
```

---

### 2. Streaming Response Tokens
For real-time responses, pass `stream=True` to receive a generator yielding chunk responses:

```python
from everyai_core import EveryAI

client = EveryAI()

chunks = client.chat(
    provider="openrouter",
    model="google/gemini-2.5-flash",
    messages=[{"role": "user", "content": "Write a short poem about coding."}],
    stream=True
)

for chunk in chunks:
    content = chunk.choices[0].message.get("content", "")
    print(content, end="", flush=True)
```

---

### 3. Fallback Failover

When building AI applications, API providers can fail due to rate limits, server outages, or network hiccups. The fallback feature prevents your application from crashing by automatically trying a list of backup providers and models in order until one succeeds.

#### How it works:
You provide an ordered list of configurations (each specifying a `provider` and a `model`). EveryAI attempts the first configuration in the list. If it raises any exception (like rate limits, authentication issues, or network errors), EveryAI catches the error, prints a warning message, and automatically retries the request using the next provider and model in your list.

#### Complete Example:

```python
from everyai_core import EveryAI
from dotenv import load_dotenv
import os

load_dotenv()

client = EveryAI(
    api_keys={
        "groq": os.getenv("GROQ_API_KEY"),
        "cerebras": os.getenv("CEREBRAS_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY")
    }
)

# If groq fails (e.g. rate limit reached), it falls back to cerebras.
# If cerebras also fails, it falls back to openrouter.
response = client.chat(
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    fallback_chain=[
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "cerebras", "model": "llama-3.1-70b"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free"}
    ]
)

print(f"Success! Response resolved via: {response.provider}")
print(f"Model used: {response.model}")
print(f"Answer: {response.choices[0].message['content']}")
```

---

### 4. Autopilot Routing (mode)

Instead of manually defining a fallback chain on every single `chat()` call, you can configure your fallback chains once when initializing the `EveryAI` client. This is called Autopilot Routing.

You define named routing profiles (like `"fastest"`, `"smartest"`, or `"balanced"`) using the `routing_presets` dictionary. When you call `.chat()`, you simply pass `mode="fastest"`, and EveryAI automatically resolves that mode to the corresponding fallback chain you defined.

#### Complete Example:

```python
from everyai_core import EveryAI
from dotenv import load_dotenv
import os

load_dotenv()

# Configure your fallback chains once at client initialization
client = EveryAI(
    api_keys={
        "groq": os.getenv("GROQ_API_KEY"),
        "cloudflare": os.getenv("CLOUDFLARE_API_KEY")
    },
    provider_config={
        "cloudflare": {"account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID")}
    },
    routing_presets={
        "fastest": [
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "cloudflare", "model": "@cf/meta/llama-3.1-8b-instruct"}
        ],
        "smartest": [
            {"provider": "groq", "model": "llama-3.3-70b-versatile"}
        ],
        "balanced": [
            {"provider": "groq", "model": "llama-3.1-8b-instant"}
        ]
    }
)

# Use autopilot mode by passing the mode name
response = client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    mode="fastest"
)

print(f"Resolved via provider: {response.provider}")
```

---

### 5. Client-Side Throttling (Rate Governor)
Pace outbound API requests client-side to prevent hitting provider rate limit caps.

```python
from everyai_core import EveryAI

# Configure 10 requests and 5,000 tokens maximum per minute
client = EveryAI(
    max_requests_per_minute=10,
    max_tokens_per_minute=5000
)

for i in range(12):
    response = client.chat(
        provider="groq",
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": f"Ping number {i}"}]
    )
    # The governor will block and throttle execution if limits are exceeded
```

---

### 6. Local Query Cache
Enable local request caching backed by SQLite. Identical prompt inputs with matching model settings are resolved instantly without hitting endpoints, conserving tokens and avoiding rate limits.

```python
from everyai_core import EveryAI

# Enable caching globally
client = EveryAI(cache=True, cache_path="./my_cache.db")

# First call: hits Groq API (takes ~500ms)
res1 = client.chat(
    provider="groq",
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Calculate 25 * 40."}]
)

# Second call: resolved instantly from local SQLite cache (~1ms)
res2 = client.chat(
    provider="groq",
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Calculate 25 * 40."}]
)
```

---

### 7. Local Offline Models
Run open-weights models on your local machine using PyTorch and Hugging Face Transformers.

```python
from everyai_core import EveryAI

client = EveryAI()

# Run OPT-125m locally on CPU/GPU
response = client.chat(
    provider="huggingface",
    model="facebook/opt-125m",
    messages=[{"role": "user", "content": "The weather today is"}],
    local=True  # Enables local transformers inference
)
print(response.choices[0].message["content"])
```

---

### 8. Telemetry & Web Dashboard

All token counts, call latencies, success rates, and rate limit errors are recorded in a local SQLite database.

#### Query Telemetry via Code:
```python
from everyai_core import EveryAI

client = EveryAI()
# Retrieve telemetry summary
summary = client.tracker.get_summary()

print(f"Total Requests: {summary['total_calls']}")
print(f"Cache Hits: {summary['cache_hits_total']}")
print(f"Tokens Saved: {summary['tokens_saved_total']}")
```

#### Launch the Web Telemetry Dashboard:
Boot the built-in HTTP server to view real-time statistics, charts, and detailed transaction logs in your web browser:

```bash
everyai dashboard --port 8080
```

Alternatively, print a quick tabular report of statistics directly in your terminal:
```bash
everyai stats
```

---

## Error Handling

EveryAI maps raw HTTP status codes from all providers to clean, standardized exceptions:

```python
from everyai_core import EveryAI
from everyai_core.exceptions import RateLimitError, AuthenticationError, ModelNotFoundError

client = EveryAI()

try:
    client.chat(
        provider="groq",
        model="non-existent-model",
        messages=[{"role": "user", "content": "Hello"}]
    )
except ModelNotFoundError as e:
    print(f"Requested model was not found: {e}")
except RateLimitError:
    print("Rate limit reached. Pacing requests...")
except AuthenticationError:
    print("Invalid API credentials. Check your keys.")
```

---

## Security & Packaging Safety

EveryAI is designed with production safety and security in mind:
1.  **No Leaked Credentials**: API keys are handled entirely in-memory and are never written to telemetry databases, logs, or disk.
2.  **No Prompt Logging**: Telemetry logs record only metadata (token count, provider, model name, status, execution duration). Your sensitive prompts and responses are never logged to the telemetry database.
3.  **Strict Package Bundling**: The library's `MANIFEST.in` explicitly excludes local developer `.env` files, temporary verification scripts, cache SQLite database stores, and unit tests. You can deploy it to public directories with confidence.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for the full text.