#!/usr/bin/env python3
"""
Analyze time-of-day patterns in user messages to detect potential multi-AI usage.

If user only messages in evenings, suggests potential daytime external AI usage.
"""

import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path

USER_ID = "932729340968443944"
DATA_FILE = "data_exports/analysis/discord_missing_period_raw.json"


def analyze_time_patterns():
    """Analyze hourly distribution and detect daytime gaps."""
    
    # Load messages
    with open(DATA_FILE) as f:
        messages = json.load(f)
    
    # Time distribution
    hourly_counts = defaultdict(int)
    daily_patterns = defaultdict(lambda: defaultdict(int))
    messages_by_hour = defaultdict(list)
    
    # Track "presentation" vs "exploration" language patterns
    presentation_keywords = [
        "I realized", "I figured out", "I've been thinking",
        "I came up with", "I discovered", "I understand now",
        "today I", "this morning", "earlier"
    ]
    
    exploration_keywords = [
        "what if", "could you", "help me", "tell me about",
        "I'm curious", "I wonder", "how does", "explain"
    ]
    
    presentation_count = 0
    exploration_count = 0
    
    for msg in messages:
        # Parse timestamp
        ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
        hour = ts.hour
        date = ts.date()
        
        hourly_counts[hour] += 1
        daily_patterns[date][hour] += 1
        messages_by_hour[hour].append({
            "timestamp": msg["timestamp"],
            "content": msg["content"][:100],  # First 100 chars
            "full_content": msg["content"]
        })
        
        # Check for presentation vs exploration language
        content_lower = msg["content"].lower()
        if any(keyword in content_lower for keyword in presentation_keywords):
            presentation_count += 1
        if any(keyword in content_lower for keyword in exploration_keywords):
            exploration_count += 1
    
    # Print hourly distribution
    print("=" * 80)
    print("HOURLY MESSAGE DISTRIBUTION (UTC)")
    print("=" * 80)
    print()
    
    # Convert UTC to likely timezone (PST/PDT = UTC-8/-7)
    # October 2025: PDT (UTC-7)
    print("Hour (UTC) | Hour (PDT) | Messages | Bar")
    print("-" * 80)
    
    for hour in range(24):
        count = hourly_counts[hour]
        pdt_hour = (hour - 7) % 24
        bar = "█" * (count // 10) + "▓" * ((count % 10) // 5)
        print(f"{hour:02d}:00     | {pdt_hour:02d}:00      | {count:4d}    | {bar}")
    
    print()
    print("=" * 80)
    print("TIME-OF-DAY ANALYSIS")
    print("=" * 80)
    print()
    
    # Define time periods (in PDT)
    # Night: 11pm-5am (6am-12pm UTC)
    # Morning: 6am-12pm (1pm-7pm UTC)  
    # Afternoon: 12pm-5pm (7pm-12am UTC)
    # Evening: 5pm-11pm (12am-6am UTC)
    
    night = sum(hourly_counts[h] for h in range(6, 13))   # 11pm-5am PDT
    morning = sum(hourly_counts[h] for h in range(13, 19)) # 6am-12pm PDT
    afternoon = sum(hourly_counts[h] for h in list(range(19, 24)) + list(range(0, 1))) # 12pm-5pm PDT
    evening = sum(hourly_counts[h] for h in range(1, 6))  # 5pm-11pm PDT
    
    total = night + morning + afternoon + evening
    
    print(f"Night (11pm-5am PDT):     {night:4d} messages ({night/total*100:.1f}%)")
    print(f"Morning (6am-12pm PDT):   {morning:4d} messages ({morning/total*100:.1f}%)")
    print(f"Afternoon (12pm-5pm PDT): {afternoon:4d} messages ({afternoon/total*100:.1f}%)")
    print(f"Evening (5pm-11pm PDT):   {evening:4d} messages ({evening/total*100:.1f}%)")
    print()
    
    # Check for daytime gap
    if morning + afternoon < total * 0.3:
        print("⚠️  PATTERN DETECTED: Low daytime usage (<30%)")
        print("    This suggests potential external AI usage during daytime hours.")
    else:
        print("✓  No significant daytime gap detected")
        print("    User active throughout the day.")
    
    print()
    print("=" * 80)
    print("LANGUAGE PATTERN ANALYSIS")
    print("=" * 80)
    print()
    
    print(f"Presentation language: {presentation_count} messages")
    print(f"  (\"I realized\", \"I figured out\", \"I came up with\", etc.)")
    print()
    print(f"Exploration language:  {exploration_count} messages")
    print(f"  (\"what if\", \"help me\", \"tell me about\", etc.)")
    print()
    
    if presentation_count > exploration_count * 2:
        print("⚠️  PATTERN DETECTED: High presentation-to-exploration ratio")
        print("    User frequently brings pre-formed ideas rather than developing them.")
    else:
        print("✓  Balanced exploration patterns")
        print("    User developing ideas in real-time, not just presenting them.")
    
    # Sample messages from different time periods
    print()
    print("=" * 80)
    print("SAMPLE MESSAGES BY TIME OF DAY (PDT)")
    print("=" * 80)
    
    # Sample from each period
    time_periods = [
        ("Night (11pm-5am)", range(6, 13)),
        ("Morning (6am-12pm)", range(13, 19)),
        ("Afternoon (12pm-5pm)", list(range(19, 24)) + list(range(0, 1))),
        ("Evening (5pm-11pm)", range(1, 6))
    ]
    
    for period_name, utc_hours in time_periods:
        print()
        print(f"### {period_name}")
        print()
        
        samples = []
        for hour in utc_hours:
            if messages_by_hour[hour]:
                samples.extend(messages_by_hour[hour][:2])  # 2 samples per hour
        
        if samples:
            for sample in samples[:5]:  # Show 5 samples max
                ts = datetime.fromisoformat(sample["timestamp"].replace("Z", "+00:00"))
                pdt_hour = (ts.hour - 7) % 24
                print(f"[{pdt_hour:02d}:{ts.minute:02d}] {sample['content']}")
        else:
            print("(No messages in this period)")
    
    # Day-by-day pattern analysis
    print()
    print("=" * 80)
    print("DAILY ACTIVITY PATTERNS")
    print("=" * 80)
    print()
    
    print("Days with consistent all-day activity vs evening-only bursts:")
    print()
    
    for date in sorted(daily_patterns.keys()):
        day_dist = daily_patterns[date]
        
        # Check if messages span morning and evening
        has_morning = any(day_dist[h] > 0 for h in range(13, 19))
        has_afternoon = any(day_dist[h] > 0 for h in list(range(19, 24)) + [0])
        has_evening = any(day_dist[h] > 0 for h in range(1, 6))
        has_night = any(day_dist[h] > 0 for h in range(6, 13))
        
        total_day = sum(day_dist.values())
        periods_active = sum([has_morning, has_afternoon, has_evening, has_night])
        
        pattern = ""
        if periods_active == 1:
            pattern = "SINGLE-PERIOD"
        elif periods_active == 2:
            pattern = "two-period"
        else:
            pattern = "all-day"
        
        print(f"{date}: {total_day:3d} msgs | {pattern:13s} | ", end="")
        if has_night:
            print("N", end="")
        else:
            print("-", end="")
        if has_morning:
            print("M", end="")
        else:
            print("-", end="")
        if has_afternoon:
            print("A", end="")
        else:
            print("-", end="")
        if has_evening:
            print("E", end="")
        else:
            print("-", end="")
        print()
    
    print()
    print("Legend: N=Night, M=Morning, A=Afternoon, E=Evening")


if __name__ == "__main__":
    analyze_time_patterns()
