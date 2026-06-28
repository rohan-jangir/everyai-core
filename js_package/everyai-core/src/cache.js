import crypto from "crypto";
import fs from "fs";
import path from "path";
import os from "os";

/**
 * Handles local response caching to prevent duplicate API execution.
 */
export class RequestCache {
    /**
     * @param {string} [cachePath] Optional custom file path for the cache.
     */
    constructor(cachePath = null) {
        if (cachePath === null) {
            const dbDir = path.join(os.homedir(), ".everyai");
            if (!fs.existsSync(dbDir)) {
                try {
                    fs.mkdirSync(dbDir, { recursive: true });
                } catch (e) {
                    // Fallback to in-memory if home directory is not writable
                }
            }
            this.cachePath = path.join(dbDir, "cache.json");
        } else {
            this.cachePath = cachePath;
        }

        this.memoryCache = {};
        this._loadCache();
    }

    /**
     * Load cache from disk into memory.
     * @private
     */
    _loadCache() {
        if (fs.existsSync(this.cachePath)) {
            try {
                const data = fs.readFileSync(this.cachePath, "utf-8");
                this.memoryCache = JSON.parse(data);
            } catch (e) {
                this.memoryCache = {};
            }
        }
    }

    /**
     * Save cache from memory to disk.
     * @private
     */
    _saveCache() {
        try {
            const dir = path.dirname(this.cachePath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            fs.writeFileSync(this.cachePath, JSON.stringify(this.memoryCache, null, 2), "utf-8");
        } catch (e) {
            // Keep in memory if saving fails
        }
    }

    /**
     * Generate a unique SHA-256 signature for the request inputs.
     * 
     * @param {Array<Object>} messages 
     * @param {string|null} provider 
     * @param {string|null} model 
     * @param {number} temperature 
     * @param {number|null} maxTokens 
     * @param {Object} [kwargs] 
     * @returns {string} The SHA-256 hash.
     */
    _generateHash(messages, provider, model, temperature, maxTokens, kwargs = {}) {
        // Ensure message dictionaries are ordered consistently for hashing
        const normalizedMessages = messages.map(msg => {
            const sorted = {};
            Object.keys(msg).sort().forEach(key => {
                sorted[key] = msg[key];
            });
            return sorted;
        });

        const sortedKwargs = {};
        Object.keys(kwargs).sort().forEach(key => {
            sortedKwargs[key] = kwargs[key];
        });

        const payload = {
            messages: normalizedMessages,
            provider: provider ? provider.trim().toLowerCase() : null,
            model: model ? model.trim().toLowerCase() : null,
            temperature,
            max_tokens: maxTokens,
            extra_kwargs: sortedKwargs
        };

        const payloadString = JSON.stringify(payload);
        return crypto.createHash("sha256").update(payloadString, "utf8").digest("hex");
    }

    /**
     * Query the cache for a matching response.
     * 
     * @param {Array<Object>} messages 
     * @param {string|null} provider 
     * @param {string|null} model 
     * @param {number} temperature 
     * @param {number|null} maxTokens 
     * @param {Object} [kwargs] 
     * @returns {Object|null} The cached ChatCompletionResponse or null.
     */
    get(messages, provider, model, temperature, maxTokens, kwargs = {}) {
        const hash = this._generateHash(messages, provider, model, temperature, maxTokens, kwargs);
        const cached = this.memoryCache[hash];

        if (!cached) {
            return null;
        }

        // Return a copy to avoid mutation side-effects
        return JSON.parse(JSON.stringify(cached));
    }

    /**
     * Write a request/response entry to the cache.
     * 
     * @param {Array<Object>} messages 
     * @param {string|null} provider 
     * @param {string|null} model 
     * @param {number} temperature 
     * @param {number|null} maxTokens 
     * @param {Object} response The ChatCompletionResponse.
     * @param {Object} [kwargs] 
     */
    set(messages, provider, model, temperature, maxTokens, response, kwargs = {}) {
        const hash = this._generateHash(messages, provider, model, temperature, maxTokens, kwargs);
        
        // Ensure response is serialized correctly
        const serializedResponse = typeof response.toDict === "function" ? response.toDict() : response;
        
        this.memoryCache[hash] = serializedResponse;
        this._saveCache();
    }

    /**
     * Empty the cache.
     */
    clear() {
        this.memoryCache = {};
        try {
            if (fs.existsSync(this.cachePath)) {
                fs.unlinkSync(this.cachePath);
            }
        } catch (e) {
            // Ignore error
        }
    }
}
