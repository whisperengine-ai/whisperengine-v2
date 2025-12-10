#!/usr/bin/env python3
"""
Add DAILY_LIFE_SPONTANEITY_CHANCE setting to all bot .env files.
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

# Set to 15% for testing (normal is 1%)
SPONTANEITY_LINE = "DAILY_LIFE_SPONTANEITY_CHANCE=0.15"

def update_env_file(filepath: Path) -> dict:
    """Add DAILY_LIFE_SPONTANEITY_CHANCE if not present."""
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}
    
    content = filepath.read_text()
    
    # Check if already present
    if "DAILY_LIFE_SPONTANEITY_CHANCE" in content:
        # Update existing value
        pattern = r'^DAILY_LIFE_SPONTANEITY_CHANCE=.*$'
        if re.search(pattern, content, re.MULTILINE):
            old_match = re.search(pattern, content, re.MULTILINE)
            old_value = old_match.group(0) if old_match else None
            content = re.sub(pattern, SPONTANEITY_LINE, content, flags=re.MULTILINE)
            filepath.write_text(content)
            return {"updated": True, "from": old_value, "to": SPONTANEITY_LINE}
        return {"skipped": True, "reason": "already present"}
    
    # Add after DISCORD_CHECK_MESSAGE_LOOKBACK or at end of Daily Life section
    if "DISCORD_CHECK_MESSAGE_LOOKBACK" in content:
        content = content.replace(
            "DISCORD_CHECK_MESSAGE_LOOKBACK=",
            f"DISCORD_CHECK_MESSAGE_LOOKBACK="
        )
        # Find the line and add after it
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.startswith("DISCORD_CHECK_MESSAGE_LOOKBACK="):
                new_lines.append(SPONTANEITY_LINE)
        content = '\n'.join(new_lines)
        filepath.write_text(content)
        return {"added": True, "line": SPONTANEITY_LINE}
    
    # Fallback: add at end
    if not content.endswith('\n'):
        content += '\n'
    content += f"\n# Spontaneity chance for bot-to-bot conversations (0.15 = 15%)\n{SPONTANEITY_LINE}\n"
    filepath.write_text(content)
    return {"added": True, "line": SPONTANEITY_LINE, "at": "end"}


def main():
    root = Path(__file__).parent.parent
    
    print(f"\n{'='*50}")
    print(f"Adding DAILY_LIFE_SPONTANEITY_CHANCE=0.15 (15%)")
    print(f"(Normal production is 0.01 = 1%)")
    print(f"{'='*50}")
    
    for bot_name in BOT_NAMES:
        env_file = root / f".env.{bot_name}"
        print(f"\n{env_file.name}:", end=" ")
        
        result = update_env_file(env_file)
        
        if "error" in result:
            print(f"❌ {result['error']}")
        elif "updated" in result:
            print(f"✅ Updated: {result['from']} → {result['to']}")
        elif "added" in result:
            print(f"✅ Added: {result['line']}")
        elif "skipped" in result:
            print(f"⏭️  {result['reason']}")
    
    print(f"\n{'='*50}")
    print("Done! Stop and start bots to apply:")
    print("  ./bot.sh stop bots && ./bot.sh start bots")
    print('='*50)


if __name__ == "__main__":
    main()
