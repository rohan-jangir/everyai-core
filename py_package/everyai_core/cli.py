"""Command-line Interface for everyai-core.

Provides shell operations like launching the dashboard server and printing or clearing logs.
"""

import argparse
import sys
from everyai_core.tracker import UsageTracker
from everyai_core.dashboard import start_dashboard


def main() -> None:
    """Entrypoint for the 'everyai' command line utility."""
    parser = argparse.ArgumentParser(description="EveryAI command-line utility tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Dashboard Command parser
    dash_parser = subparsers.add_parser("dashboard", help="Start the telemetry dashboard server.")
    dash_parser.add_argument(
        "--port", 
        type=int, 
        default=8080, 
        help="Local port to serve the dashboard web interface (default: 8080)."
    )
    dash_parser.add_argument(
        "--db", 
        type=str, 
        default=None, 
        help="Custom path to the telemetry SQLite database."
    )

    # Stats Command parser
    stats_parser = subparsers.add_parser("stats", help="Show summary details of token consumption.")
    stats_parser.add_argument(
        "--db", 
        type=str, 
        default=None, 
        help="Custom path to the telemetry SQLite database."
    )
    stats_parser.add_argument(
        "--clear", 
        action="store_true", 
        help="Permanently truncate all usage and error event logs."
    )

    args = parser.parse_args()

    if args.command == "dashboard":
        start_dashboard(port=args.port, db_path=args.db)

    elif args.command == "stats":
        tracker = UsageTracker(db_path=args.db)
        if args.clear:
            confirm = input("Are you sure you want to permanently clear all logs? [y/N]: ").strip().lower()
            if confirm in ("y", "yes"):
                tracker.clear_logs()
                print("Logs successfully cleared.")
            else:
                print("Operation aborted.")
        else:
            summary = tracker.get_summary()
            print("\n==============================================")
            print("EveryAI Token Telemetry Statistics")
            print("==============================================")
            print(f"Total Requests:         {summary['total_calls']}")
            print(f"Total Tokens:           {summary['total_tokens']}")
            print(f"Prompt (Input) Tokens:  {summary['total_prompt_tokens']}")
            print(f"Completion (Output):    {summary['total_completion_tokens']}")
            print(f"Rate Limit Blocks:      {summary['rate_limits_total']}")
            
            print("\nBreakdown by Provider:")
            if not summary["by_provider"]:
                print("  (No logs recorded yet)")
            else:
                for provider, stats in summary["by_provider"].items():
                    print(f"  - {provider.upper()}:")
                    print(f"      Calls: {stats['calls']}")
                    print(f"      Tokens: {stats['total_tokens']} (In: {stats['prompt_tokens']}, Out: {stats['completion_tokens']})")
                    print(f"      Rate Limits: {stats['rate_limits']}")
            print("==============================================\n")


if __name__ == "__main__":
    main()
