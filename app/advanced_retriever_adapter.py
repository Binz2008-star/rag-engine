"""Advanced retrieval adapter - wraps app.retriever.Retriever for shadow-mode comparison."""

from __future__ import annotations

import logging
from typing import List, Optional
import numpy as np

from app.config import USE_ADVANCED_RETRIEVAL_SHADOW
from app.models import RetrievalHit, RetrievedChunk, Chunk
from app.embeddings import EmbeddingClient
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)


class MultiIndexVectorStore:
    """
    Adapter that wraps multiple FaissIndex instances (by intent) and presents
    them as a single VectorStore interface for the advanced retriever.

    This solves the wiring issue: current system uses separate indexes (cv, eco, general),
    while advanced retriever expects a single VectorStore.
    """

    def __init__(self, indexes: dict):
        """
        Initialize with separate FaissIndex instances.

        Args:
            indexes: dict of {intent: FaissIndex}
        """
        self.indexes = indexes or {}
        self.chunks: List[Chunk] = []
        self.dim = 0

        # Merge chunks from all indexes
        for intent, faiss_index in self.indexes.items():
            self.chunks.extend(faiss_index.chunks)
            if faiss_index.dim > 0:
                self.dim = faiss_index.dim

        logger.info("MultiIndexVectorStore initialized: %d chunks from %d intent indexes",
                    len(self.chunks), len(self.indexes))

    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> List[tuple[Chunk, float]]:
        """
        Search across all intent indexes and merge results.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return

        Returns:
            List of (Chunk, score) tuples
        """
        all_results: List[tuple[Chunk, float]] = []

        # Search each intent index
        for intent, faiss_index in self.indexes.items():
            try:
                hits = faiss_index.search(query_embedding, top_k=top_k)
                # Convert RetrievalHit to (Chunk, score) tuples
                for hit in hits:
                    chunk = Chunk(
                        chunk_id=hit.chunk_id,
                        source=hit.source,
                        text=hit.text,
                        path=hit.path,
                        doc_type=hit.doc_type,
                    )
                    all_results.append((chunk, hit.score))
            except Exception as e:
                logger.warning("Search failed for intent %s: %s", intent, e)

        # Sort by score and return top_k
        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results[:top_k]


class AdvancedRetrievalAdapter:
    """
    Adapter to wrap app.retriever.Retriever for shadow-mode comparison.

    This adapter allows the advanced retrieval system to run alongside the current
    MultiRetriever without affecting production behavior. It converts the advanced
    RetrievedChunk objects into RetrievalHit format expected by the pipeline.
    """

    def __init__(self, indexes=None):
        """
        Initialize the adapter.

        Args:
            indexes: Current indexes dict (FaissIndex instances by intent)
        """
        self._indexes = indexes
        self._advanced_retriever = None
        self._vector_store = None
        self._enabled = USE_ADVANCED_RETRIEVAL_SHADOW and indexes is not None

        if self._enabled:
            try:
                # Initialize advanced retriever with EmbeddingClient
                self._advanced_retriever = self._init_advanced_retriever()
                logger.info("Advanced retrieval shadow mode: ENABLED")
            except Exception as e:
                logger.warning("Failed to initialize advanced retriever: %s", e)
                self._enabled = False
        else:
            logger.info("Advanced retrieval shadow mode: DISABLED")

    def _init_advanced_retriever(self):
        """Initialize app.retriever.Retriever with required dependencies."""
        # Create EmbeddingClient
        embedding_client = EmbeddingClient()

        # Create MultiIndexVectorStore from existing indexes
        self._vector_store = self._create_vector_store_from_indexes()

        # Initialize BM25Index from merged chunks
        self._bm25_index = self._create_bm25_index()

        # Import and instantiate advanced retriever
        from app.retriever import Retriever
        retriever = Retriever(embedding_client=embedding_client)

        # Inject BM25Index into retriever
        retriever._bm25 = self._bm25_index

        return retriever

    def _create_bm25_index(self):
        """Create BM25Index from unified VectorStore chunks."""
        from app.bm25_index import BM25Index
        bm25 = BM25Index()
        if self._vector_store and self._vector_store.chunks:
            bm25.build(self._vector_store.chunks)
            logger.info("BM25Index built with %d chunks", len(self._vector_store.chunks))
        else:
            logger.warning("No chunks available for BM25Index")
        return bm25

    def _create_vector_store_from_indexes(self) -> VectorStore:
        """Create a unified VectorStore from the current FaissIndex instances."""
        # Build a unified VectorStore for shadow mode
        # This is the minimal solution: load chunks from all indexes, re-embed, build single VectorStore
        shadow_vector_store = self._build_unified_vector_store()
        return shadow_vector_store

    def _build_unified_vector_store(self) -> VectorStore:
        """Build a unified VectorStore from separate FaissIndex instances."""
        from app.vector_store import VectorStore
        from pathlib import Path
        import numpy as np

        # Check if shadow VectorStore already exists
        shadow_index_path = Path("models/shadow.faiss")
        shadow_metadata_path = Path("models/shadow_metadata.json")

        if shadow_index_path.exists() and shadow_metadata_path.exists():
            logger.info("Loading existing shadow VectorStore")
            vector_store = VectorStore()
            try:
                # Temporarily override the config paths for shadow store
                import app.config as config
                original_faiss_path = config.FAISS_INDEX_PATH
                original_metadata_path = config.METADATA_PATH

                config.FAISS_INDEX_PATH = shadow_index_path
                config.METADATA_PATH = shadow_metadata_path

                vector_store.load()

                # Restore original paths
                config.FAISS_INDEX_PATH = original_faiss_path
                config.METADATA_PATH = original_metadata_path

                logger.info("Shadow VectorStore loaded: %d chunks", len(vector_store.chunks))
                return vector_store
            except Exception as e:
                logger.warning("Failed to load shadow VectorStore, rebuilding: %s", e)

        # Build unified VectorStore from separate indexes
        logger.info("Building unified shadow VectorStore from separate indexes")

        # Collect all chunks from all indexes
        all_chunks = []
        for intent, faiss_index in self._indexes.items():
            all_chunks.extend(faiss_index.chunks)

        if not all_chunks:
            logger.warning("No chunks found in any index")
            return VectorStore()

        logger.info("Collected %d chunks from %d intent indexes", len(all_chunks), len(self._indexes))

        # Extract existing embeddings from FAISS indexes instead of re-embedding
        # This avoids Ollama 500 errors and long build times
        logger.info("Extracting existing embeddings from FAISS indexes")
        all_embeddings = []
        all_chunks_ordered = []

        for intent, faiss_index in self._indexes.items():
            # Get embeddings from FAISS index
            if faiss_index.index is not None and faiss_index.chunks:
                # Reconstruct embeddings from FAISS index
                index_embeddings = faiss_index.index.reconstruct_n(0, len(faiss_index.chunks))
                all_embeddings.append(index_embeddings)
                all_chunks_ordered.extend(faiss_index.chunks)
                logger.debug("Extracted %d embeddings from %s index", len(faiss_index.chunks), intent)

        all_embeddings = np.vstack(all_embeddings)
        all_chunks = all_chunks_ordered

        # Build VectorStore
        vector_store = VectorStore()
        vector_store.build(all_chunks, all_embeddings)

        # Save shadow VectorStore
        try:
            import app.config as config
            original_faiss_path = config.FAISS_INDEX_PATH
            original_metadata_path = config.METADATA_PATH
            original_storage_dir = config.STORAGE_DIR

            config.FAISS_INDEX_PATH = shadow_index_path
            config.METADATA_PATH = shadow_metadata_path
            config.STORAGE_DIR = Path("models")

            vector_store.save()

            # Restore original paths
            config.FAISS_INDEX_PATH = original_faiss_path
            config.METADATA_PATH = original_metadata_path
            config.STORAGE_DIR = original_storage_dir

            logger.info("Shadow VectorStore saved to models/shadow.faiss and models/shadow_metadata.json")
        except Exception as e:
            logger.warning("Failed to save shadow VectorStore: %s", e)

        return vector_store

    def retrieve(
        self,
        query_vec,
        intent: str,
        query: str,
        top_k: int = 5,
    ) -> tuple[List[RetrievalHit], Optional[dict]]:
        """
        Retrieve using advanced path in shadow mode.

        Args:
            query_vec: Query embedding (not used by advanced path)
            intent: Intent classification (not used by advanced path)
            query: Query string
            top_k: Number of results to return

        Returns:
            Tuple of (retrieval_hits, shadow_metadata)
            - retrieval_hits: Empty list if shadow disabled or advanced fails
            - shadow_metadata: Dict with advanced retrieval results if enabled
        """
        shadow_metadata = None

        if not self._enabled or self._advanced_retriever is None:
            return [], None

        try:
            # Call advanced retriever
            advanced_chunks = self._advanced_retriever.retrieve(query, self._vector_store)

            # Convert RetrievedChunk to RetrievalHit format
            retrieval_hits = self._convert_to_retrieval_hits(advanced_chunks)

            # Extract intent from advanced retriever
            advanced_intent = getattr(self._advanced_retriever, 'last_intent', None)
            advanced_intent_confidence = getattr(self._advanced_retriever, 'last_intent_confidence', 0.0)
            advanced_intent_method = getattr(self._advanced_retriever, 'last_intent_method', None)

            shadow_metadata = {
                "advanced_enabled": True,
                "query": query,
                "primary_intent": intent,
                "advanced_intent": advanced_intent,
                "advanced_intent_confidence": advanced_intent_confidence,
                "advanced_intent_method": advanced_intent_method,
                "status": "success",
                "advanced_sources": [rc.source for rc in advanced_chunks],
                "advanced_scores": [float(rc.score) for rc in advanced_chunks],
            }

            logger.debug(
                "Advanced retrieval shadow: query=%s primary_intent=%s advanced_intent=%s results=%d",
                query, intent, advanced_intent, len(advanced_chunks)
            )

            return retrieval_hits, shadow_metadata

        except Exception as e:
            logger.warning("Advanced retrieval shadow failed: %s", e)
            shadow_metadata = {
                "advanced_enabled": True,
                "query": query,
                "primary_intent": intent,
                "status": "error",
                "error": str(e)
            }

        return [], shadow_metadata

    def _convert_to_retrieval_hits(self, chunks: list) -> list:
        """Convert list of RetrievedChunk to list of RetrievalHit."""
        return [self._convert_to_retrieval_hit(c) for c in chunks]

    def _convert_to_retrieval_hit(self, chunk: RetrievedChunk) -> RetrievalHit:
        """Convert RetrievedChunk to RetrievalHit format."""
        # RetrievedChunk doesn't have 'source', use doc_type or path as fallback
        source = getattr(chunk, 'source', None)
        if source is None:
            # Use doc_type or extract from path
            source = getattr(chunk, 'doc_type', 'unknown')
            if chunk.path and chunk.path != 'unknown':
                # Extract filename from path
                source = chunk.path.split('/')[-1] if '/' in chunk.path else chunk.path

        return RetrievalHit(
            chunk_id=chunk.chunk_id,
            source=source,
            text=chunk.text,
            score=chunk.score,
            path=chunk.path,
            doc_type=chunk.doc_type,
        )

    def is_enabled(self) -> bool:
        """Check if advanced retrieval shadow mode is enabled."""
        return self._enabled
