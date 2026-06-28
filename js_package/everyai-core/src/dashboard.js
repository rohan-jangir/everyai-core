import http from "http";
import { exec } from "child_process";
import os from "os";
import { UsageTracker } from "./tracker.js";

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EveryAI Telemetry Dashboard</title>
    <!-- Tailwind CSS for modern layout -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js for graphs -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Google Fonts Inter & Outfit -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        outfit: ['Outfit', 'sans-serif'],
                    },
                }
            }
        }
    </script>
    <style>
        /* Custom scrollbars and styling */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: #0f172a;
        }
        ::-webkit-scrollbar-thumb {
            background: #1e293b;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #334155;
        }
        .glass-card {
            background: rgba(21, 28, 44, 0.4);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
</head>
<body class="h-full bg-[#0a0f1d] text-slate-100 flex flex-col font-sans overflow-x-hidden antialiased">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800/80 bg-[#0f172a]/60 backdrop-blur-md sticky top-0 z-40 px-8 py-5 flex items-center justify-between">
        <div class="flex items-center space-x-3">
            <!-- Sleek Tech Icon -->
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-500 via-teal-400 to-emerald-500 flex items-center justify-center shadow-lg shadow-teal-500/10">
                <span class="text-slate-900 font-extrabold text-xl font-outfit">∀</span>
            </div>
            <div>
                <h1 class="text-lg font-bold font-outfit tracking-tight bg-gradient-to-r from-blue-400 via-teal-400 to-emerald-400 bg-clip-text text-transparent">EveryAI Telemetry</h1>
                <p class="text-[11px] text-slate-400 uppercase tracking-widest font-semibold">Real-time Performance & Fallback Analyzer</p>
            </div>
        </div>

        <div class="flex items-center space-x-3">
            <button onclick="fetchData()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700/80 active:scale-95 border border-slate-700/80 rounded-lg text-xs font-semibold tracking-wider uppercase transition flex items-center space-x-2">
                <svg class="w-3.5 h-3.5 text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3 3L22 4"></path>
                </svg>
                <span>Refresh</span>
            </button>
            <button onclick="confirmClearLogs()" class="px-4 py-2 bg-rose-500/10 hover:bg-rose-500 text-rose-400 hover:text-slate-950 border border-rose-500/20 active:scale-95 rounded-lg text-xs font-semibold tracking-wider uppercase transition">
                Truncate logs
            </button>
        </div>
    </header>

    <!-- Main Workspace Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-8 space-y-8">

        <!-- Navigation Tabs -->
        <div class="flex space-x-8 border-b border-slate-800 pb-3">
            <button onclick="switchTab('overview')" id="tab-overview" class="text-sm font-semibold pb-2 border-b-2 border-teal-400 text-slate-100 transition duration-150">
                Performance Overview
            </button>
            <button onclick="switchTab('logs')" id="tab-logs" class="text-sm font-semibold pb-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition duration-150">
                Transaction Logs
            </button>
            <button onclick="switchTab('errors')" id="tab-errors" class="text-sm font-semibold pb-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition duration-150">
                Error Analysis
            </button>
        </div>

        <!-- Tab 1: OVERVIEW -->
        <div id="view-overview" class="space-y-8">
            
            <!-- Metrics Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-5">
                <!-- Stat 1: Total Requests -->
                <div class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Total Requests</span>
                    <div class="mt-4 flex items-baseline space-x-1.5">
                        <span id="stat-total-calls" class="text-3xl font-bold font-outfit text-white">0</span>
                    </div>
                </div>

                <!-- Stat 2: Cache Hits -->
                <div class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg border-l-2 border-emerald-500/40">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Cache Hits</span>
                    <div class="mt-4 flex items-baseline space-x-1.5">
                        <span id="stat-cache-hits" class="text-3xl font-bold font-outfit text-emerald-400">0</span>
                    </div>
                </div>

                <!-- Stat 3: Tokens Saved -->
                <div class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg border-l-2 border-teal-500/40">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tokens Saved</span>
                    <div class="mt-4 flex items-baseline space-x-1.5">
                        <span id="stat-tokens-saved" class="text-3xl font-bold font-outfit text-teal-400">0</span>
                    </div>
                </div>

                <!-- Stat 4: Tokens Consumed -->
                <div class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Total Tokens</span>
                    <div class="mt-4 flex items-baseline space-x-1.5">
                        <span id="stat-total-tokens" class="text-3xl font-bold font-outfit text-blue-400">0</span>
                    </div>
                </div>

                <!-- Stat 5: Token Split -->
                <div class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg col-span-1">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Token Split</span>
                    <div class="mt-3 space-y-1">
                        <div class="flex justify-between text-[10px] font-bold text-slate-400">
                            <span>In: <strong id="stat-prompt-tokens" class="text-slate-200">0</strong></span>
                            <span>Out: <strong id="stat-completion-tokens" class="text-slate-200">0</strong></span>
                        </div>
                        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden flex">
                            <div id="stat-prompt-bar" class="bg-blue-400 h-full" style="width: 50%"></div>
                            <div id="stat-completion-bar" class="bg-teal-400 h-full" style="width: 50%"></div>
                        </div>
                    </div>
                </div>

                <!-- Stat 6: Rate Limits -->
                <div id="stat-rate-limit-card" class="glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg transition-colors">
                    <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Rate Limits</span>
                    <div class="mt-4 flex items-baseline space-x-1.5">
                        <span id="stat-rate-limits" class="text-3xl font-bold font-outfit text-white">0</span>
                    </div>
                </div>
            </div>

            <!-- Visualization section -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Doughnut Chart: Requests by Provider -->
                <div class="glass-card rounded-xl p-6 flex flex-col shadow-lg">
                    <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Requests Breakdown</h3>
                    <div class="flex-1 flex items-center justify-center min-h-[220px]">
                        <canvas id="chart-requests" class="max-w-[220px] max-h-[220px]"></canvas>
                    </div>
                </div>

                <!-- Bar Chart: Token consumption by Provider -->
                <div class="lg:col-span-2 glass-card rounded-xl p-6 flex flex-col shadow-lg">
                    <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Token Consumption Breakdown</h3>
                    <div class="flex-1 min-h-[220px]">
                        <canvas id="chart-tokens"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Quick View Table -->
            <div class="glass-card rounded-xl p-6 shadow-lg">
                <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Recent Transactions</h3>
                <div class="overflow-x-auto rounded-lg border border-slate-800 bg-[#0d1222]/40">
                    <table class="min-w-full divide-y divide-slate-800/80 text-left text-xs">
                        <thead class="bg-slate-900/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                            <tr>
                                <th class="px-6 py-4">Timestamp</th>
                                <th class="px-6 py-4">Provider</th>
                                <th class="px-6 py-4">Model</th>
                                <th class="px-6 py-4">Status</th>
                                <th class="px-6 py-4 text-right">Prompt</th>
                                <th class="px-6 py-4 text-right">Completion</th>
                                <th class="px-6 py-4 text-right">Total Tokens</th>
                            </tr>
                        </thead>
                        <tbody id="overview-table-body" class="divide-y divide-slate-800/50 text-slate-300">
                            <!-- Rows loaded dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 2: FULL LOGS VIEW -->
        <div id="view-logs" class="hidden space-y-6">
            <div class="glass-card rounded-xl p-6 shadow-lg">
                <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Transaction History Log</h3>
                    <p class="text-[10px] text-slate-400 tracking-wider">Showing up to 200 items</p>
                </div>
                <div class="overflow-x-auto rounded-lg border border-slate-800 bg-[#0d1222]/40">
                    <table class="min-w-full divide-y divide-slate-800/80 text-left text-xs">
                        <thead class="bg-slate-900/60 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                            <tr>
                                <th class="px-6 py-4">Timestamp</th>
                                <th class="px-6 py-4">Provider</th>
                                <th class="px-6 py-4">Model</th>
                                <th class="px-6 py-4">Status</th>
                                <th class="px-6 py-4 text-right">Prompt</th>
                                <th class="px-6 py-4 text-right">Completion</th>
                                <th class="px-6 py-4 text-right">Total</th>
                                <th class="px-6 py-4 text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body" class="divide-y divide-slate-800/50 text-slate-300">
                            <!-- Loaded dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 3: ERRORS VIEW -->
        <div id="view-errors" class="hidden space-y-6">
            <div class="glass-card rounded-xl p-6 shadow-lg">
                <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">Incident Log Reports</h3>
                <div class="space-y-4" id="errors-container">
                    <!-- Loaded dynamically -->
                </div>
            </div>
        </div>

    </main>

    <!-- Overlay Modal for Error Details -->
    <div id="modal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center hidden px-4">
        <div class="bg-[#111827] border border-slate-800 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="text-sm font-bold text-rose-400 uppercase tracking-wider" id="modal-title">Exception details</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-slate-200 font-bold text-lg">&times;</button>
            </div>
            <div>
                <p class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Error Traceback</p>
                <pre class="mt-2 p-4 bg-slate-950/80 rounded-xl text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-[350px]" id="modal-content"></pre>
            </div>
            <div class="flex justify-end pt-3">
                <button onclick="closeModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold uppercase tracking-wider rounded-lg transition">Dismiss</button>
            </div>
        </div>
    </div>

    <!-- JS Logic -->
    <script>
        let summaryData = {};
        let logRows = [];
        let requestsChart = null;
        let tokensChart = null;
        let errorCache = {};

        // Provider brand identities
        const providerColors = {
            "groq": "#f59e0b",         // Amber
            "openrouter": "#ec4899",   // Pink
            "huggingface": "#eab308",   // Yellow
            "cerebras": "#06b6d4",     // Teal
            "mistral": "#f97316",      // Orange
            "cloudflare": "#ea580c",   // Cloudflare Orange
            "nvidia": "#76b900"        // Nvidia Green
        };

        const defaultColors = ["#3b82f6", "#10b981", "#8b5cf6", "#319795", "#6366f1"];

        document.addEventListener("DOMContentLoaded", () => {
            fetchData();
        });

        function switchTab(tabId) {
            const tabs = ["overview", "logs", "errors"];
            tabs.forEach(t => {
                const btn = document.getElementById("tab-" + t);
                const view = document.getElementById("view-" + t);
                if (t === tabId) {
                    btn.className = "text-sm font-semibold pb-2 border-b-2 border-teal-400 text-slate-100 transition duration-150";
                    view.classList.remove("hidden");
                } else {
                    btn.className = "text-sm font-semibold pb-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200 transition duration-150";
                    view.classList.add("hidden");
                }
            });
        }

        async function fetchData() {
            try {
                const [summaryRes, logsRes] = await Promise.all([
                    fetch("/api/summary"),
                    fetch("/api/logs")
                ]);
                
                summaryData = await summaryRes.json();
                logRows = await logsRes.json();

                updateStats();
                updateCharts();
                updateTables();
                updateErrors();
            } catch (err) {
                console.error("Error loading telemetry data", err);
            }
        }

        function updateStats() {
            document.getElementById("stat-total-calls").innerText = (summaryData.total_calls || 0).toLocaleString();
            document.getElementById("stat-cache-hits").innerText = (summaryData.cache_hits_total || 0).toLocaleString();
            document.getElementById("stat-tokens-saved").innerText = (summaryData.tokens_saved_total || 0).toLocaleString();
            document.getElementById("stat-total-tokens").innerText = (summaryData.total_tokens || 0).toLocaleString();
            document.getElementById("stat-prompt-tokens").innerText = (summaryData.total_prompt_tokens || 0).toLocaleString();
            document.getElementById("stat-completion-tokens").innerText = (summaryData.total_completion_tokens || 0).toLocaleString();
            document.getElementById("stat-rate-limits").innerText = (summaryData.rate_limits_total || 0).toLocaleString();

            const rlCard = document.getElementById("stat-rate-limit-card");
            const rlText = document.getElementById("stat-rate-limits");
            if (summaryData.rate_limits_total > 0) {
                rlCard.className = "glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg border-l-2 border-rose-500";
                rlText.className = "text-3xl font-bold font-outfit text-rose-500 animate-pulse";
            } else {
                rlCard.className = "glass-card rounded-xl p-5 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between shadow-lg";
                rlText.className = "text-3xl font-bold font-outfit text-white";
            }

            const promptPct = summaryData.total_tokens > 0 ? (summaryData.total_prompt_tokens / summaryData.total_tokens) * 100 : 50;
            const compPct = 100 - promptPct;
            document.getElementById("stat-prompt-bar").style.width = promptPct + "%";
            document.getElementById("stat-completion-bar").style.width = compPct + "%";
        }

        function updateCharts() {
            const providerNames = Object.keys(summaryData.by_provider || {});
            const callCounts = providerNames.map(name => summaryData.by_provider[name].calls);

            if (requestsChart) requestsChart.destroy();
            
            const ctxReq = document.getElementById("chart-requests").getContext("2d");
            if (providerNames.length === 0) {
                requestsChart = new Chart(ctxReq, {
                    type: 'doughnut',
                    data: {
                        labels: ['No Data'],
                        datasets: [{
                            data: [1],
                            backgroundColor: ['#1e293b'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } }
                    }
                });
            } else {
                // Map colors matching brand guidelines dynamically
                const colors = providerNames.map((name, i) => providerColors[name.toLowerCase()] || defaultColors[i % defaultColors.length]);

                requestsChart = new Chart(ctxReq, {
                    type: 'doughnut',
                    data: {
                        labels: providerNames.map(p => p.toUpperCase()),
                        datasets: [{
                            data: callCounts,
                            backgroundColor: colors,
                            borderWidth: 1,
                            borderColor: '#0f172a'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 } }
                            }
                        }
                    }
                });
            }

            // 2. Bar Chart
            const promptTokens = providerNames.map(name => summaryData.by_provider[name].prompt_tokens);
            const completionTokens = providerNames.map(name => summaryData.by_provider[name].completion_tokens);

            if (tokensChart) tokensChart.destroy();
            const ctxTok = document.getElementById("chart-tokens").getContext("2d");
            tokensChart = new Chart(ctxTok, {
                type: 'bar',
                data: {
                    labels: providerNames.map(p => p.toUpperCase()),
                    datasets: [
                        {
                            label: 'Prompt (Input)',
                            data: promptTokens,
                            backgroundColor: '#3b82f6',
                            borderRadius: 4
                        },
                        {
                            label: 'Completion (Output)',
                            data: completionTokens,
                            backgroundColor: '#10b981',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            stacked: true,
                            grid: { display: false },
                            ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                        },
                        y: {
                            stacked: true,
                            grid: { color: '#1e293b' },
                            ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { color: '#94a3b8', font: { family: 'Inter', size: 10 } }
                        }
                    }
                }
            });
        }

        function updateTables() {
            const overBody = document.getElementById("overview-table-body");
            overBody.innerHTML = "";
            const recent = logRows.slice(0, 5);
            
            if (recent.length === 0) {
                overBody.innerHTML = '<tr><td colspan="7" class="px-6 py-8 text-center text-slate-500 font-semibold">No requests logged yet. Hit an API to see details here!</td></tr>';
            } else {
                recent.forEach(row => {
                    overBody.appendChild(createTableRow(row, false));
                });
            }

            const logsBody = document.getElementById("logs-table-body");
            logsBody.innerHTML = "";
            if (logRows.length === 0) {
                logsBody.innerHTML = '<tr><td colspan="8" class="px-6 py-8 text-center text-slate-500 font-semibold">No request event history found.</td></tr>';
            } else {
                logRows.forEach(row => {
                    logsBody.appendChild(createTableRow(row, true));
                });
            }
        }

        function createTableRow(row, showMetaColumn) {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-900/30 transition-colors";

            let statusBadge = "";
            if (row.status === "success") {
                statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Success</span>';
            } else if (row.status === "rate_limit") {
                statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-pulse">Rate Limit</span>';
            } else if (row.status === "auth_error") {
                statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">Auth Error</span>';
            } else if (row.status === "cache_hit") {
                statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">Cache Hit</span>';
            } else {
                statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-600/20">Error</span>';
            }

            const promptVal = row.prompt_tokens !== null ? row.prompt_tokens.toLocaleString() : "-";
            const compVal = row.completion_tokens !== null ? row.completion_tokens.toLocaleString() : "-";
            const totVal = row.total_tokens !== null ? row.total_tokens.toLocaleString() : "-";
            
            const timeStr = row.timestamp.replace("T", " ").split(".")[0];

            let html = 
                '<td class="px-6 py-4 font-mono text-[11px] text-slate-400 whitespace-nowrap">' + timeStr + '</td>' +
                '<td class="px-6 py-4 font-bold text-slate-100 whitespace-nowrap">' + row.provider.toUpperCase() + '</td>' +
                '<td class="px-6 py-4 text-slate-300 whitespace-nowrap">' + row.model + '</td>' +
                '<td class="px-6 py-4 whitespace-nowrap">' + statusBadge + '</td>' +
                '<td class="px-6 py-4 text-right font-mono text-[11px] text-slate-400">' + promptVal + '</td>' +
                '<td class="px-6 py-4 text-right font-mono text-[11px] text-slate-400">' + compVal + '</td>' +
                '<td class="px-6 py-4 text-right font-mono text-xs text-blue-400 font-semibold">' + totVal + '</td>';

            if (showMetaColumn) {
                let actionBtn = "-";
                if (row.error_message) {
                    errorCache[row.id] = row.error_message;
                    actionBtn = '<button onclick="showErrorModalById(' + row.id + ', \'' + row.status.toUpperCase() + '\')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-teal-400 text-[10px] font-semibold rounded border border-slate-700 transition active:scale-95">Show Error</button>';
                }
                html += '<td class="px-6 py-4 text-center whitespace-nowrap">' + actionBtn + '</td>';
            }

            tr.innerHTML = html;
            return tr;
        }

        function updateErrors() {
            const container = document.getElementById("errors-container");
            container.innerHTML = "";

            const errors = logRows.filter(r => r.status !== "success" && r.status !== "cache_hit");

            if (errors.length === 0) {
                container.innerHTML = 
                    '<div class="p-8 text-center text-slate-500 font-semibold border border-dashed border-slate-800 rounded-xl bg-slate-950/20">' +
                        'Zero incident reports logged. Excellent API health!' +
                    '</div>';
                return;
            }

            errors.forEach(err => {
                const card = document.createElement("div");
                card.className = "flex items-center justify-between p-4 bg-slate-900/40 border border-slate-800 rounded-xl gap-4 hover:border-slate-700/80 transition duration-300";
                
                let errorTitle = "";
                if (err.status === "rate_limit") {
                    errorTitle = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-500 border border-rose-500/20">RATE_LIMIT_ERROR</span>';
                } else if (err.status === "auth_error") {
                    errorTitle = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">AUTH_ERROR</span>';
                } else {
                    errorTitle = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-500/10 text-slate-400 border border-slate-600/20">PROVIDER_ERROR</span>';
                }

                errorCache[err.id] = err.error_message;

                card.innerHTML = 
                    '<div class="flex-1 space-y-1">' +
                        '<h4 class="text-xs font-semibold flex items-center">' + errorTitle + ' <span class="font-bold text-slate-200 ml-2">' + err.provider.toUpperCase() + '</span></h4>' +
                        '<p class="font-mono text-[10px] text-slate-400">Model: <code class="text-teal-400 font-medium">' + err.model + '</code> • ' + err.timestamp.replace("T", " ") + '</p>' +
                        '<div class="text-xs text-slate-300 font-mono mt-2 p-3 bg-slate-950/40 rounded-lg border border-slate-800 max-h-[80px] overflow-hidden text-ellipsis whitespace-nowrap">' + escapeHtml(err.error_message) + '</div>' +
                    '</div>' +
                    '<div>' +
                        '<button onclick="showErrorModalById(' + err.id + ', \'' + err.status.toUpperCase() + '\')" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-[10px] font-semibold text-slate-300 transition whitespace-nowrap">Log Trace</button>' +
                    '</div>';
                container.appendChild(card);
            });
        }

        function showErrorModalById(id, title) {
            const text = errorCache[id] || "";
            showErrorModal(title, text);
        }

        function showErrorModal(title, text) {
            document.getElementById("modal-title").innerText = title + " DETAILS";
            document.getElementById("modal-content").innerText = text;
            document.getElementById("modal").classList.remove("hidden");
        }

        function closeModal() {
            document.getElementById("modal").classList.add("hidden");
        }

        async function confirmClearLogs() {
            if (confirm("Are you sure you want to permanently clear all usage and token logs?")) {
                try {
                    const res = await fetch("/api/clear", { method: "POST" });
                    if (res.ok) {
                        alert("Logs cleared successfully.");
                        fetchData();
                    }
                } catch (err) {
                    console.error("Error clearing logs", err);
                }
            }
        }

        function escapeHtml(str) {
            if (!str) return "";
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;")
                .replace(/\\x60/g, "\\\\x60")
                .replace(/\\\\n/g, " ");
        }
    </script>
</body>
</html>
`;

function launchBrowser(url) {
    const start = os.platform() === "darwin" ? "open" : os.platform() === "win32" ? "start" : "xdg-open";
    exec(`${start} ${url}`);
}

/**
 * Start the telemetry dashboard local HTTP server.
 * 
 * @param {number} [port] Local port to host the server.
 * @param {string|null} [dbPath] Path to the telemetry SQLite database / JSON file.
 */
export function startDashboard(port = 8080, dbPath = null) {
    const tracker = new UsageTracker(dbPath);

    const server = http.createServer((req, res) => {
        const url = new URL(req.url, `http://localhost:${port}`);

        if (req.method === "GET") {
            if (url.pathname === "/") {
                res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
                res.end(DASHBOARD_HTML);
            } else if (url.pathname === "/api/summary") {
                res.writeHead(200, { "Content-Type": "application/json" });
                res.end(JSON.stringify(tracker.getSummary()));
            } else if (url.pathname === "/api/logs") {
                res.writeHead(200, { "Content-Type": "application/json" });
                res.end(JSON.stringify(tracker.getLogs(200)));
            } else {
                res.writeHead(404, { "Content-Type": "text/plain" });
                res.end("Not Found");
            }
        } else if (req.method === "POST" && url.pathname === "/api/clear") {
            tracker.clearLogs();
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ status: "success" }));
        } else {
            res.writeHead(404, { "Content-Type": "text/plain" });
            res.end("Not Found");
        }
    });

    server.listen(port, () => {
        console.log(`\n=======================================================`);
        console.log(`Starting EveryAI Telemetry Dashboard`);
        console.log(`URL: http://localhost:${port}`);
        console.log(`Telemetry DB: ${tracker.dbPath}`);
        console.log(`=======================================================`);
        console.log(`Press Ctrl+C to stop the dashboard server.`);

        setTimeout(() => {
            try {
                launchBrowser(`http://localhost:${port}`);
            } catch (e) {
                // Ignore launch browser errors
            }
        }, 800);
    });

    // Handle standard server shutdown errors cleanly
    process.on("SIGINT", () => {
        console.log("\nStopping EveryAI dashboard server.");
        server.close();
        process.exit(0);
    });

    return server;
}

export const start_dashboard = startDashboard;
