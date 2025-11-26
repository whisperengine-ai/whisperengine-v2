import asyncio
import time
import sys
import os
import numpy as np
import asyncpg
from fastembed import TextEmbedding
from typing import List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_v2.config.settings import settings

def cosine_similarity(a: Any, b: Any) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def benchmark_model(model_name: str, sentences: List[str]) -> dict:
    print(f"\n--- Benchmarking {model_name} ---")
    
    # 1. Load Model
    start_time = time.time()
    try:
        model = TextEmbedding(model_name=model_name)
        # Force load by running one embedding
        list(model.embed(["warmup"]))
    except Exception as e:
        return {"error": str(e)}
    load_time = time.time() - start_time
    print(f"Load time: {load_time:.4f}s")

    # 2. Inference Speed
    start_time = time.time()
    embeddings = list(model.embed(sentences))
    inference_time = time.time() - start_time
    avg_time_per_sentence = inference_time / len(sentences)
    print(f"Inference time for {len(sentences)} sentences: {inference_time:.4f}s ({avg_time_per_sentence*1000:.2f}ms/sentence)")

    # 3. Dimensions
    dims = len(embeddings[0])
    print(f"Dimensions: {dims}")

    return {
        "model": model_name,
        "load_time": load_time,
        "inference_time_ms": avg_time_per_sentence * 1000,
        "dimensions": dims,
        "separation_delta": 0 # Not calculating separation on random messages
    }

async def get_real_messages(limit: int = 200) -> List[str]:
    print(f"Connecting to PostgreSQL at {settings.POSTGRES_URL}...")
    try:
        conn = await asyncpg.connect(settings.POSTGRES_URL)
        rows = await conn.fetch("SELECT content FROM v2_chat_history ORDER BY timestamp DESC LIMIT $1", limit)
        await conn.close()
        
        messages = [row['content'] for row in rows if row['content'] and len(row['content'].strip()) > 0]
        print(f"Retrieved {len(messages)} messages from database.")
        return messages
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return []

async def main():
    # 1. Get Real Data
    sentences = await get_real_messages(200)
    
    if not sentences:
        print("⚠️ No messages found in database. Using synthetic data.")
        sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "Artificial intelligence is transforming the world.",
            "WhisperEngine v2 is a production multi-character Discord AI roleplay platform.",
            "Python is a programming language that lets you work quickly.",
            "To be or not to be, that is the question.",
            "I wandered lonely as a cloud.",
            "The user wants to run benchmark tests.",
            "FastEmbed is a lightweight, fast, Python library for embedding generation.",
            "Vector databases are essential for RAG applications.",
            "Deep learning models require significant computational resources."
        ] * 10

    # Ensure we have enough data for a fair test
    if len(sentences) < 100:
        print(f"⚠️ Only {len(sentences)} messages found. Duplicating to reach ~100 for stable timing.")
        while len(sentences) < 100:
            sentences.extend(sentences)
        sentences = sentences[:200] # Cap at 200

    print(f"Benchmarking with {len(sentences)} unique messages.")
    avg_len = sum(len(s) for s in sentences) / len(sentences)
    print(f"Average message length: {avg_len:.1f} characters")
    print(f"Sample message: '{sentences[0][:50]}...'")

    models_to_test = [
        "sentence-transformers/all-MiniLM-L6-v2",  # Current Baseline (384d)
        "BAAI/bge-small-en-v1.5",                  # BGE Small (384d)
        "BAAI/bge-base-en-v1.5",                   # BGE Base (768d)
        "nomic-ai/nomic-embed-text-v1.5",          # Nomic (768d)
        "snowflake/snowflake-arctic-embed-m",      # Snowflake Medium (768d)
    ]

    results = []
    for model_name in models_to_test:
        results.append(benchmark_model(model_name, sentences))

    print("\n\n=== SUMMARY COMPARISON (REAL DATA) ===")
    print(f"{'Model':<40} | {'Dim':<5} | {'Load(s)':<8} | {'Inf(ms)':<8}")
    print("-" * 80)
    
    for res in results:
        if "error" in res:
            print(f"{res['model']:<40} | ERROR: {res['error']}")
        else:
            print(f"{res['model']:<40} | {res['dimensions']:<5} | {res['load_time']:.2f}{'':<4} | {res['inference_time_ms']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
