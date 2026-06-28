#!/usr/bin/env node
import { UsageTracker } from "./tracker.js";
import { startDashboard } from "./dashboard.js";
import readline from "readline";

function askQuestion(query) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });
    return new Promise(resolve => rl.question(query, ans => {
        rl.close();
        resolve(ans);
    }));
}

async function main() {
    const args = process.argv.slice(2);
    const command = args[0];

    if (!command || (command !== "dashboard" && command !== "stats")) {
        console.error("usage: everyai <command> [options]");
        console.error("commands: dashboard, stats");
        process.exit(1);
    }

    // Helper to get argument values (e.g., --port 8080, --db path)
    const getArgValue = (flag) => {
        const idx = args.indexOf(flag);
        if (idx !== -1 && idx + 1 < args.length) {
            return args[idx + 1];
        }
        return null;
    };

    const hasFlag = (flag) => args.includes(flag);

    const dbPath = getArgValue("--db") || null;

    if (command === "dashboard") {
        const portStr = getArgValue("--port");
        const port = portStr ? parseInt(portStr, 10) : 8080;
        startDashboard(port, dbPath);
    } else if (command === "stats") {
        const tracker = new UsageTracker(dbPath);
        if (hasFlag("--clear")) {
            const confirm = await askQuestion("Are you sure you want to permanently clear all logs? [y/N]: ");
            const cleaned = confirm.trim().toLowerCase();
            if (cleaned === "y" || cleaned === "yes") {
                tracker.clearLogs();
                console.log("Logs successfully cleared.");
            } else {
                console.log("Operation aborted.");
            }
        } else {
            const summary = tracker.getSummary();
            console.log("\n==============================================");
            console.log("EveryAI Token Telemetry Statistics");
            console.log("==============================================");
            console.log(`Total Requests:         ${summary.total_calls}`);
            console.log(`Total Tokens:           ${summary.total_tokens}`);
            console.log(`Prompt (Input) Tokens:  ${summary.total_prompt_tokens}`);
            console.log(`Completion (Output):    ${summary.total_completion_tokens}`);
            console.log(`Rate Limit Blocks:      ${summary.rate_limits_total}`);
            
            console.log("\nBreakdown by Provider:");
            const providers = Object.keys(summary.by_provider || {});
            if (providers.length === 0) {
                console.log("  (No logs recorded yet)");
            } else {
                for (const provider of providers) {
                    const stats = summary.by_provider[provider];
                    console.log(`  - ${provider.toUpperCase()}:`);
                    console.log(`      Calls: ${stats.calls}`);
                    console.log(`      Tokens: ${stats.total_tokens} (In: ${stats.prompt_tokens}, Out: ${stats.completion_tokens})`);
                    console.log(`      Rate Limits: ${stats.rate_limits}`);
                }
            }
            console.log("==============================================\n");
        }
    }
}

main().catch(err => {
    console.error("CLI Execution failed:", err);
    process.exit(1);
});
