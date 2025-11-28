#!/usr/bin/env python3
"""
WhisperEngine Master Test Runner

Runs the full regression test suite across all bots with reporting.

Usage:
    # Run all tests
    python tests_v2/run_regression.py

    # Run for specific bot
    python tests_v2/run_regression.py --bot elena

    # Run specific test category
    python tests_v2/run_regression.py --category health
    python tests_v2/run_regression.py --category chat
    python tests_v2/run_regression.py --category memory
    python tests_v2/run_regression.py --category conversation

    # Quick smoke test (health + basic chat only)
    python tests_v2/run_regression.py --smoke

    # Full test with HTML report
    python tests_v2/run_regression.py --report
"""

import argparse
import subprocess
import sys
import os
import time
import signal
from datetime import datetime
from pathlib import Path

# Try to import BOT_CONFIGS to get port numbers
try:
    sys.path.append(os.getcwd())
    from tests_v2.regression.test_regression_suite import BOT_CONFIGS
except ImportError:
    print("Warning: Could not import BOT_CONFIGS. Auto-start API might fail.")
    BOT_CONFIGS = []

# Test categories mapped to pytest markers/patterns
TEST_CATEGORIES = {
    "health": "TestHealthAndDiagnostics",
    "chat": "TestBasicChat",
    "character": "TestCharacterConsistency",
    "memory": "TestMemoryAndState",
    "conversation": "TestMultiTurnConversation",
    "complexity": "TestComplexityRouting",
    "comparison": "TestModelComparison",
    "production": "TestProductionBotStability",
}

# Bot names for filtering
BOTS = ["elena", "ryan", "dotty", "aria", "dream", "jake", "sophia", "marcus", "nottaylor"]


def start_api_server(bot_name: str, port: int) -> subprocess.Popen:
    """Start the API server for a specific bot."""
    print(f"🚀 Starting API for {bot_name} on port {port}...")
    
    env = os.environ.copy()
    env["DISCORD_BOT_NAME"] = bot_name
    env["API_PORT"] = str(port)
    
    # Start uvicorn process
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", 
            "src_v2.api.app:app", 
            "--host", "0.0.0.0", 
            "--port", str(port),
            "--workers", "1"
        ],
        env=env,
        stdout=subprocess.DEVNULL,  # Suppress stdout to keep test output clean
        stderr=subprocess.PIPE      # Capture stderr for errors
    )
    
    # Wait for startup (simple sleep for now, could be health check)
    time.sleep(3)
    
    if process.poll() is not None:
        print(f"❌ API failed to start for {bot_name}")
        stderr = process.stderr.read().decode()
        print(stderr)
        sys.exit(1)
        
    print(f"✅ API started (PID: {process.pid})")
    return process


def run_tests(
    bot: str | None = None,
    category: str | None = None,
    smoke: bool = False,
    report: bool = False,
    verbose: bool = True,
    no_cov: bool = True,
    auto_start: bool = False
) -> int:
    """Run the regression test suite."""
    
    api_process = None
    
    try:
        # Auto-start API logic
        if auto_start:
            if not bot:
                # If no bot specified, we need to run sequentially for ALL bots
                # This is a recursive call strategy
                print("🔄 Running sequential tests for ALL bots with auto-start...")
                overall_exit_code = 0
                
                for bot_config in BOT_CONFIGS:
                    print(f"\n\n>>> TEST RUN: {bot_config.name} <<<")
                    code = run_tests(
                        bot=bot_config.name,
                        category=category,
                        smoke=smoke,
                        report=report,
                        verbose=verbose,
                        no_cov=no_cov,
                        auto_start=True
                    )
                    if code != 0:
                        overall_exit_code = code
                        # Continue or stop? Let's continue to see all failures
                
                return overall_exit_code
            
            else:
                # Find port for this bot
                config = next((b for b in BOT_CONFIGS if b.name == bot), None)
                if not config:
                    print(f"❌ Configuration not found for bot: {bot}")
                    return 1
                
                api_process = start_api_server(bot, config.port)

    
        # Base pytest command
        cmd = ["pytest", "tests_v2/regression/", "-v"]
        
        if no_cov:
            cmd.append("--no-cov")
        
        if verbose:
            cmd.append("-s")
        
        # Filter by bot
        if bot:
            if bot not in BOTS:
                print(f"Unknown bot: {bot}")
                print(f"Available: {BOTS}")
                return 1
            cmd.extend(["-k", bot])
        
        # Filter by category
        if category:
            if category not in TEST_CATEGORIES:
                print(f"Unknown category: {category}")
                print(f"Available: {list(TEST_CATEGORIES.keys())}")
                return 1
            cmd.extend(["-k", TEST_CATEGORIES[category]])
        
        # Smoke test - just health and basic chat
        if smoke:
            cmd.extend(["-k", "TestHealthAndDiagnostics or test_simple_greeting"])
        
        # Generate HTML report
        if report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = f"tests_v2/reports/regression_{timestamp}.html"
            os.makedirs("tests_v2/reports", exist_ok=True)
            cmd.extend(["--html", report_path, "--self-contained-html"])
            print(f"Report will be saved to: {report_path}")
        
        # Print command
        print(f"\n{'='*60}")
        print(f"Running: {' '.join(cmd)}")
        print(f"{'='*60}\n")
        
        # Run tests
        result = subprocess.run(cmd, check=False)
        
        return result.returncode

    finally:
        # Cleanup API process
        if api_process:
            print(f"🛑 Stopping API for {bot}...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
            print("✅ API stopped")


def main():
    parser = argparse.ArgumentParser(description="WhisperEngine Regression Test Runner")
    
    parser.add_argument(
        "--bot", "-b",
        choices=BOTS,
        help="Run tests for a specific bot only"
    )
    parser.add_argument(
        "--category", "-c",
        choices=list(TEST_CATEGORIES.keys()),
        help="Run tests for a specific category only"
    )
    parser.add_argument(
        "--smoke", "-s",
        action="store_true",
        help="Quick smoke test (health + basic chat)"
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Generate HTML report"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Less verbose output"
    )
    parser.add_argument(
        "--cov",
        action="store_true",
        help="Enable coverage (disabled by default for speed)"
    )
    parser.add_argument(
        "--auto-start-api",
        action="store_true",
        help="Automatically start/stop API server for tests (no Discord)"
    )
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("tests_v2").exists():
        print("Error: Run this from the whisperengine-v2 root directory")
        sys.exit(1)
    
    # Run tests
    exit_code = run_tests(
        bot=args.bot,
        category=args.category,
        smoke=args.smoke,
        report=args.report,
        verbose=not args.quiet,
        no_cov=not args.cov,
        auto_start=args.auto_start_api
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
