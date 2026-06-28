/**
 * System configuration provider for EveryAI client settings and API keys.
 */
export class Config {
    // Map providers to their commonly used environment variables (in order of priority)
    static PROVIDER_ENV_MAP = {
        "groq": ["GROQ_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_KEY"],
        "huggingface": ["HUGGINGFACE_API_KEY", "HF_TOKEN", "HF_API_KEY"],
        "cerebras": ["CEREBRAS_API_KEY"],
        "mistral": ["MISTRAL_API_KEY", "MISTRAL_APIKEY"],
        "cloudflare": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY", "CF_API_TOKEN"],
        "nvidia": ["NVIDIA_API_KEY"],
    };

    /**
     * Resolve API key for a given provider.
     * Checks user input first, then falls back to environment variables.
     * 
     * @param {string} provider The provider name (e.g. 'groq').
     * @param {string} [userProvidedKey] The developer-supplied API key.
     * @returns {string|null} The resolved API key or null.
     */
    static getApiKey(provider, userProvidedKey = null) {
        if (userProvidedKey) {
            return userProvidedKey;
        }

        const providerLower = provider.toLowerCase();
        const envKeys = this.PROVIDER_ENV_MAP[providerLower] || [`${providerLower.toUpperCase()}_API_KEY`];

        // Safely access process.env for Node/Common environments
        const env = typeof process !== "undefined" ? process.env : {};

        for (const varName of envKeys) {
            const key = env[varName];
            if (key) {
                return key;
            }
        }

        return null;
    }
}
