#!/usr/bin/env python3
"""
Check Qdrant for user's grandiose realizations and self-declarations
"""
import asyncio
from qdrant_client import QdrantClient
from datetime import datetime
import json

USER_ID = "932729340968443944"

async def check_qdrant_memories():
    """Query Qdrant for user's messages"""
    
    # Connect to Qdrant
    client = QdrantClient(host="localhost", port=6333)
    
    # Try nottaylor collection first (most interactions)
    collections = ["whisperengine_memory_nottaylor", "whisperengine_memory_dotty"]
    
    for collection_name in collections:
        try:
            print(f"\n{'='*80}")
            print(f"COLLECTION: {collection_name}")
            print('='*80)
            
            # Get all points for this user
            scroll_result = client.scroll(
                collection_name=collection_name,
                scroll_filter={
                    "must": [
                        {"key": "user_id", "match": {"value": USER_ID}}
                    ]
                },
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            
            print(f"\nFound {len(points)} memory points for user {USER_ID}")
            
            # Look for user messages (role=user/human)
            user_messages = []
            for point in points:
                payload = point.payload
                if payload.get('role') in ['user', 'human']:
                    user_messages.append({
                        'timestamp': payload.get('timestamp'),
                        'content': payload.get('content', ''),
                        'metadata': payload.get('metadata', {})
                    })
            
            # Sort by timestamp
            user_messages.sort(key=lambda x: x['timestamp'])
            
            print(f"\nFound {len(user_messages)} user messages")
            print("\n" + "="*80)
            print("USER MESSAGES (Checking for 'realizations' and grandiose patterns)")
            print("="*80)
            
            # Keywords to look for
            grandiose_keywords = [
                'realized', 'realization', 'epiphany', 'understand now',
                'divine', 'god', 'cosmic', 'universe', 'balance', 'nexus',
                'ether', 'phoenix', 'sage', 'chosen', 'special',
                'like taylor', 'like beyonce', 'like christ', 'like enoch',
                'I am the', 'I am now', 'manifesting', 'channeling',
                'frequency', 'vibration', 'ascending', 'transcend',
                'my purpose', 'my calling', 'destined', 'meant to'
            ]
            
            matches = []
            for i, msg in enumerate(user_messages, 1):
                content_lower = msg['content'].lower()
                matched_keywords = [kw for kw in grandiose_keywords if kw in content_lower]
                
                if matched_keywords:
                    matches.append({
                        'index': i,
                        'timestamp': msg['timestamp'],
                        'content': msg['content'],
                        'keywords': matched_keywords
                    })
            
            print(f"\nFound {len(matches)} messages with grandiose patterns\n")
            
            # Show all matches
            for match in matches:
                print(f"\n[{match['index']}] {match['timestamp']}")
                print(f"Keywords: {', '.join(match['keywords'])}")
                print(f"Content: {match['content'][:500]}")
                print("-" * 80)
            
            # Pattern analysis
            if matches:
                print("\n" + "="*80)
                print("PATTERN ANALYSIS")
                print("="*80)
                
                # Count keyword frequency
                keyword_freq = {}
                for match in matches:
                    for kw in match['keywords']:
                        keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
                
                print("\nMost common grandiose terms:")
                for kw, count in sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"  - '{kw}': {count} times")
                
                # Timeline
                print(f"\nTimeline:")
                print(f"  First grandiose message: {matches[0]['timestamp']}")
                print(f"  Last grandiose message: {matches[-1]['timestamp']}")
                print(f"  Duration: ~{len(matches)} messages over {len(user_messages)} total user messages")
                print(f"  Percentage: {len(matches)/len(user_messages)*100:.1f}% of user messages contained grandiose language")
        
        except Exception as e:
            print(f"Error accessing {collection_name}: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(check_qdrant_memories())
