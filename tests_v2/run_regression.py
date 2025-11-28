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
from datetime import datetime
from pathlib import Path


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


def run_tests(
    bot: str | None = None,
    category: str | None = None,
    smoke: bool = False,
    report: bool = False,
    verbose: bool = True,
    no_cov: bool = True
) -> int:
    """Run the regression test suite."""
    
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
        no_cov=not args.cov
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
