import time
import numpy as np
from fastembed import TextEmbedding
from typing import List, Any

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

    # 4. Semantic Separation
    query = "What is the capital of France?"
    positive = "Paris is the capital city of France."
    negative = "The quick brown fox jumps over the lazy dog."
    
    q_emb = list(model.embed([query]))[0]
    p_emb = list(model.embed([positive]))[0]
    n_emb = list(model.embed([negative]))[0]
    
    pos_sim = cosine_similarity(q_emb, p_emb)
    neg_sim = cosine_similarity(q_emb, n_emb)
    delta = pos_sim - neg_sim
    
    print(f"Query: '{query}'")
    print(f"Positive Sim ('{positive}'): {pos_sim:.4f}")
    print(f"Negative Sim ('{negative}'): {neg_sim:.4f}")
    print(f"Separation Delta: {delta:.4f}")

    return {
        "model": model_name,
        "load_time": load_time,
        "inference_time_ms": avg_time_per_sentence * 1000,
        "dimensions": dims,
        "separation_delta": delta
    }

def main():
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
    ] * 10  # 100 sentences

    models_to_test = [
        "sentence-transformers/all-MiniLM-L6-v2",  # Current
        "BAAI/bge-base-en-v1.5"                    # Proposed
    ]

    results = []
    for model_name in models_to_test:
        results.append(benchmark_model(model_name, sentences))

    print("\n\n=== SUMMARY COMPARISON ===")
    print(f"{'Metric':<25} | {'all-MiniLM-L6-v2':<25} | {'BAAI/bge-base-en-v1.5':<25}")
    print("-" * 80)
    
    current = results[0]
    proposed = results[1]
    
    if "error" in current:
        print(f"Error testing current model: {current['error']}")
        return
    if "error" in proposed:
        print(f"Error testing proposed model: {proposed['error']}")
        return

    print(f"{'Dimensions':<25} | {current['dimensions']:<25} | {proposed['dimensions']:<25}")
    print(f"{'Load Time (s)':<25} | {current['load_time']:.4f}{'':<19} | {proposed['load_time']:.4f}")
    print(f"{'Inference (ms/sent)':<25} | {current['inference_time_ms']:.2f}{'':<20} | {proposed['inference_time_ms']:.2f}")
    print(f"{'Semantic Delta':<25} | {current['separation_delta']:.4f}{'':<19} | {proposed['separation_delta']:.4f}")
    
    print("\nRecommendation:")
    if proposed['separation_delta'] > current['separation_delta']:
        print("✅ BAAI/bge-base-en-v1.5 shows better semantic separation.")
    else:
        print("⚠️ BAAI/bge-base-en-v1.5 does NOT show better semantic separation.")
        
    if proposed['dimensions'] == 768:
        print("✅ BAAI/bge-base-en-v1.5 provides 768 dimensions (2x information density).")
        
    speed_ratio = proposed['inference_time_ms'] / current['inference_time_ms']
    print(f"ℹ️  BAAI/bge-base-en-v1.5 is {speed_ratio:.1f}x slower than MiniLM (expected for larger model).")

if __name__ == "__main__":
    main()
