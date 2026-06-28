import { BaseProvider } from "./base.js";
import { raiseForStatus, ConfigurationError } from "../exceptions.js";
import { ChatCompletionResponse, ChatCompletionChoice, UsageInfo, ModelInfo } from "../types.js";

/**
 * Provider class for HuggingFace LLM APIs (Serverless Cloud).
 */
export class HuggingFaceProvider extends BaseProvider {
    /**
     * Submit a request to Hugging Face Cloud Serverless API.
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
        const isLocal = kwargs.local || this.extraConfig.local || false;
        if (isLocal) {
            throw new ConfigurationError("Local inference is not supported in the JavaScript package. Please use cloud serverless models.");
        }

        const base = (this.baseUrl || "https://api-inference.huggingface.co/v1").replace(/\/$/, "");
        const endpoint = `${base}/chat/completions`;

        const headers = {
            "Authorization": `Bearer ${this.apiKey}`,
            "Content-Type": "application/json",
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

        const timeout = kwargs.timeout ?? this.extraConfig.timeout ?? 90.0;
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
                raiseForStatus("huggingface", response.status, text);
            }

            if (!stream) {
                const data = await response.json();
                const choices = (data.choices || []).map(c => new ChatCompletionChoice(
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
                    "huggingface"
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
            "huggingface"
        );
    }

    /**
     * List standard models available on HuggingFace Hub via API.
     * 
     * @returns {Promise<Array<ModelInfo>>} A list of model info objects.
     */
    async listModels() {
        const endpoint = "https://huggingface.co/api/models?pipeline_tag=text-generation&limit=100&sort=downloads&direction=-1";
        const headers = {};
        if (this.apiKey) {
            headers["Authorization"] = `Bearer ${this.apiKey}`;
        }

        const response = await fetch(endpoint, { headers, timeout: 20000 });
        if (response.status !== 200) {
            const text = await response.text();
            raiseForStatus("huggingface", response.status, text);
        }

        const data = await response.json();
        return data.map(m => new ModelInfo(
            m.modelId || m.id || "",
            m.modelId || m.id || "",
            2048,
            "huggingface",
            { downloads: m.downloads || 0, likes: m.likes || 0 }
        ));
    }
}
