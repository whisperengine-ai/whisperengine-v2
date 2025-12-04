#!/usr/bin/env python3
"""
Hive Mind Dashboard (Phase E24)

CLI tool to visualize the state of the agentic queue system.
Shows pending jobs, active workers, and queue health.

Usage:
    python scripts/hive_mind.py
    python scripts/hive_mind.py --watch
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from arq import create_pool
from arq.connections import RedisSettings

# Add project root to path
sys.path.append(".")
from src_v2.config.settings import settings
from src_v2.workers.task_queue import TaskQueue

console = Console()

QUEUES = [
    TaskQueue.QUEUE_COGNITION,
    TaskQueue.QUEUE_SENSORY,
    TaskQueue.QUEUE_ACTION,
    TaskQueue.QUEUE_SOCIAL
]

QUEUE_DESCRIPTIONS = {
    TaskQueue.QUEUE_COGNITION: "🧠 Cognition (Deep Reasoning)",
    TaskQueue.QUEUE_SENSORY: "👁️ Sensory (Fast Analysis)",
    TaskQueue.QUEUE_ACTION: "⚡ Action (Outbound Effects)",
    TaskQueue.QUEUE_SOCIAL: "💬 Social (Inter-Agent)"
}

async def get_queue_stats(redis) -> List[Dict[str, Any]]:
    """Fetch stats for all queues."""
    stats = []
    
    for queue_name in QUEUES:
        # Get queued jobs
        job_ids = await redis.zrange(queue_name, 0, -1)
        count = len(job_ids)
        
        # Get jobs details (first 5)
        jobs = []
        for job_id in job_ids[:5]:
            # arq stores job details in a separate key
            # We can't easily get the function name without decoding the job definition
            # But we can list the ID
            jobs.append(job_id.decode() if isinstance(job_id, bytes) else job_id)
            
        stats.append({
            "name": queue_name,
            "description": QUEUE_DESCRIPTIONS.get(queue_name, queue_name),
            "count": count,
            "jobs": jobs
        })
        
    return stats

def create_dashboard(stats: List[Dict[str, Any]]) -> Table:
    """Create a rich table for the dashboard."""
    table = Table(title=f"Hive Mind Status - {datetime.now().strftime('%H:%M:%S')}")
    
    table.add_column("Queue", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Pending", justify="right", style="green")
    table.add_column("Next Jobs", style="dim")
    
    total_pending = 0
    
    for stat in stats:
        count = stat["count"]
        total_pending += count
        
        count_style = "green" if count < 10 else "yellow" if count < 50 else "red"
        
        jobs_str = ", ".join(stat["jobs"])
        if count > 5:
            jobs_str += f", ... (+{count-5})"
        if not jobs_str:
            jobs_str = "-"
            
        table.add_row(
            stat["name"],
            stat["description"],
            f"[{count_style}]{count}[/{count_style}]",
            jobs_str
        )
        
    return table

async def run_dashboard(watch: bool = False):
    """Run the dashboard."""
    redis_settings = TaskQueue.get_redis_settings()
    redis = await create_pool(redis_settings)
    
    try:
        if watch:
            with Live(refresh_per_second=1) as live:
                while True:
                    stats = await get_queue_stats(redis)
                    table = create_dashboard(stats)
                    live.update(table)
                    await asyncio.sleep(1)
        else:
            stats = await get_queue_stats(redis)
            table = create_dashboard(stats)
            console.print(table)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
    finally:
        await redis.aclose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hive Mind Dashboard")
    parser.add_argument("--watch", action="store_true", help="Watch queue status in real-time")
    args = parser.parse_args()
    
    asyncio.run(run_dashboard(args.watch))
