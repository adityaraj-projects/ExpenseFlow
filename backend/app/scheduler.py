"""
ExpenseFlow - Standalone Background Scheduler Worker / Cron Entry Point
Runs idempotent background checks:
- Due Reminders notification & rollover
- Due Recurring Transactions generation
- Monthly Budget 80% & 100% threshold alerts
- Savings Goals deadlines & milestones

Usage:
    One-shot (Cron Job):
        python -m app.scheduler

    Continuous Daemon Worker:
        python -m app.scheduler --loop --interval 3600
"""
import sys
import time
import argparse
from datetime import datetime
from app.database.connection import SessionLocal
from app.services.scheduler_service import SchedulerService


def run_scheduled_job():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running ExpenseFlow scheduler pass...")
    db = SessionLocal()
    try:
        results = SchedulerService.process_all_scheduled_events(db)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduler finished:")
        print(f"  - Reminders notified: {results['reminders_notified']}")
        print(f"  - Recurring generated: {results['recurring_generated']}")
        print(f"  - Budget alerts: {results['budget_alerts']}")
        print(f"  - Goal alerts: {results['goal_alerts']}")
    except Exception as e:
        print(f"[Scheduler Error] Exception during execution: {e}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="ExpenseFlow Scheduler Worker")
    parser.add_argument("--loop", action="store_true", help="Run in continuous daemon loop mode")
    parser.add_argument("--interval", type=int, default=3600, help="Interval in seconds for daemon mode (default 3600s)")
    args = parser.parse_args()

    if args.loop:
        print(f"Starting ExpenseFlow scheduler daemon (interval: {args.interval}s)... Press Ctrl+C to stop.")
        while True:
            run_scheduled_job()
            time.sleep(args.interval)
    else:
        run_scheduled_job()


if __name__ == "__main__":
    main()
