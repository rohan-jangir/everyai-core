/**
 * Smart Auto-Pilot Routing presets for everyai-core.
 * Provides preset model lists for speed, intelligence, and balanced operation
 * across free tiers of Groq, OpenRouter, and HuggingFace.
 */
export const ROUTING_PRESETS = {
    "fastest": [
        { provider: "groq", model: "llama3-8b-8192" },
        { provider: "openrouter", model: "meta-llama/llama-3-8b-instruct" },
        { provider: "huggingface", model: "meta-llama/Meta-Llama-3-8B-Instruct" },
    ],
    "smartest": [
        { provider: "groq", model: "llama3-70b-8192" },
        { provider: "openrouter", model: "google/gemini-flash-1.5" },
        { provider: "openrouter", model: "anthropic/claude-3-haiku" },
    ],
    "balanced": [
        { provider: "groq", model: "llama3-70b-8192" },
        { provider: "groq", model: "llama3-8b-8192" },
        { provider: "openrouter", model: "meta-llama/llama-3-8b-instruct" },
    ],
};

export const VALID_MODES = Object.keys(ROUTING_PRESETS);

/**
 * Resolve a prioritized list of provider/model objects based on the requested mode.
 * 
 * @param {string} mode The requested auto-pilot mode ('fastest', 'smartest', 'balanced').
 * @param {Record<string, Array<Object>>|null} [userPresets] User-defined routing presets.
 * @returns {Array<Object>} A list of fallback configuration dictionaries.
 * @throws {Error} If the requested mode is not recognized.
 */
export function resolveRoutingChain(mode, userPresets = null) {
    const modeKey = mode.trim().toLowerCase();
    
    if (!VALID_MODES.includes(modeKey)) {
        throw new Error(
            `Unsupported routing mode: '${mode}'. ` +
            `Supported options: ${VALID_MODES.join(", ")}`
        );
    }

    let chain;
    if (userPresets && modeKey in userPresets) {
        chain = userPresets[modeKey];
    } else if (modeKey in ROUTING_PRESETS) {
        chain = ROUTING_PRESETS[modeKey];
    } else {
        throw new Error(
            `Routing mode '${mode}' is not configured. ` +
            `Please define it when initializing EveryAI:\n` +
            `  new EveryAI({\n` +
            `      routingPresets: {\n` +
            `          '${modeKey}': [\n` +
            `              { provider: 'groq', model: 'llama-3.1-8b-instant' },\n` +
            `              { provider: 'openrouter', model: 'google/gemini-2.5-flash' }\n` +
            `          ]\n` +
            `      }\n` +
            `  })`
        );
    }

    if (!chain || chain.length === 0) {
        throw new Error(
            `Routing mode '${mode}' has an empty chain. ` +
            `Please add at least one { provider: '...', model: '...' } entry.`
        );
    }

    return chain;
}

// Export snake_case alias for compatibility
export const resolve_routing_chain = resolveRoutingChain;
