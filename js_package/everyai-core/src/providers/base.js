/**
 * Abstract Base Class defining the contract for all LLM providers.
 * All platforms (e.g. Groq, OpenRouter, HuggingFace) must extend this class.
 */
export class BaseProvider {
    /**
     * Initialize the provider with API credentials and custom configuration.
     * 
     * @param {string} apiKey The API key for the provider's service.
     * @param {string|null} [baseUrl] Optional override URL for API calls.
     * @param {Object} [kwargs] Additional provider-specific configuration settings.
     */
    constructor(apiKey, baseUrl = null, kwargs = {}) {
        if (this.constructor === BaseProvider) {
            throw new TypeError("Cannot instantiate BaseProvider directly.");
        }
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.extraConfig = kwargs;
    }

    /**
     * Send a chat completion request to the provider.
     * 
     * @param {string} model The ID/name of the model to query.
     * @param {Array<Object>} messages A list of messages (e.g. [{"role": "user", "content": "..."}]).
     * @param {number} [temperature] Sampling temperature (default: 0.7).
     * @param {number|null} [maxTokens] Maximum number of tokens to generate.
     * @param {boolean} [stream] Whether to stream the response.
     * @param {Object} [kwargs] Provider-specific overrides.
     * @returns {Promise<Object|AsyncGenerator<Object, void, unknown>>}
     * @abstract
     */
    async chat(model, messages, temperature = 0.7, maxTokens = null, stream = false, kwargs = {}) {
        throw new Error(`Method 'chat()' must be implemented by subclass ${this.constructor.name}`);
    }

    /**
     * List available models for this provider's API key.
     * 
     * @returns {Promise<Array<Object>>} A list of model info objects.
     * @abstract
     */
    async listModels() {
        throw new Error(`Method 'listModels()' must be implemented by subclass ${this.constructor.name}`);
    }
}
