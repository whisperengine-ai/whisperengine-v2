#!/usr/bin/env python3
"""
Enable bot-to-bot conversation settings for all bot .env files.
"""

import os
import re
from pathlib import Path

# Bot env files to update
BOT_NAMES = [
    "elena", "nottaylor", "dotty", "aria", "dream", 
    "jake", "marcus", "ryan", "sophia", "gabriel", 
    "aethys", "aetheris"
]

# Settings to enable for bot-to-bot conversations
SETTINGS = {
    "ENABLE_AUTONOMOUS_ACTIVITY": "true",
    "ENABLE_CROSS_BOT_CHAT": "true",
    "ENABLE_AUTONOMOUS_POSTING": "true",
    "ENABLE_BOT_CONVERSATIONS": "true",
    "CROSS_BOT_MAX_CHAIN": "5",
    "CROSS_BOT_COOLDOWN_MINUTES": "5",
    "CROSS_BOT_RESPONSE_CHANCE": "0.95",
    "BOT_CONVERSATION_MAX_TURNS": "3",
    "BOT_CONVERSATION_CHANNEL_ID": "1446040182766702727",
}

def update_env_file(filepath: Path) -> dict:
    """Update settings in an env file. Returns dict of changes made."""
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}
    
    content = filepath.read_text()
    changes = {}
    
    for key, value in SETTINGS.items():
        # Pattern to match the key with any value
        pattern = rf'^{re.escape(key)}=.*$'
        replacement = f'{key}={value}'
        
        if re.search(pattern, content, re.MULTILINE):
            old_match = re.search(pattern, content, re.MULTILINE)
            old_value = old_match.group(0) if old_match else None
            if old_value != replacement:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                changes[key] = {"from": old_value, "to": replacement}
        else:
            # Key doesn't exist, we'd need to add it (skip for now)
            changes[key] = {"error": "key not found in file"}
    
    if changes:
        filepath.write_text(content)
    
    return changes


def main():
    root = Path(__file__).parent.parent
    
    for bot_name in BOT_NAMES:
        env_file = root / f".env.{bot_name}"
        print(f"\n{'='*50}")
        print(f"Updating {env_file.name}")
        print('='*50)
        
        changes = update_env_file(env_file)
        
        for key, change in changes.items():
            if "error" in change:
                print(f"  ⚠️  {key}: {change['error']}")
            else:
                print(f"  ✅ {key}")
                print(f"      {change['from']} → {change['to']}")
    
    print(f"\n{'='*50}")
    print("Done! Restart bots to apply: ./bot.sh restart bots")
    print('='*50)


if __name__ == "__main__":
    main()
