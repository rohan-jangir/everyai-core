import { BaseProvider } from "./base.js";
import { raiseForStatus, NetworkError } from "../exceptions.js";
import { ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo } from "../types.js";

/**
 * Provider class for OpenRouter LLM API.
 */
export class OpenRouterProvider extends BaseProvider {
    /**
     * Send a chat completion request to OpenRouter API using direct HTTP REST.
     * 
     * @param {string} model The ID/name of the model to query.
     * @param {Array<Object>} messages A list of messages.
     * @param {number} [temperature] Sampling temperature (default: 0.7).
     * @param {number|null} [maxTokens] Maximum number of tokens to generate.
     * @param {boolean} [stream] Whether to stream the response.
     * @param {Object} [kwargs] Provider-specific overrides.
     * @returns {Promise<ChatCompletionResponse|AsyncGenerator<ChatCompletionResponse, void, unknown>>}
     */
    async chat(model, messages, temperature = 0.7, maxTokens = null, stream = false, kwargs = {}) {
        const base = (this.baseUrl || "https://openrouter.ai/api/v1").replace(/\/$/, "");
        const endpoint = `${base}/chat/completions`;

        const headers = {
            "Authorization": `Bearer ${this.apiKey}`,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rohan-jangir/everyai-core",
            "X-Title": "EveryAI-Core",
        };

        const payload = {
            model: model,
            messages: messages,
            temperature: temperature,
            stream: stream,
        };
        if (maxTokens !== null) {
            payload["max_tokens"] = maxTokens;
        }

        // Merge overrides
        Object.assign(payload, kwargs);

        const timeout = kwargs.timeout ?? this.extraConfig.timeout ?? 120.0;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

        try {
            let response;
            try {
                response = await fetch(endpoint, {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify(payload),
                    signal: controller.signal
                });
            } catch (err) {
                if (err.name === "AbortError" || err.message?.includes("timeout") || err.message?.includes("fetch")) {
                    throw new NetworkError(
                        `OpenRouter request timed out or failed to connect after ${timeout}s. ` +
                        `The upstream model '${model}' may be slow or temporarily unavailable. ` +
                        `Try increasing the timeout: client.chat(..., { timeout: 300 }) ` +
                        `or try a different model. Original error: ${err.name}: ${err.message}`
                    );
                }
                throw err;
            } finally {
                clearTimeout(timeoutId);
            }

            if (response.status !== 200) {
                const text = await response.text();
                raiseForStatus("openrouter", response.status, text);
            }

            if (!stream) {
                const data = await response.json();
                const rawChoices = data.choices || [];
                
                // Guard against empty choices from OpenRouter
                if (rawChoices.length === 0) {
                    const errorInfo = data.error;
                    if (errorInfo) {
                        const code = typeof errorInfo === "object" ? (errorInfo.code || 500) : 500;
                        raiseForStatus("openrouter", code, JSON.stringify(data));
                    }
                }

                const choices = rawChoices.map(c => new ChatCompletionChoice(
                    c.index ?? 0,
                    c.message || {},
                    c.finish_reason || null
                ));

                let usage = null;
                if (data.usage) {
                    const u = data.usage;
                    usage = new UsageInfo(u.prompt_tokens, u.completion_tokens, u.total_tokens);
                }

                return new ChatCompletionResponse(
                    data.id,
                    data.object || "chat.completion",
                    data.created || 0,
                    data.model || model,
                    choices,
                    usage,
                    "openrouter"
                );
            }

            // Streaming execution
            const self = this;
            async function* streamGenerator() {
                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                try {
                    while (true) {
                        let readRes;
                        try {
                            readRes = await reader.read();
                        } catch (err) {
                            throw new NetworkError(
                                `OpenRouter streaming request timed out or failed to connect. ` +
                                `The upstream model '${model}' may be slow or temporarily unavailable. ` +
                                `Original error: ${err.name}: ${err.message}`
                            );
                        }

                        const { value, done } = readRes;
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split("\n");
                        buffer = lines.pop(); // keep trailing partial line

                        for (let line of lines) {
                            line = line.trim();
                            if (!line) continue;
                            if (line.startsWith("data: ")) {
                                const dataStr = line.slice(6);
                                if (dataStr === "[DONE]") {
                                    return;
                                }
                                try {
                                    const chunkData = JSON.parse(dataStr);
                                    yield self._parseChunk(chunkData, model);
                                } catch (e) {
                                    continue;
                                }
                            }
                        }
                    }
                } finally {
                    reader.releaseLock();
                }
            }

            return streamGenerator();
        } catch (error) {
            throw error;
        }
    }

    /**
     * Parse standard streaming JSON chunk into a ChatCompletionResponse.
     * 
     * @private
     * @param {Object} chunkData
     * @param {string} model
     * @returns {ChatCompletionResponse}
     */
    _parseChunk(chunkData, model) {
        const choices = (chunkData.choices || []).map(c => {
            const delta = c.delta || {};
            let content = delta.content || "";
            if (!content) {
                content = delta.reasoning || delta.reasoning_content || "";
            }
            return new ChatCompletionChoice(
                c.index ?? 0,
                { role: delta.role || "assistant", content: content },
                c.finish_reason || null
            );
        });

        let usage = null;
        if (chunkData.usage) {
            const u = chunkData.usage;
            usage = new UsageInfo(u.prompt_tokens, u.completion_tokens, u.total_tokens);
        }

        return new ChatCompletionResponse(
            chunkData.id,
            chunkData.object || "chat.completion.chunk",
            chunkData.created || 0,
            chunkData.model || model,
            choices,
            usage,
            "openrouter"
        );
    }

    /**
     * List models available for OpenRouter.
     * 
     * @returns {Promise<Array<ModelInfo>>} A list of model info objects.
     */
    async listModels() {
        const base = (this.baseUrl || "https://openrouter.ai/api/v1").replace(/\/$/, "");
        const endpoint = `${base}/models`;

        const response = await fetch(endpoint, { timeout: 20000 });
        if (response.status !== 200) {
            const text = await response.text();
            raiseForStatus("openrouter", response.status, text);
        }

        const data = await response.json();
        return (data.data || []).map(m => new ModelInfo(
            m.id,
            m.name || m.id,
            m.context_length || null,
            m.owned_by || null
        ));
    }
}
