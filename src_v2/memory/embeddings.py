from typing import List
from fastembed import TextEmbedding
from loguru import logger
import threading
import os

class EmbeddingService:
    """
    Service for generating vector embeddings using FastEmbed.
    Defaults to 'sentence-transformers/all-MiniLM-L6-v2' (384 dimensions).
    """
    
    _model_cache: dict[str, tuple[TextEmbedding, threading.Lock]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        
    @property
    def _model_entry(self) -> tuple[TextEmbedding, threading.Lock]:
        """Lazy loading of the model with thread-safe locking."""
        if self.model_name not in self._model_cache:
            with self._cache_lock:
                # Double-checked locking pattern to ensure thread safety
                if self.model_name not in self._model_cache:
                    logger.info(f"Loading embedding model: {self.model_name}")
                    
                    # Check for cache path env var
                    cache_dir = os.environ.get("FASTEMBED_CACHE_PATH")
                    kwargs = {"model_name": self.model_name}
                    if cache_dir:
                        logger.info(f"Using FastEmbed cache: {cache_dir}")
                        kwargs["cache_dir"] = cache_dir
                        
                    model = TextEmbedding(**kwargs)
                    self._model_cache[self.model_name] = (model, threading.Lock())
                    logger.info("Embedding model loaded successfully.")
        return self._model_cache[self.model_name]

    @property
    def model(self) -> TextEmbedding:
        """Returns the model instance (for backward compatibility/direct access if needed)."""
        return self._model_entry[0]

    def embed_query(self, text: str) -> List[float]:
        """Embed a single string query."""
        model, lock = self._model_entry
        with lock:
            # list(model.embed([text])) returns a generator of numpy arrays
            embeddings = list(model.embed([text]))
            return embeddings[0].tolist()

    async def embed_query_async(self, text: str) -> List[float]:
        """Embed a single string query asynchronously."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_query, text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        model, lock = self._model_entry
        with lock:
            embeddings = list(model.embed(texts))
            return [e.tolist() for e in embeddings]
