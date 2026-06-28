/**
 * Helper to pause execution for a given number of milliseconds.
 * @param {number} ms 
 * @returns {Promise<void>}
 */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Locally tracks request history to govern and throttle API request rates.
 */
export class RateLimitGovernor {
    /**
     * @param {number|null} [maxRequestsPerMinute] Max requests allowed per 60-second window.
     * @param {number|null} [maxTokensPerMinute] Max tokens allowed per 60-second window.
     */
    constructor(maxRequestsPerMinute = null, maxTokensPerMinute = null) {
        this.maxRpm = maxRequestsPerMinute;
        this.maxTpm = maxTokensPerMinute;
        
        /** @type {Array<{timestamp: number, tokens: number}>} */
        this.history = [];
    }

    /**
     * Throttle execution by sleeping if sending the request would exceed configured limits.
     * 
     * @param {number} [estimatedTokens] Estimated count of tokens.
     * @returns {Promise<void>}
     */
    async throttleIfNeeded(estimatedTokens = 500) {
        if (!this.maxRpm && !this.maxTpm) {
            return;
        }

        while (true) {
            const currentTime = Date.now() / 1000;
            this._cleanOldRecords(currentTime);

            // Check if request count exceeds RPM threshold
            const rpmExceeded = this.maxRpm !== null && this.history.length >= this.maxRpm;

            // Check if token count exceeds TPM threshold
            const currentTokens = this.history.reduce((sum, item) => sum + item.tokens, 0);
            const tpmExceeded = this.maxTpm !== null && (currentTokens + estimatedTokens > this.maxTpm);

            if (!rpmExceeded && !tpmExceeded) {
                break;
            }

            // Calculate wait time until the oldest request falls out of the sliding window
            if (this.history.length > 0) {
                const oldestTime = this.history[0].timestamp;
                const sleepTime = (oldestTime + 60.0) - currentTime;
                if (sleepTime > 0) {
                    console.log(
                        `[EveryAI Governor] Approaching rate limits. ` +
                        `Throttling request, sleeping for ${sleepTime.toFixed(2)} seconds...`
                    );
                    await sleep(sleepTime * 1000);
                }
            } else {
                // Safeguard sleep to prevent CPU locks
                await sleep(500);
                break;
            }
        }
    }

    /**
     * Log a successful request in the governor's sliding window history.
     * 
     * @param {number} tokensUsed Exact count of prompt + completion tokens consumed.
     */
    recordRequest(tokensUsed) {
        if (!this.maxRpm && !this.maxTpm) {
            return;
        }
        this.history.push({
            timestamp: Date.now() / 1000,
            tokens: tokensUsed
        });
    }

    /**
     * Purge sliding-window requests older than 60 seconds.
     * 
     * @param {number} currentTime Current timestamp in seconds.
     * @private
     */
    _cleanOldRecords(currentTime) {
        const cutoff = currentTime - 60.0;
        while (this.history.length > 0 && this.history[0].timestamp <= cutoff) {
            this.history.shift();
        }
    }
}
