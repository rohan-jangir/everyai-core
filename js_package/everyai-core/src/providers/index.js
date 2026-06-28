import { BaseProvider } from "./base.js";
import { GroqProvider } from "./groq.js";
import { OpenRouterProvider } from "./openrouter.js";
import { HuggingFaceProvider } from "./huggingface.js";
import { CerebrasProvider } from "./cerebras.js";
import { MistralProvider } from "./mistral.js";
import { CloudflareProvider } from "./cloudflare.js";
import { NvidiaProvider } from "./nvidia.js";

// Global registry mapping lowercased provider names to their classes
const _registry = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "huggingface": HuggingFaceProvider,
    "cerebras": CerebrasProvider,
    "mistral": MistralProvider,
    "cloudflare": CloudflareProvider,
    "nvidia": NvidiaProvider,
};

/**
 * Retrieve the provider class associated with a specific name.
 * 
 * @param {string} name The name identifier of the provider.
 * @returns {typeof BaseProvider} The provider class.
 * @throws {Error} If the provider name is not registered.
 */
export function getProviderClass(name) {
    const providerKey = name.trim().toLowerCase();
    if (!(providerKey in _registry)) {
        throw new Error(
            `Unsupported provider: '${name}'. ` +
            `Currently supported: ${listProviders().join(", ")}`
        );
    }
    return _registry[providerKey];
}

/**
 * Register a custom provider class into the EveryAI ecosystem.
 * 
 * @param {string} name Unique name identifier for the provider.
 * @param {typeof BaseProvider} providerCls The provider class inheriting from BaseProvider.
 * @throws {TypeError} If provider class is invalid.
 */
export function registerProvider(name, providerCls) {
    if (!(providerCls.prototype instanceof BaseProvider)) {
        throw new TypeError("Provider class must inherit from BaseProvider");
    }
    
    const providerKey = name.trim().toLowerCase();
    _registry[providerKey] = providerCls;
}

/**
 * Get a list of all registered provider names.
 * 
 * @returns {Array<string>} A list of supported providers.
 */
export function listProviders() {
    return Object.keys(_registry);
}

export {
    BaseProvider,
    GroqProvider,
    OpenRouterProvider,
    HuggingFaceProvider,
    CerebrasProvider,
    MistralProvider,
    CloudflareProvider,
    NvidiaProvider
};
