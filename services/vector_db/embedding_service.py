"""
Embedding service using sentence-transformers.
Handles text embedding for vector storage and similarity search.
"""

from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer

from utilities.config_loader import get_config


class EmbeddingService:
    """Service for generating text embeddings using sentence-transformers."""
    
    _instance = None
    _model = None
    
    def __new__(cls) -> 'EmbeddingService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_model()
        return cls._instance
    
    def _initialize_model(self) -> None:
        """Initialize the embedding model."""
        config = get_config()
        model_name = config.get('vector_db.embedding.model_name', 'all-MiniLM-L6-v2')
        
        print(f"📦 Loading embedding model: {model_name}")
        self._model = SentenceTransformer(model_name)
        self._dimension = config.get('vector_db.embedding.dimension', 384)
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension."""
        return self._dimension
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            return [0.0] * self._dimension
        
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts but keep track of indices
        non_empty_indices = []
        non_empty_texts = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(text)
        
        # Generate embeddings for non-empty texts
        if non_empty_texts:
            embeddings = self._model.encode(non_empty_texts, convert_to_numpy=True)
        else:
            embeddings = np.array([])
        
        # Reconstruct result with zero vectors for empty texts
        result = [[0.0] * self._dimension for _ in range(len(texts))]
        for idx, embedding in zip(non_empty_indices, embeddings):
            result[idx] = embedding.tolist()
        
        return result
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Compute cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))


# Global embedding service instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
