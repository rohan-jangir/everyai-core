/**
 * Base error class for all EveryAI library exceptions.
 */
export class EveryAIError extends Error {
    constructor(message) {
        super(message);
        this.name = this.constructor.name;
        if (Error.captureStackTrace) {
            Error.captureStackTrace(this, this.constructor);
        }
    }
}

/**
 * Raised when the client is misconfigured or lacks required API keys.
 */
export class ConfigurationError extends EveryAIError {
    constructor(message) {
        super(
            `[Configuration Error] ${message}\n` +
            `[Suggestion]: Please verify that you have passed the correct API keys when initializing ` +
            `EveryAI(api_keys={...}) or that you have set the corresponding environment variables (e.g. GROQ_API_KEY).`
        );
    }
}

/**
 * Raised when the requested model is not found or unsupported on the client side.
 */
export class ModelNotFoundError extends EveryAIError {
    constructor(message) {
        super(
            `[Model Not Found] ${message}\n` +
            `[Suggestion]: Double-check the spelling of the model identifier. You can retrieve a list of supported ` +
            `models by calling \`EveryAI.list_models(provider)\` or query the provider's official model catalog.`
        );
    }
}

/**
 * Raised when a connection to an AI provider's server fails or times out on the client side.
 */
export class NetworkError extends EveryAIError {
    constructor(message) {
        super(
            `[Network Connection Error] ${message}\n` +
            `[Suggestion]: Check your local internet connectivity, DNS configuration, proxy settings, or firewall.`
        );
    }
}

/**
 * Base exception for errors returned by LLM providers' APIs.
 * Preserves the raw error message from the provider without client-side suggestions.
 */
export class ProviderError extends EveryAIError {
    constructor(message, provider, statusCode = null, responseBody = null) {
        let baseMsg = `[${provider.toUpperCase()} API Error]`;
        if (statusCode) {
            baseMsg += ` (Status ${statusCode})`;
        }
        super(`${baseMsg}: ${message}`);
        this.provider = provider;
        this.statusCode = statusCode;
        this.responseBody = responseBody;
        this.rawMessage = message;
    }
}

/**
 * Raised when authentication with a provider fails (e.g. invalid API key).
 */
export class AuthenticationError extends ProviderError {}

/**
 * Raised when the provider returns a rate limit error (HTTP 429).
 */
export class RateLimitError extends ProviderError {}

/**
 * Raised when the prompt or completion exceeds the model's context length limit.
 */
export class ContextLengthExceededError extends ProviderError {}

/**
 * Raised when the request parameters are invalid.
 */
export class InvalidRequestError extends ProviderError {}

/**
 * Raised when the provider's server returns a 5xx error.
 */
export class ProviderServerError extends ProviderError {}

/**
 * Parses HTTP error response from a provider, extracts the message, and raises the correct custom exception.
 * 
 * @param {string} provider Name of the provider.
 * @param {number} statusCode The HTTP status code returned.
 * @param {string} responseText The raw HTTP response body.
 * @throws {EveryAIError}
 */
export function raiseForStatus(provider, statusCode, responseText) {
    const providerKey = provider.trim().toLowerCase();
    let errorMsg = responseText;

    try {
        const data = JSON.parse(responseText);
        if (providerKey === "groq" || providerKey === "openrouter") {
            if (data && typeof data === "object" && data.error) {
                const errInfo = data.error;
                if (errInfo && typeof errInfo === "object") {
                    errorMsg = errInfo.message || errorMsg;
                } else {
                    errorMsg = String(errInfo);
                }
            }
        } else if (providerKey === "huggingface") {
            if (data && typeof data === "object") {
                const errVal = data.error;
                if (Array.isArray(errVal)) {
                    errorMsg = errVal.join(", ");
                } else if (errVal && typeof errVal === "object") {
                    errorMsg = errVal.message || errorMsg;
                } else if (errVal) {
                    errorMsg = String(errVal);
                }
            } else if (Array.isArray(data) && data.length > 0) {
                errorMsg = String(data[0]);
            }
        }
    } catch (e) {
        // Fall back to raw responseText
    }

    if (statusCode === 401) {
        throw new AuthenticationError(errorMsg, provider, statusCode, responseText);
    } else if (statusCode === 429) {
        throw new RateLimitError(errorMsg, provider, statusCode, responseText);
    } else if (statusCode === 404) {
        throw new ModelNotFoundError(`Model not found or provider endpoint error: ${errorMsg}`);
    } else if (statusCode === 400 || statusCode === 422) {
        const msgLower = errorMsg.toLowerCase();
        if (msgLower.includes("context length") || msgLower.includes("context window") || msgLower.includes("max tokens") || msgLower.includes("too large")) {
            throw new ContextLengthExceededError(errorMsg, provider, statusCode, responseText);
        } else {
            throw new InvalidRequestError(errorMsg, provider, statusCode, responseText);
        }
    } else if (statusCode >= 500) {
        throw new ProviderServerError(errorMsg, provider, statusCode, responseText);
    } else {
        throw new ProviderError(errorMsg, provider, statusCode, responseText);
    }
}

// Export snake_case alias for compatibility
export const raise_for_status = raiseForStatus;
