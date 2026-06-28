import { BaseProvider } from "./base.js";
import { raiseForStatus, ConfigurationError } from "../exceptions.js";
import { ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo } from "../types.js";

/**
 * Provider class for Cloudflare AI API.
 */
export class CloudflareProvider extends BaseProvider {
    /**
     * Send a chat completion request to Cloudflare direct AI Run endpoint.
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
        // Resolve Account ID
        const accountId = kwargs.accountId || kwargs.account_id || 
                          this.extraConfig.accountId || this.extraConfig.account_id || 
                          process.env.CLOUDFLARE_ACCOUNT_ID;
        if (!accountId) {
            throw new ConfigurationError(
                "Cloudflare AI requires 'account_id'. Please pass it via " +
                "new EveryAI({ providerConfig: { 'cloudflare': { 'account_id': 'your_id' } } }), " +
                "or set the environment variable 'CLOUDFLARE_ACCOUNT_ID'."
            );
        }

        const base = (this.baseUrl || `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run`).replace(/\/$/, "");
        const cleanModel = model.replace(/^\//, "");
        const endpoint = `${base}/${cleanModel}`;

        const headers = {
            "Authorization": `Bearer ${this.apiKey}`,
            "Content-Type": "application/json",
        };

        const payload = {
            messages: messages,
            stream: stream,
        };
        if (temperature !== 0.7) {
            payload["temperature"] = temperature;
        }
        if (maxTokens !== null) {
            payload["max_tokens"] = maxTokens;
        }

        // Merge overrides
        Object.assign(payload, kwargs);

        const timeout = kwargs.timeout ?? this.extraConfig.timeout ?? 20.0;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout * 1000);

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: headers,
                body: JSON.stringify(payload),
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (response.status !== 200) {
                const text = await response.text();
                raiseForStatus("cloudflare", response.status, text);
            }

            if (!stream) {
                const data = await response.json();
                if (!data.success) {
                    const errors = data.errors || [];
                    const errMsg = (errors[0] && errors[0].message) ? errors[0].message : "Cloudflare query failed";
                    raiseForStatus("cloudflare", 400, errMsg);
                }

                const result = data.result || {};
                const content = result.response || "";

                const choices = [
                    new ChatCompletionChoice(
                        0,
                        { role: "assistant", content: content },
                        "stop"
                    )
                ];

                return new ChatCompletionResponse(
                    null,
                    "chat.completion",
                    0,
                    model,
                    choices,
                    new UsageInfo(null, null, null),
                    "cloudflare"
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
                        const { value, done } = await reader.read();
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
            clearTimeout(timeoutId);
            throw error;
        }
    }

    /**
     * Parse Cloudflare streaming chunk into a ChatCompletionResponse.
     * 
     * @private
     * @param {Object} chunkData
     * @param {string} model
     * @returns {ChatCompletionResponse}
     */
    _parseChunk(chunkData, model) {
        const content = chunkData.response || "";
        const choices = [
            new ChatCompletionChoice(
                0,
                { role: "assistant", content: content },
                null
            )
        ];

        return new ChatCompletionResponse(
            null,
            "chat.completion.chunk",
            0,
            model,
            choices,
            null,
            "cloudflare"
        );
    }

    /**
     * List models available for Cloudflare AI (presets list).
     * 
     * @returns {Promise<Array<ModelInfo>>} A list of model info objects.
     */
    async listModels() {
        const presets = [
            "@cf/meta/llama-3-8b-instruct",
            "@cf/meta/llama-3-70b-instruct",
            "@cf/mistral/mistral-7b-instruct-v0.1",
            "@cf/meta/llama-2-7b-chat-int8"
        ];
        return presets.map(p => new ModelInfo(
            p,
            p.split("/").pop(),
            2048,
            "cloudflare"
        ));
    }
}
