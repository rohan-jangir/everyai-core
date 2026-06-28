/**
 * Standard representation of token usage.
 */
export class UsageInfo {
    /**
     * @param {number|null} [promptTokens]
     * @param {number|null} [completionTokens]
     * @param {number|null} [totalTokens]
     */
    constructor(promptTokens = null, completionTokens = null, totalTokens = null) {
        this.prompt_tokens = promptTokens;
        this.completion_tokens = completionTokens;
        this.total_tokens = totalTokens;
    }

    /**
     * Convert to standard plain object.
     * @returns {Object}
     */
    toDict() {
        return {
            prompt_tokens: this.prompt_tokens,
            completion_tokens: this.completion_tokens,
            total_tokens: this.total_tokens
        };
    }

    /**
     * JSON serialization support.
     * @returns {Object}
     */
    toJSON() {
        return this.toDict();
    }
}

/**
 * A single choice in the chat completion response.
 */
export class ChatCompletionChoice {
    /**
     * @param {number} index
     * @param {{role: string, content: string}} message
     * @param {string|null} [finishReason]
     */
    constructor(index, message, finishReason = null) {
        this.index = index;
        this.message = message;
        this.finish_reason = finishReason;
    }

    /**
     * @returns {Object}
     */
    toDict() {
        return {
            index: this.index,
            message: this.message,
            finish_reason: this.finish_reason
        };
    }

    toJSON() {
        return this.toDict();
    }
}

/**
 * Standard unified structure for all LLM chat responses.
 */
export class ChatCompletionResponse {
    /**
     * @param {string|null} id
     * @param {string} object
     * @param {number} created
     * @param {string} model
     * @param {Array<ChatCompletionChoice>} choices
     * @param {UsageInfo|null} [usage]
     * @param {string|null} [provider]
     */
    constructor(id, object, created, model, choices, usage = null, provider = null) {
        this.id = id;
        this.object = object;
        this.created = created;
        this.model = model;
        this.choices = choices;
        this.usage = usage;
        this.provider = provider;
    }

    /**
     * @returns {Object}
     */
    toDict() {
        return {
            id: this.id,
            object: this.object,
            created: this.created,
            model: this.model,
            choices: this.choices.map(c => c.toDict()),
            usage: this.usage ? this.usage.toDict() : null,
            provider: this.provider
        };
    }

    toJSON() {
        return this.toDict();
    }
}

/**
 * Standard schema representing metadata of a model.
 */
export class ModelInfo {
    /**
     * @param {string} id
     * @param {string} name
     * @param {number|null} [contextLength]
     * @param {string|null} [ownedBy]
     * @param {Object} [extra]
     */
    constructor(id, name, contextLength = null, ownedBy = null, extra = {}) {
        this.id = id;
        this.name = name;
        this.context_length = contextLength;
        this.owned_by = ownedBy;
        this.extra = extra;
    }

    /**
     * @returns {Object}
     */
    toDict() {
        return {
            id: this.id,
            name: this.name,
            context_length: this.context_length,
            owned_by: this.owned_by,
            extra: this.extra
        };
    }

    toJSON() {
        return this.toDict();
    }
}
