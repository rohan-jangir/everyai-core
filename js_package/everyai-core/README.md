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
  - [7. Telemetry & Web Dashboard](#7-telemetry--web-dashboard)
- [Error Handling](#error-handling)
- [Security & Packaging Safety](#security--packaging-safety)
- [License](#license)

---

## What is it?
**EveryAI Core** is a Node.js package providing a unified, clean, and highly resilient interface to query multiple free and premium AI providers with zero developer setup. It aims to be the fundamental high-level building block for building robust, production-grade LLM applications in Node.js without vendor lock-in. It handles rate limit governance, response caching, fallback orchestration, and telemetry tracking entirely on the client side, ensuring privacy and reliability.

---

## Main Features
Here are the core capabilities that EveryAI Core does well:
- **Unified SDK Wrapper**: Speak to 7+ major AI platforms (Groq, OpenRouter, Cerebras, Mistral, Cloudflare, Nvidia, Hugging Face) using one single syntax.
- **Failover & Fallback Chains**: Automatically route requests to backup models or providers if an API fails, has downtime, or hits rate limits.
- **Smart Autopilot Routing**: Define custom presets (like speed or quality priorities) at client start-up and execute them using simple mode parameters.
- **Client-Side Rate Governor**: Prevent rate limit bans by pacing your requests automatically based on RPM (Requests Per Minute) and TPM (Tokens Per Minute) caps.
- **Local Response Caching**: Save tokens and achieve near-zero latency for identical prompts using a local JSON cache.
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

Install the core library via npm:

```bash
npm install everyai-core
```

---

## Quick Start

### 1. Set Your Environment Variables
EveryAI searches your environment for keys. Add them to your shell or `.env` file:

```bash
export GROQ_API_KEY="gsk_..."
export OPENROUTER_API_KEY="sk-or-..."
```

### 2. Basic Request
```javascript
import EveryAI from "everyai-core";

// Initialize client (uses environment keys by default)
const client = new EveryAI();

// Run a completion
const response = await client.chat({
    provider: "groq",
    model: "llama-3.1-8b-instant",
    messages: [
        { role: "user", content: "Explain quantum computing in one sentence." }
    ],
    temperature: 0.7
});

console.log(`[${response.provider.toUpperCase()}] ${response.choices[0].message.content}`);
console.log(`Tokens Used: ${response.usage.total_tokens}`);
```

---

## Detailed Module & Feature Guide

### 1. Provider-Specific Direct Clients
You can access provider SDK wrappers directly through client attributes for full autocomplete and IDE integration:

```javascript
import EveryAI from "everyai-core";

const client = new EveryAI({
    apiKeys: { groq: "your_custom_key_here" }
});

// Access Groq direct instance
const response = await client.groq.chat(
    "llama-3.1-8b-instant",
    [{ role: "user", content: "Hi!" }]
);
```

---

### 2. Streaming Response Tokens
For real-time responses, pass `stream: true` to receive a generator yielding chunk responses:

```javascript
import EveryAI from "everyai-core";

const client = new EveryAI();

const chunks = await client.chat({
    provider: "openrouter",
    model: "google/gemini-2.5-flash",
    messages: [{ role: "user", content: "Write a short poem about coding." }],
    stream: true
});

for await (const chunk of chunks) {
    const content = chunk.choices[0].message.content || "";
    process.stdout.write(content);
}
```

---

### 3. Fallback Failover

When building AI applications, API providers can fail due to rate limits, server outages, or network hiccups. The fallback feature prevents your application from crashing by automatically trying a list of backup providers and models in order until one succeeds.

#### How it works:
You provide an ordered list of configurations (each specifying a `provider` and a `model`). EveryAI attempts the first configuration in the list. If it raises any exception (like rate limits, authentication issues, or network errors), EveryAI catches the error, prints a warning message, and automatically retries the request using the next provider and model in your list.

#### Complete Example:

```javascript
import EveryAI from "everyai-core";
import dotenv from "dotenv";
dotenv.config();

const client = new EveryAI({
    apiKeys: {
        groq: process.env.GROQ_API_KEY,
        cerebras: process.env.CEREBRAS_API_KEY,
        openrouter: process.env.OPENROUTER_API_KEY
    }
});

// If groq fails (e.g. rate limit reached), it falls back to cerebras.
// If cerebras also fails, it falls back to openrouter.
const response = await client.chat({
    messages: [{ role: "user", content: "What is the capital of France?" }],
    fallbackChain: [
        { provider: "groq", model: "llama-3.3-70b-versatile" },
        { provider: "cerebras", model: "llama-3.1-70b" },
        { provider: "openrouter", model: "meta-llama/llama-3.1-8b-instruct:free" }
    ]
});

console.log(`Success! Response resolved via: ${response.provider}`);
console.log(`Model used: ${response.model}`);
console.log(`Answer: ${response.choices[0].message.content}`);
```

---

### 4. Autopilot Routing (mode)

Instead of manually defining a fallback chain on every single `chat()` call, you can configure your fallback chains once when initializing the `EveryAI` client. This is called Autopilot Routing.

You define named routing profiles (like `"fastest"`, `"smartest"`, or `"balanced"`) using the `routingPresets` configuration. When you call `.chat()`, you simply pass `mode: "fastest"`, and EveryAI automatically resolves that mode to the corresponding fallback chain you defined.

#### Complete Example:

```javascript
import EveryAI from "everyai-core";
import dotenv from "dotenv";
dotenv.config();

// Configure your fallback chains once at client initialization
const client = new EveryAI({
    apiKeys: {
        groq: process.env.GROQ_API_KEY,
        cloudflare: process.env.CLOUDFLARE_API_KEY
    },
    providerConfig: {
        cloudflare: { accountId: process.env.CLOUDFLARE_ACCOUNT_ID }
    },
    routingPresets: {
        fastest: [
            { provider: "groq", model: "llama-3.1-8b-instant" },
            { provider: "cloudflare", model: "@cf/meta/llama-3.1-8b-instruct" }
        ],
        smartest: [
            { provider: "groq", model: "llama-3.3-70b-versatile" }
        ],
        balanced: [
            { provider: "groq", model: "llama-3.1-8b-instant" }
        ]
    }
});

// Use autopilot mode by passing the mode name
const response = await client.chat({
    messages: [{ role: "user", content: "Hello!" }],
    mode: "fastest"
});

console.log(`Resolved via provider: ${response.provider}`);
```

---

### 5. Client-Side Throttling (Rate Governor)
Pace outbound API requests client-side to prevent hitting provider rate limit caps.

```javascript
import EveryAI from "everyai-core";

// Configure 10 requests and 5,000 tokens maximum per minute
const client = new EveryAI({
    maxRequestsPerMinute: 10,
    maxTokensPerMinute: 5000
});

for (let i = 0; i < 12; i++) {
    const response = await client.chat({
        provider: "groq",
        model: "llama-3.1-8b-instant",
        messages: [{ role: "user", content: `Ping number ${i}` }]
    });
    // The governor will block and throttle execution if limits are exceeded
}
```

---

### 6. Local Query Cache
Enable local request caching backed by a JSON store. Identical prompt inputs with matching model settings are resolved instantly without hitting endpoints, conserving tokens and avoiding rate limits.

```javascript
import EveryAI from "everyai-core";

// Enable caching globally
const client = new EveryAI({ cache: true, cachePath: "./my_cache.json" });

// First call: hits Groq API (takes ~500ms)
const res1 = await client.chat({
    provider: "groq",
    model: "llama-3.1-8b-instant",
    messages: [{ role: "user", content: "Calculate 25 * 40." }]
});

// Second call: resolved instantly from local cache (~1ms)
const res2 = await client.chat({
    provider: "groq",
    model: "llama-3.1-8b-instant",
    messages: [{ role: "user", content: "Calculate 25 * 40." }]
});
```

---

### 7. Telemetry & Web Dashboard

All token counts, call latencies, success rates, and rate limit errors are recorded in a local telemetry JSON database.

#### Query Telemetry via Code:
```javascript
import EveryAI from "everyai-core";

const client = new EveryAI();
// Retrieve telemetry summary
const summary = client.tracker.getSummary();

console.log(`Total Requests: ${summary.total_calls}`);
console.log(`Cache Hits: ${summary.cache_hits_total}`);
console.log(`Tokens Saved: ${summary.tokens_saved_total}`);
```

#### Launch the Web Telemetry Dashboard:
Boot the built-in HTTP server to view real-time statistics, charts, and detailed transaction logs in your web browser:

```bash
everyai dashboard --port 8080
```

Alternatively, print a quick report of statistics directly in your terminal:
```bash
everyai stats
```

---

## Error Handling

EveryAI maps raw HTTP status codes from all providers to clean, standardized exceptions:

```javascript
import EveryAI from "everyai-core";
import { RateLimitError, AuthenticationError, ModelNotFoundError } from "everyai-core/exceptions";

const client = new EveryAI();

try {
    await client.chat({
        provider: "groq",
        model: "non-existent-model",
        messages: [{ role: "user", content: "Hello" }]
    });
} catch (e) {
    if (e instanceof ModelNotFoundError) {
        console.log(`Requested model was not found: ${e.message}`);
    } else if (e instanceof RateLimitError) {
        console.log("Rate limit reached. Pacing requests...");
    } else if (e instanceof AuthenticationError) {
        console.log("Invalid API credentials. Check your keys.");
    }
}
```

---

## Security & Packaging Safety

EveryAI is designed with production safety and security in mind:
1.  **No Leaked Credentials**: API keys are handled entirely in-memory and are never written to telemetry files, logs, or disk.
2.  **No Prompt Logging**: Telemetry logs record only metadata (token count, provider, model name, status, execution duration). Your sensitive prompts and responses are never logged to the telemetry database.
3.  **Strict Package Bundling**: The library excludes local developer `.env` files, temporary verification scripts, cache JSON stores, and unit tests from production.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for the full text.