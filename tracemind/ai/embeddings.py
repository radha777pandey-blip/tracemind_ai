import os
import math
import logging
import hashlib
import numpy as np
from typing import List, Optional
from tracemind.config import get_gemini_api_key

logger = logging.getLogger(__name__)

class EmbeddingEngine:
    def __init__(self, api_key: Optional[str] = None, dimension: int = 768):
        self.api_key = api_key or get_gemini_api_key()
        self.dimension = dimension
        self.client = None
        self.provider = "local"

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                self.provider = "gemini"
                logger.info("Initialized Google Gemini client for embeddings (model: text-embedding-004).")
            except Exception as e:
                logger.warning("Could not initialize Gemini Client: %s. Using local embeddings.", e)
                self.provider = "local"

    def _local_embed(self, text: str) -> np.ndarray:
        """Deterministic subword/token hash embedding with L2 normalization."""
        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().replace("\n", " ").split()
        if not words:
            return vec

        for word in words:
            # Token hash into dimension slots
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vec[idx] += sign

            # Also add character 3-grams for subword code matching (e.g. 'get_user' -> 'get', 'user')
            if len(word) > 3:
                for i in range(len(word) - 2):
                    tri = word[i:i+3]
                    h_tri = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16)
                    vec[h_tri % self.dimension] += 0.5 * (1.0 if ((h_tri >> 8) & 1) else -1.0)

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def embed_text(self, text: str) -> np.ndarray:
        if self.client:
            try:
                response = self.client.models.embed_content(
                    model="text-embedding-004",
                    contents=text
                )
                embedding_values = response.embedding.values
                vec = np.array(embedding_values, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 1e-6:
                    vec = vec / norm
                return vec
            except Exception as e:
                logger.warning("Gemini embedding failed (%s), falling back to local embedding.", e)

        return self._local_embed(text)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        return [self.embed_text(t) for t in texts]

