import { Config } from "./config.js";
import { resolveRoutingChain } from "./routing.js";
import { UsageTracker } from "./tracker.js";
import { RequestCache } from "./cache.js";
import { RateLimitGovernor } from "./governor.js";
import { getProviderClass, listProviders } from "./providers/index.js";
import { startDashboard } from "./dashboard.js";
import {
    EveryAIError,
    ConfigurationError,
    AuthenticationError,
    RateLimitError,
    ContextLengthExceededError,
    InvalidRequestError,
    ProviderServerError,
    ProviderError,
    NetworkError,
    ModelNotFoundError
} from "./exceptions.js";
import {
    ChatCompletionResponse,
    ChatCompletionChoice,
    UsageInfo
} from "./types.js";

/**
 * The central client for everyai-core.
 * Provides programmatic access to all supported AI model providers.
 */
export default class EveryAI {
    /**
     * Initialize the EveryAI client.
     * 
     * @param {Object} [options]
     * @param {Record<string, string>} [options.apiKeys] Dictionary mapping provider keys (e.g. 'groq') to their API keys.
     * @param {Record<string, string>} [options.api_keys] Snake-case alias for apiKeys.
     * @param {string} [options.dbPath] Optional custom path for the usage tracking JSON file.
     * @param {string} [options.db_path] Snake-case alias for dbPath.
     * @param {Array<Object>} [options.fallbackChain] Default list of fallback configurations.
     * @param {Array<Object>} [options.fallback_chain] Snake-case alias for fallbackChain.
     * @param {boolean} [options.cache] Whether prompt-response caching is enabled globally (default: false).
     * @param {string} [options.cachePath] Optional custom path for the caching JSON file.
     * @param {string} [options.cache_path] Snake-case alias for cachePath.
     * @param {number} [options.maxRequestsPerMinute] Local limit of requests per minute (default: null).
     * @param {number} [options.max_requests_per_minute] Snake-case alias for maxRequestsPerMinute.
     * @param {number} [options.maxTokensPerMinute] Local limit of prompt+completion tokens per minute (default: null).
     * @param {number} [options.max_tokens_per_minute] Snake-case alias for maxTokensPerMinute.
     * @param {Object} [options.clientConfig] Extra global provider configurations.
     */
    constructor(options = {}) {
        const apiKeys = options.apiKeys || options.api_keys || {};
        const dbPath = options.dbPath || options.db_path || null;
        const fallbackChain = options.fallbackChain || options.fallback_chain || [];
        const routingPresets = options.routingPresets || options.routing_presets || {};
        const providerConfig = options.providerConfig || options.provider_config || {};
        const cache = options.cache || false;
        const cachePath = options.cachePath || options.cache_path || null;
        const maxRequestsPerMinute = options.maxRequestsPerMinute ?? options.max_requests_per_minute ?? null;
        const maxTokensPerMinute = options.maxTokensPerMinute ?? options.max_tokens_per_minute ?? null;

        this.apiKeys = {};
        // Normalize keys to lowercase
        for (const [k, v] of Object.entries(apiKeys)) {
            this.apiKeys[k.trim().toLowerCase()] = v;
        }

        this.fallbackChain = fallbackChain;
        this.routingPresets = routingPresets;
        this.providerConfig = {};
        for (const [k, v] of Object.entries(providerConfig)) {
            this.providerConfig[k.trim().toLowerCase()] = v;
        }
        
        // Extract extra config arguments
        const destructuringKeys = [
            "apiKeys", "api_keys", "dbPath", "db_path", "fallbackChain", "fallback_chain",
            "routingPresets", "routing_presets", "providerConfig", "provider_config",
            "cache", "cachePath", "cache_path", "maxRequestsPerMinute", "max_requests_per_minute",
            "maxTokensPerMinute", "max_tokens_per_minute"
        ];
        this.clientConfig = {};
        for (const [k, v] of Object.entries(options)) {
            if (!destructuringKeys.includes(k)) {
                this.clientConfig[k] = v;
            }
        }

        /** @type {Record<string, import("./providers/base.js").BaseProvider>} */
        this._providerInstances = {};
        this.tracker = new UsageTracker(dbPath);
        this.cacheEnabled = cache;
        this.cache = new RequestCache(cachePath);
        this.governor = new RateLimitGovernor(maxRequestsPerMinute, maxTokensPerMinute);
    }

    /**
     * Lazily initialize and fetch a provider instance.
     * 
     * @param {string} providerName The name identifier of the provider.
     * @param {string|null} [apiKeyOverride] Optional custom API key override.
     * @returns {import("./providers/base.js").BaseProvider} An instantiated provider class.
     * @throws {ConfigurationError} If no API key can be resolved for the provider.
     */
    getProvider(providerName, apiKeyOverride = null) {
        const normalizedName = providerName.trim().toLowerCase();
        
        // Resolve the API key
        const userKey = apiKeyOverride || this.apiKeys[normalizedName];
        const apiKey = Config.getApiKey(normalizedName, userKey);
        
        if (!apiKey) {
            throw new ConfigurationError(
                `API Key for provider '${providerName}' is not set. ` +
                `Please pass it in during EveryAI initialization via: ` +
                `new EveryAI({ apiKeys: { '${providerName}': 'your_key' } }) ` +
                `or set the environment variable.`
            );
        }
            
        const cacheKey = `${normalizedName}:${apiKey}`;
        
        if (!this._providerInstances[cacheKey]) {
            const ProviderCls = getProviderClass(normalizedName);
            // Merge global client config with per-provider config
            const mergedConfig = { ...this.clientConfig };
            const perProvider = this.providerConfig[normalizedName] || {};
            Object.assign(mergedConfig, perProvider);

            this._providerInstances[cacheKey] = new ProviderCls(
                apiKey,
                mergedConfig.baseUrl || mergedConfig.base_url || null,
                mergedConfig
            );
        }
            
        return this._providerInstances[cacheKey];
    }

    // --- Property Getters for IDE Autocomplete & Easy Access ---

    /**
     * Access the Groq provider client.
     * @type {import("./providers/groq.js").GroqProvider}
     */
    get groq() {
        return /** @type {any} */ (this.getProvider("groq"));
    }

    /**
     * Access the OpenRouter provider client.
     * @type {import("./providers/openrouter.js").OpenRouterProvider}
     */
    get openrouter() {
        return /** @type {any} */ (this.getProvider("openrouter"));
    }

    /**
     * Access the HuggingFace provider client.
     * @type {import("./providers/huggingface.js").HuggingFaceProvider}
     */
    get huggingface() {
        return /** @type {any} */ (this.getProvider("huggingface"));
    }

    /**
     * Access the Cerebras provider client.
     * @type {import("./providers/cerebras.js").CerebrasProvider}
     */
    get cerebras() {
        return /** @type {any} */ (this.getProvider("cerebras"));
    }

    /**
     * Access the Mistral provider client.
     * @type {import("./providers/mistral.js").MistralProvider}
     */
    get mistral() {
        return /** @type {any} */ (this.getProvider("mistral"));
    }

    /**
     * Access the Cloudflare provider client.
     * @type {import("./providers/cloudflare.js").CloudflareProvider}
     */
    get cloudflare() {
        return /** @type {any} */ (this.getProvider("cloudflare"));
    }

    /**
     * Access the Nvidia provider client.
     * @type {import("./providers/nvidia.js").NvidiaProvider}
     */
    get nvidia() {
        return /** @type {any} */ (this.getProvider("nvidia"));
    }

    // --- Generic Unified Methods ---

    /**
     * Submit a chat completion request to a specific provider or fallback chain.
     * 
     * @param {Object} options
     * @param {string} [options.provider] The name identifier of the provider.
     * @param {string} [options.model] The model identifier.
     * @param {Array<Object>} [options.messages] A list of messages (e.g. [{"role": "user", "content": "..."}]).
     * @param {number} [options.temperature] Sampling temperature (default: 0.7).
     * @param {number|null} [options.maxTokens] Maximum number of tokens to generate.
     * @param {number|null} [options.max_tokens] Snake-case alias for maxTokens.
     * @param {boolean} [options.stream] Whether to stream the response (default: false).
     * @param {Array<Object>} [options.fallbackChain] Custom fallback list of configs.
     * @param {Array<Object>} [options.fallback_chain] Snake-case alias for fallbackChain.
     * @param {number} [options.maxPasses] Maximum passes to make over the fallback chain (default: 2).
     * @param {number} [options.max_passes] Snake-case alias for maxPasses.
     * @param {string} [options.mode] Optional auto-pilot routing mode ('fastest', 'smartest', 'balanced').
     * @param {boolean} [options.cache] Whether prompt-response caching is enabled for this call.
     * @returns {Promise<Object|AsyncGenerator<Object, void, unknown>>}
     */
    async chat(options = {}) {
        const provider = options.provider;
        const model = options.model;
        const messages = options.messages || [];
        const temperature = options.temperature ?? 0.7;
        const maxTokens = options.maxTokens ?? options.max_tokens ?? null;
        const stream = options.stream || false;
        let fallbackChain = options.fallbackChain || options.fallback_chain || null;
        const maxPasses = options.maxPasses ?? options.max_passes ?? 2;
        const mode = options.mode || null;
        const cache = options.cache;

        // Extract extra config/kwargs arguments by excluding library options
        const clientOptionsKeys = [
            "provider", "model", "messages", "temperature", 
            "maxTokens", "max_tokens", "stream", 
            "fallbackChain", "fallback_chain", "maxPasses", 
            "max_passes", "mode", "cache"
        ];
        const kwargs = {};
        for (const [k, v] of Object.entries(options)) {
            if (!clientOptionsKeys.includes(k)) {
                kwargs[k] = v;
            }
        }

        // Resolve auto-pilot mode to fallback chain
        if (mode) {
            fallbackChain = resolveRoutingChain(mode, this.routingPresets);
        }

        const useCache = cache !== undefined ? cache : this.cacheEnabled;

        // 1. Perform cache lookup if caching is enabled
        if (useCache && messages.length > 0) {
            if (provider && model) {
                const cachedRes = this.cache.get(messages, provider, model, temperature, maxTokens, kwargs);
                if (cachedRes) {
                    const savedTokens = cachedRes.usage ? cachedRes.usage.total_tokens : 0;
                    this.tracker.logCall(
                        provider,
                        model,
                        null,
                        null,
                        "cache_hit",
                        String(savedTokens)
                    );
                    if (stream) {
                        async function* cachedStream() {
                            yield cachedRes;
                        }
                        return cachedStream();
                    }
                    return cachedRes;
                }
            } else {
                const targetChain = fallbackChain || this.fallbackChain;
                if (targetChain && targetChain.length > 0) {
                    for (const config of targetChain) {
                        const cProv = config.provider;
                        const cModel = config.model;
                        if (cProv && cModel) {
                            const cachedRes = this.cache.get(messages, cProv, cModel, temperature, maxTokens, kwargs);
                            if (cachedRes) {
                                const savedTokens = cachedRes.usage ? cachedRes.usage.total_tokens : 0;
                                this.tracker.logCall(
                                    cProv,
                                    cModel,
                                    null,
                                    null,
                                    "cache_hit",
                                    String(savedTokens)
                                );
                                if (stream) {
                                    async function* cachedStream() {
                                        yield cachedRes;
                                    }
                                    return cachedStream();
                                }
                                return cachedRes;
                            }
                        }
                    }
                }
            }
        }

        // Determine if we should route using fallback
        const actualChain = fallbackChain || ((!provider && !model) ? this.fallbackChain : null);

        if (actualChain && actualChain.length > 0) {
            return this._chatWithFallback(
                actualChain,
                messages,
                temperature,
                maxTokens,
                stream,
                maxPasses,
                useCache,
                kwargs
            );
        }

        if (!provider || !model) {
            throw new Error(
                "You must specify both 'provider' and 'model', " +
                "or configure/pass a 'fallbackChain' to execute a request."
            );
        }

        return this._chatSingle(
            provider,
            model,
            messages,
            temperature,
            maxTokens,
            stream,
            null,
            useCache,
            kwargs
        );
    }

    /**
     * Runs a single request execution to the specific provider/model config.
     * 
     * @private
     */
    async _chatSingle(
        provider,
        model,
        messages,
        temperature = 0.7,
        maxTokens = null,
        stream = false,
        apiKeyOverride = null,
        cache = null,
        kwargs = {}
    ) {
        const providerInstance = this.getProvider(provider, apiKeyOverride);
        const useCache = cache !== null ? cache : this.cacheEnabled;
        
        // Local Rate Limit Governor Throttling
        const promptLen = messages.reduce((sum, msg) => sum + (msg.content || "").length, 0);
        const estimatedTokens = Math.max(500, Math.floor(promptLen / 4) + (maxTokens || 150));
        await this.governor.throttleIfNeeded(estimatedTokens);

        try {
            const response = await providerInstance.chat(
                model,
                messages,
                temperature,
                maxTokens,
                stream,
                kwargs
            );
            
            if (stream) {
                // Wrap generator to intercept final usage/tokens and cache it
                return this._wrapStreamTelemetry(
                    response,
                    provider,
                    model,
                    messages,
                    temperature,
                    maxTokens,
                    useCache,
                    kwargs
                );
            }
            
            // Record non-streaming log
            const pTok = response.usage ? response.usage.prompt_tokens : null;
            const cTok = response.usage ? response.usage.completion_tokens : null;
            this.tracker.logCall(
                provider,
                model,
                pTok,
                cTok,
                "success"
            );
            
            // Record tokens in governor
            const totalTok = response.usage ? response.usage.total_tokens : 0;
            this.governor.recordRequest(totalTok);
            
            // Write success to cache if caching is enabled
            if (useCache) {
                this.cache.set(
                    messages,
                    provider,
                    model,
                    temperature,
                    maxTokens,
                    response,
                    kwargs
                );
            }
            return response;

        } catch (e) {
            let status = "error";
            if (e instanceof RateLimitError) status = "rate_limit";
            else if (e instanceof AuthenticationError) status = "auth_error";
            else if (e instanceof ContextLengthExceededError) status = "context_exceeded";
            else if (e instanceof InvalidRequestError) status = "invalid_request";
            else if (e instanceof ProviderServerError) status = "server_error";
            else if (e instanceof ProviderError) status = "provider_error";
            else if (e instanceof NetworkError) status = "network_error";

            this.tracker.logCall(provider, model, null, null, status, e.message);
            throw e;
        }
    }

    /**
     * Automatically attempts request execution across a chain of configurations.
     * 
     * @private
     */
    async _chatWithFallback(
        fallbackChain,
        messages,
        temperature = 0.7,
        maxTokens = null,
        stream = false,
        maxPasses = 2,
        cache = null,
        kwargs = {}
    ) {
        if (!fallbackChain || fallbackChain.length === 0) {
            throw new Error("Fallback chain cannot be empty.");
        }

        const failures = [];
        
        for (let passIdx = 1; passIdx <= maxPasses; passIdx++) {
            for (let configIdx = 0; configIdx < fallbackChain.length; configIdx++) {
                const config = fallbackChain[configIdx];
                const prov = config.provider;
                const modelName = config.model;
                const apiKeyOverride = config.apiKey || config.api_key || null;
                
                if (!prov || !modelName) {
                    throw new Error(
                        `Each fallback configuration must define 'provider' and 'model'. ` +
                        `Config index ${configIdx} is invalid.`
                    );
                }
                
                try {
                    const result = await this._chatSingle(
                        prov,
                        modelName,
                        messages,
                        temperature,
                        maxTokens,
                        stream,
                        apiKeyOverride,
                        cache,
                        kwargs
                    );
                    
                    if (passIdx > 1) {
                        console.log(`[EveryAI Info] Succeeded on pass ${passIdx} using ${prov}/${modelName}.`);
                    }
                    return result;
                    
                } catch (e) {
                    failures.push({
                        pass: passIdx,
                        configIndex: configIdx,
                        provider: prov,
                        model: modelName,
                        errorType: e.name || "Error",
                        errorMessage: e.message
                    });
                    
                    console.warn(
                        `[EveryAI Failover Warning] Pass ${passIdx}/${maxPasses}, ` +
                        `Config ${configIdx} (${prov}/${modelName}) failed due to: ${e.name || "Error"} (${e.message}). ` +
                        `Routing to next alternate...`
                    );
                }
            }
        }
        
        const failuresSummary = failures.map(f => 
            `  - Pass ${f.pass} Config ${f.configIndex} (${f.provider}/${f.model}): ${f.errorType} - ${f.errorMessage}`
        ).join("\n");
        
        throw new EveryAIError(
            `Inference failed. All fallback configurations in the chain failed after ${maxPasses} passes.\n` +
            `Attempt Details:\n${failuresSummary}`
        );
    }

    /**
     * Yields chunks from the stream and logs usage telemetry on completion or error.
     * 
     * @private
     */
    async* _wrapStreamTelemetry(
        generator,
        provider,
        model,
        messages,
        temperature,
        maxTokens,
        useCache,
        kwargs
    ) {
        let totalPrompt = null;
        let totalCompletion = null;
        const accumulatedChunks = [];
        
        try {
            for await (const chunk of generator) {
                if (chunk.usage) {
                    if (chunk.usage.prompt_tokens !== undefined && chunk.usage.prompt_tokens !== null) {
                        totalPrompt = chunk.usage.prompt_tokens;
                    }
                    if (chunk.usage.completion_tokens !== undefined && chunk.usage.completion_tokens !== null) {
                        totalCompletion = chunk.usage.completion_tokens;
                    }
                }
                accumulatedChunks.push(chunk);
                yield chunk;
            }
            
            // Log successful stream completion
            this.tracker.logCall(
                provider,
                model,
                totalPrompt,
                totalCompletion,
                "success"
            );
            
            // Record tokens in governor
            const totalTok = (totalPrompt || 0) + (totalCompletion || 0);
            this.governor.recordRequest(totalTok);
            
            // Write success to cache if caching is enabled
            if (useCache && accumulatedChunks.length > 0) {
                const firstChunk = accumulatedChunks[0];
                
                // Combine choices content from chunks
                let combinedContent = "";
                for (const chunk of accumulatedChunks) {
                    if (chunk.choices && chunk.choices[0] && chunk.choices[0].message) {
                        const contentDelta = chunk.choices[0].message.content || "";
                        combinedContent += contentDelta;
                    }
                }
                
                const reconstructedChoices = [
                    new ChatCompletionChoice(
                        0,
                        { role: "assistant", content: combinedContent },
                        accumulatedChunks[accumulatedChunks.length - 1].choices?.[0]?.finish_reason || null
                    )
                ];
                
                const reconstructedUsage = new UsageInfo(
                    totalPrompt,
                    totalCompletion,
                    totalTok
                );
                
                const reconstructedRes = new ChatCompletionResponse(
                    firstChunk.id,
                    firstChunk.object || "chat.completion",
                    firstChunk.created || Math.floor(Date.now() / 1000),
                    model,
                    reconstructedChoices,
                    reconstructedUsage,
                    provider
                );
                
                this.cache.set(
                    messages,
                    provider,
                    model,
                    temperature,
                    maxTokens,
                    reconstructedRes,
                    kwargs
                );
            }
        } catch (e) {
            let status = "error";
            if (e instanceof RateLimitError) status = "rate_limit";
            else if (e instanceof AuthenticationError) status = "auth_error";
            else if (e instanceof ContextLengthExceededError) status = "context_exceeded";
            else if (e instanceof InvalidRequestError) status = "invalid_request";
            else if (e instanceof ProviderServerError) status = "server_error";
            else if (e instanceof ProviderError) status = "provider_error";
            else if (e instanceof NetworkError) status = "network_error";

            this.tracker.logCall(provider, model, null, null, status, e.message);
            throw e;
        }
    }

    /**
     * List models available for a specified provider.
     * 
     * @param {string} provider The name identifier of the provider (e.g. 'groq').
     * @returns {Promise<Array<Object>>} A list of ModelInfo details.
     */
    async listModels(provider) {
        const providerInstance = this.getProvider(provider);
        return providerInstance.listModels();
    }

    /**
     * List all supported/registered provider names.
     * 
     * @returns {Array<string>} A list of strings.
     */
    listProviders() {
        return listProviders();
    }

    /**
     * Start a local web server to display the telemetry dashboard.
     * 
     * @param {number} [port] Port to start the dashboard web server on.
     */
    showDashboard(port = 8080) {
        startDashboard(port, this.tracker.dbPath);
    }

    // --- Snake Case Aliases for Python Parity ---
    get_provider(providerName, apiKeyOverride = null) {
        return this.getProvider(providerName, apiKeyOverride);
    }

    list_models(provider) {
        return this.listModels(provider);
    }

    list_providers() {
        return this.listProviders();
    }

    show_dashboard(port = 8080) {
        return this.showDashboard(port);
    }
}
