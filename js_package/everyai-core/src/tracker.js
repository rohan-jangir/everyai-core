import fs from "fs";
import path from "path";
import os from "os";

/**
 * Handles logging and queries for provider API telemetry.
 */
export class UsageTracker {
    /**
     * @param {string} [dbPath] Optional custom file path for the usage tracking database.
     */
    constructor(dbPath = null) {
        if (dbPath === null) {
            const dbDir = path.join(os.homedir(), ".everyai");
            if (!fs.existsSync(dbDir)) {
                try {
                    fs.mkdirSync(dbDir, { recursive: true });
                } catch (e) {
                    // Fallback to in-memory if home directory is not writable
                }
            }
            this.dbPath = path.join(dbDir, "usage.json");
        } else {
            this.dbPath = dbPath;
        }

        /** @type {Array<Object>} */
        this.logs = [];
        this._loadLogs();
    }

    /**
     * Load logs from disk.
     * @private
     */
    _loadLogs() {
        if (fs.existsSync(this.dbPath)) {
            try {
                const data = fs.readFileSync(this.dbPath, "utf-8");
                this.logs = JSON.parse(data);
            } catch (e) {
                this.logs = [];
            }
        }
    }

    /**
     * Save logs to disk.
     * @private
     */
    _saveLogs() {
        try {
            const dir = path.dirname(this.dbPath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            fs.writeFileSync(this.dbPath, JSON.stringify(this.logs, null, 2), "utf-8");
        } catch (e) {
            // Keep in memory if saving fails
        }
    }

    /**
     * Write a request log to the telemetry database.
     * 
     * @param {string} provider AI provider name (e.g. 'groq').
     * @param {string} model Model name.
     * @param {number|null} [promptTokens] Number of prompt/input tokens.
     * @param {number|null} [completionTokens] Number of completion/output tokens.
     * @param {string} [status] Call status ('success', 'rate_limit', 'auth_error', etc.).
     * @param {string|null} [errorMessage] Text details of any exception.
     */
    logCall(
        provider,
        model,
        promptTokens = null,
        completionTokens = null,
        status = "success",
        errorMessage = null
    ) {
        const pTok = promptTokens || 0;
        const cTok = completionTokens || 0;
        const tTok = pTok + cTok;

        const nextId = this.logs.length > 0 ? Math.max(...this.logs.map(l => typeof l.id === "number" ? l.id : 0)) + 1 : 1;
        const logEntry = {
            id: nextId,
            timestamp: new Date().toISOString(),
            provider: provider.trim().toLowerCase(),
            model,
            prompt_tokens: promptTokens,
            completion_tokens: completionTokens,
            total_tokens: (promptTokens !== null || completionTokens !== null) ? tTok : null,
            status,
            error_message: errorMessage
        };

        this.logs.push(logEntry);
        this._saveLogs();
    }

    /**
     * Aggregate tracking data across providers.
     * 
     * @returns {Object} A dictionary containing aggregated metrics.
     */
    getSummary() {
        const summary = {
            total_calls: 0,
            total_prompt_tokens: 0,
            total_completion_tokens: 0,
            total_tokens: 0,
            rate_limits_total: 0,
            cache_hits_total: 0,
            tokens_saved_total: 0,
            by_provider: {}
        };

        summary.total_calls = this.logs.length;

        for (const log of this.logs) {
            const p = log.prompt_tokens || 0;
            const c = log.completion_tokens || 0;
            const t = log.total_tokens || 0;

            summary.total_prompt_tokens += p;
            summary.total_completion_tokens += c;
            summary.total_tokens += t;

            if (log.status === "rate_limit") {
                summary.rate_limits_total += 1;
            }

            if (log.status === "cache_hit") {
                summary.cache_hits_total += 1;
                const saved = parseInt(log.error_message || "0", 10);
                summary.tokens_saved_total += isNaN(saved) ? 0 : saved;
            }

            const provider = log.provider;
            if (!summary.by_provider[provider]) {
                summary.by_provider[provider] = {
                    calls: 0,
                    prompt_tokens: 0,
                    completion_tokens: 0,
                    total_tokens: 0,
                    rate_limits: 0
                };
            }

            const pStats = summary.by_provider[provider];
            pStats.calls += 1;
            pStats.prompt_tokens += p;
            pStats.completion_tokens += c;
            pStats.total_tokens += t;
            if (log.status === "rate_limit") {
                pStats.rate_limits += 1;
            }
        }

        return summary;
    }

    /**
     * Fetch chronological log history.
     * 
     * @param {number} [limit] Maximum number of rows to return.
     * @returns {Array<Object>} Chronological logs list (newest first).
     */
    getLogs(limit = 100) {
        // Return a copy sorted newest first (timestamp DESC, id DESC)
        const sorted = [...this.logs].sort((a, b) => {
            const timeDiff = new Date(b.timestamp) - new Date(a.timestamp);
            if (timeDiff !== 0) return timeDiff;
            return b.id - a.id;
        });

        return sorted.slice(0, limit);
    }

    /**
     * Truncate the telemetry log table.
     */
    clearLogs() {
        this.logs = [];
        try {
            if (fs.existsSync(this.dbPath)) {
                fs.unlinkSync(this.dbPath);
            }
        } catch (e) {
            // Ignore error
        }
    }
}
