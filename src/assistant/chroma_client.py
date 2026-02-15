import os
import asyncio
from typing import List

try:
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:
    chromadb = None


class ChromaClient:
    """Simple wrapper around ChromaDB to fetch personal context.

    This implementation keeps calls synchronous if the chromadb client is sync,
    but exposes async API using run_in_executor.
    """

    def __init__(self, collection_name: str = "personal_context"):
        if chromadb is None:
            raise RuntimeError("chromadb not available; install chromadb package")
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(name=collection_name)

    async def query(self, text: str, top_k: int = 3) -> List[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._query_sync, text, top_k)

    async def add_document(self, doc_id: str, document: str):
        """Ajoute un document à la collection."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_document_sync, doc_id, document)

    def _add_document_sync(self, doc_id: str, document: str):
        try:
            self.collection.add(ids=[doc_id], documents=[document])
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Erreur ajout document ChromaDB: {e}")

    def _query_sync(self, text: str, top_k: int):
        # Use default embedding fn if available; otherwise, do a metadata-only search.
        try:
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            results = self.collection.query(query_texts=[text], n_results=top_k, embedding_function=ef)
        except Exception:
            results = self.collection.query(query_texts=[text], n_results=top_k)

        snippets = []
        for doc in results.get("documents", [[]])[0]:
            snippets.append(doc)
        return snippets
