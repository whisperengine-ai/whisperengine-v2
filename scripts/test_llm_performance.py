import asyncio
import time
import statistics
from typing import List, Dict, Any
from openai import AsyncOpenAI
import sys

# Configuration
BASE_URL = "http://gx10.local:8000/v1"
API_KEY = "dummy"
MAX_CONCURRENCY = 5
MAX_TOKENS = 2048

# Generate prompts of varying sizes
# Rough estimation: 1 token ~= 4 characters
def generate_prompts():
    base_text = "The quick brown fox jumps over the lazy dog. "
    
    # Small: ~20-50 tokens
    small_prompt = "Write a short poem about the future of AI."
    
    # Medium: ~1000 tokens (~4000 chars)
    # 45 chars per sentence. 4000 / 45 ~= 88 repetitions
    medium_context = (base_text * 90)
    medium_prompt = f"Read the following text and summarize it:\n\n{medium_context}\n\nSummary:"
    
    # Large: ~4000 tokens (~16000 chars)
    # 16000 / 45 ~= 355 repetitions
    large_context = (base_text * 360)
    large_prompt = f"Read the following text and identify any patterns:\n\n{large_context}\n\nAnalysis:"
    
    return {
        "Small": small_prompt,
        "Medium": medium_prompt,
        "Large": large_prompt
    }

PROMPTS = generate_prompts()

async def get_models(client: AsyncOpenAI) -> List[str]:
    try:
        response = await client.models.list()
        return [model.id for model in response.data]
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []

async def run_single_test(client: AsyncOpenAI, model: str, prompt: str, request_id: int) -> Dict[str, Any]:
    start_time = time.perf_counter()
    first_token_time = None
    token_count = 0
    
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                token_count += 1
                
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        ttft = (first_token_time - start_time) if first_token_time else total_time
        generation_time = end_time - first_token_time if first_token_time else 0
        tps = token_count / generation_time if generation_time > 0 else 0
        
        return {
            "success": True,
            "ttft": ttft,
            "total_time": total_time,
            "tokens": token_count,
            "tps": tps,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def test_model_concurrency(client: AsyncOpenAI, model: str, prompt_name: str, prompt_text: str, concurrency: int) -> Dict[str, Any]:
    print(f"Testing {model} | Prompt: {prompt_name} | Clients: {concurrency}...")
    
    tasks = [run_single_test(client, model, prompt_text, i) for i in range(concurrency)]
    results = await asyncio.gather(*tasks)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    if not successful:
        return {
            "concurrency": concurrency,
            "prompt_size": prompt_name,
            "success_rate": 0,
            "avg_ttft": 0,
            "avg_tps": 0,
            "avg_latency": 0,
            "errors": [r["error"] for r in failed]
        }
        
    return {
        "concurrency": concurrency,
        "prompt_size": prompt_name,
        "success_rate": len(successful) / len(results) * 100,
        "avg_ttft": statistics.mean([r["ttft"] for r in successful]),
        "avg_tps": statistics.mean([r["tps"] for r in successful]),
        "avg_latency": statistics.mean([r["total_time"] for r in successful]),
        "errors": [r["error"] for r in failed]
    }

async def main():
    print(f"Initializing performance test against {BASE_URL}")
    print(f"Max Tokens: {MAX_TOKENS}")
    print(f"Prompt Sizes: {', '.join(PROMPTS.keys())}")
    
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    
    # 1. Fetch Models
    print("Fetching available models...")
    models = await get_models(client)
    if not models:
        print("No models found or could not connect to endpoint.")
        return

    print(f"Found {len(models)} models: {', '.join(models)}")
    print("-" * 60)

    all_results = {}

    # 2. Test each model
    for model in models:
        print(f"\n=== Benchmarking Model: {model} ===")
        model_results = []
        
        for prompt_name, prompt_text in PROMPTS.items():
            print(f"\n--- Prompt Size: {prompt_name} ---")
            for concurrency in range(1, MAX_CONCURRENCY + 1):
                result = await test_model_concurrency(client, model, prompt_name, prompt_text, concurrency)
                model_results.append(result)
                # Small pause between concurrency levels
                await asyncio.sleep(1)
            
        all_results[model] = model_results

    # 3. Generate Report
    print("\n" + "="*100)
    print(f"{'PERFORMANCE REPORT':^100}")
    print("="*100)
    
    for model, results in all_results.items():
        print(f"\nModel: {model}")
        print(f"{'Prompt':<10} | {'Clients':<8} | {'Success %':<10} | {'TTFT (s)':<10} | {'TPS':<10} | {'Latency (s)':<12}")
        print("-" * 85)
        
        for r in results:
            print(f"{r['prompt_size']:<10} | {r['concurrency']:<8} | {r['success_rate']:<10.1f} | {r['avg_ttft']:<10.3f} | {r['avg_tps']:<10.2f} | {r['avg_latency']:<12.3f}")
            if r['errors']:
                print(f"  Errors: {r['errors'][0]} ...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
