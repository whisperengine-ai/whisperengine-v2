from fastembed import TextEmbedding
import os

def download_models():
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")
    
    print(f"Downloading embedding model: {model_name}...")
    if cache_dir:
        print(f"Using cache directory: {cache_dir}")
        TextEmbedding(model_name=model_name, cache_dir=cache_dir)
    else:
        TextEmbedding(model_name=model_name)
    print("Download complete.")

if __name__ == "__main__":
    download_models()
