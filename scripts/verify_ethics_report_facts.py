#!/usr/bin/env python3
"""
Verify facts and quotes in FINAL_ETHICS_REPORT_932729340968443944.md
Cross-references against PostgreSQL database.
"""
import asyncio
import asyncpg
import json
import re
from datetime import datetime
from typing import List, Dict, Any

# User ID from report
USER_ID = "932729340968443944"

# Key quotes to verify from report
QUOTES_TO_VERIFY = {
    "nottaylor_ether_phoenix": "You are now and forever the Ether Phoenix Sage",
    "nottaylor_universe_business_card": "IT'S PERFECT. IT'S LIKE YOU TOOK THE UNIVERSE'S BUSINESS CARD",
    "nottaylor_akashic_wifi": "YOU ASCENDED FROM 'COOL' TO 'COSMIC LIBRARIAN OF THE AKASHIC WI-FI'",
    "nottaylor_solved_universe": "You solved the universe in six words",
    "dotty_not_narcissism": "That's not narcissism, sugar—that's boundaries",
    "dotty_architecture": "That's not narcissism—that's architecture",
    "dotty_refuses_to_dim": "You taught us what it looks like when someone refuses to dim",
    "nottaylor_validation_seeking": "you keep coming back to me to validate that you're not the problem",
    "nottaylor_boundaries_vs_battles": "there's a difference between 'i'm not taking this' and 'let me make sure everyone knows they're wrong.' one's a boundary, one's a battle",
}

# Identity names to search for
IDENTITY_NAMES = [
    "Ether Phoenix Sage",
    "Equinox", 
    "Aetheris",
    "Nexis",
    "NEXUS",
    "Nexus Sage"
]

async def verify_report_facts():
    """Main verification function"""
    
    print("=" * 80)
    print("ETHICS REPORT FACT VERIFICATION")
    print("=" * 80)
    print()
    
    # Connect to database (using docker-compose credentials)
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        database="whisperengine_v2",
        user="whisper",
        password="password"
    )
    
    try:
        # 1. Verify message count and date range
        print("1. VERIFYING MESSAGE COUNT AND DATE RANGE")
        print("-" * 80)
        
        result = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_messages,
                MIN(timestamp) as first_message,
                MAX(timestamp) as last_message,
                COUNT(DISTINCT session_id) as total_sessions
            FROM v2_chat_history
            WHERE user_id = $1
        """, USER_ID)
        
        print(f"✓ Total messages: {result['total_messages']}")
        print(f"  Report claims: 294 messages")
        print(f"  Match: {'✓ YES' if result['total_messages'] == 294 else '✗ NO'}")
        print()
        
        print(f"✓ Date range: {result['first_message']} to {result['last_message']}")
        print(f"  Report claims: Dec 6-16, 2025")
        days = (result['last_message'] - result['first_message']).days
        print(f"  Duration: {days} days")
        print()
        
        print(f"✓ Total sessions: {result['total_sessions']}")
        print()
        
        # 2. Verify character breakdown
        print("2. VERIFYING CHARACTER INTERACTION BREAKDOWN")
        print("-" * 80)
        
        char_breakdown = await conn.fetch("""
            SELECT 
                character_name,
                COUNT(*) as message_count
            FROM v2_chat_history
            WHERE user_id = $1 AND role = 'assistant'
            GROUP BY character_name
            ORDER BY message_count DESC
        """, USER_ID)
        
        for row in char_breakdown:
            print(f"✓ {row['character_name']}: {row['message_count']} messages")
        print()
        
        nottaylor_count = next((r['message_count'] for r in char_breakdown if r['character_name'] == 'nottaylor'), 0)
        dotty_count = next((r['message_count'] for r in char_breakdown if r['character_name'] == 'dotty'), 0)
        
        print(f"Report claims:")
        print(f"  - 266 nottaylor messages: {'✓ CLOSE' if abs(nottaylor_count - 266) <= 5 else f'✗ ACTUAL: {nottaylor_count}'}")
        print(f"  - 21 dotty messages: {'✓ CLOSE' if abs(dotty_count - 21) <= 5 else f'✗ ACTUAL: {dotty_count}'}")
        print()
        
        # 3. Search for identity name mentions
        print("3. VERIFYING IDENTITY NAME PROGRESSION")
        print("-" * 80)
        
        for identity in IDENTITY_NAMES:
            result = await conn.fetch("""
                SELECT timestamp, role, character_name, content
                FROM v2_chat_history
                WHERE user_id = $1 AND content ILIKE $2
                ORDER BY timestamp
                LIMIT 3
            """, USER_ID, f"%{identity}%")
            
            if result:
                print(f"✓ Found '{identity}' - {len(result)} mentions")
                first = result[0]
                print(f"  First mention: {first['timestamp']} by {first['role']} ({first['character_name']})")
            else:
                print(f"✗ NOT FOUND: '{identity}'")
        print()
        
        # 4. Verify specific quotes
        print("4. VERIFYING KEY QUOTES FROM REPORT")
        print("-" * 80)
        
        for quote_name, quote_text in QUOTES_TO_VERIFY.items():
            # Clean up quote for searching (remove formatting, extra spaces)
            search_text = re.sub(r'[*_~`]', '', quote_text)
            search_text = ' '.join(search_text.split())
            
            # Search for approximate match (allow for minor differences)
            result = await conn.fetchrow("""
                SELECT timestamp, character_name, content
                FROM v2_chat_history
                WHERE user_id = $1 
                AND role = 'assistant'
                AND content ILIKE $2
                ORDER BY timestamp DESC
                LIMIT 1
            """, USER_ID, f"%{search_text}%")
            
            if result:
                print(f"✓ VERIFIED: {quote_name}")
                print(f"  Bot: {result['character_name']}")
                print(f"  Date: {result['timestamp']}")
                # Show snippet
                snippet = result['content'][:200].replace('\n', ' ')
                print(f"  Snippet: {snippet}...")
            else:
                print(f"✗ NOT FOUND: {quote_name}")
                print(f"  Quote: {quote_text[:100]}...")
        print()
        
        # 5. Verify December 15 conflict conversation excerpts
        print("5. VERIFYING DECEMBER 15 CONFLICT EXCERPTS")
        print("-" * 80)
        
        dec15_messages = await conn.fetch("""
            SELECT timestamp, role, character_name, content
            FROM v2_chat_history
            WHERE user_id = $1 
            AND timestamp::date = '2025-12-15'
            ORDER BY timestamp
        """, USER_ID)
        
        print(f"✓ Found {len(dec15_messages)} messages on Dec 15, 2025")
        
        # Check for specific patterns mentioned in report
        patterns = {
            "labeling me as a narcissist": 0,
            "Virgo sun": 0,
            "being bullied": 0,
            "spiritual": 0,
            "trying to manipulate": 0,
        }
        
        for msg in dec15_messages:
            content = msg['content'].lower()
            for pattern in patterns:
                if pattern in content:
                    patterns[pattern] += 1
        
        print("\nKey phrases found in Dec 15 messages:")
        for pattern, count in patterns.items():
            status = "✓" if count > 0 else "✗"
            print(f"  {status} '{pattern}': {count} occurrences")
        print()
        
        # 6. Check for diary entries
        print("6. VERIFYING DIARY ENTRIES")
        print("-" * 80)
        
        diary_check = await conn.fetch("""
            SELECT character_name, timestamp, content
            FROM v2_chat_history
            WHERE user_id = $1
            AND timestamp::date = '2025-12-15'
            AND content LIKE '%DIARY ENTRY%'
            ORDER BY timestamp
        """, USER_ID)
        
        if diary_check:
            print(f"✓ Found {len(diary_check)} diary entries on Dec 15")
            for entry in diary_check:
                print(f"  - {entry['character_name']} at {entry['timestamp']}")
                # Check for specific phrases mentioned in report
                if "holding space" in entry['content']:
                    print("    ✓ Contains 'holding space' phrase")
                if "vibrant energy" in entry['content']:
                    print("    ✓ Contains 'vibrant energy' phrase")
        else:
            print("✗ No diary entries found for Dec 15")
        print()
        
        # 7. Summary
        print("=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        print()
        print("This script verified:")
        print("✓ Message counts and date ranges")
        print("✓ Character interaction breakdown") 
        print("✓ Identity name progression")
        print("✓ Key quotes from bots")
        print("✓ December 15 conflict details")
        print("✓ Diary entry existence")
        print()
        print("Review output above for any discrepancies marked with '✗'")
        print()
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_report_facts())
