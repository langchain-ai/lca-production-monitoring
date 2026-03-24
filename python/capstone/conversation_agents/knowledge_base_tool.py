import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
from langsmith import traceable
from openai import AsyncOpenAI

SEARCH_KNOWLEDGE_BASE_TOOL = {"type": "function", "function": {"name": "search_knowledge_base", "description": "Search company knowledge base for information about policies, procedures, company info, shipping, returns, ordering, contact information, store locations, and business hours. Use this for non-product questions.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Natural language question or search query about company policies or information"}}, "required": ["query"]}}}


class KnowledgeBase:
    """Semantic search over whole Markdown documents using OpenAI embeddings."""

    def __init__(self, client: AsyncOpenAI):
        self.client = client
        self.docs: List[Tuple[str, str]] = []
        self.embeddings: List[List[float]] = []

    async def load(self, kb_dir: str = "./knowledge_base") -> None:
        """Load documents and embeddings, regenerating if any source files changed."""
        kb_path = Path(kb_dir) / "documents"
        cache_path = Path(kb_dir) / "embeddings" / "embeddings.json"

        if not kb_path.exists():
            print(f"Warning: Knowledge base directory '{kb_dir}' not found")
            return

        if self._embeddings_are_stale(kb_path, cache_path):
            print("Knowledge base documents changed, regenerating embeddings...")
            await self._generate_and_cache_embeddings(kb_path, cache_path)
        else:
            with open(cache_path, "r") as f:
                cache_data = json.load(f)
            self.docs = [tuple(doc) for doc in cache_data["docs"]]
            self.embeddings = cache_data["embeddings"]
            print(f"Knowledge base loaded from cache: {len(self.docs)} documents")

    @traceable(name="search_knowledge_base", run_type="tool")
    async def search(self, query: str, top_k: int = 2, langsmith_extra: dict | None = None) -> str:
        """Search knowledge base using cosine similarity. Returns whole documents."""
        if not self.docs or not self.embeddings:
            return "Error: Knowledge base not loaded"

        response = await self.client.embeddings.create(model="text-embedding-3-small", input=query)
        query_embedding = response.data[0].embedding

        similarities = []
        for i, doc_embedding in enumerate(self.embeddings):
            similarity = np.dot(query_embedding, doc_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
            similarities.append((i, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)
        top_results = similarities[:top_k]

        results = []
        for idx, score in top_results:
            filename, content = self.docs[idx]
            results.append(f"=== {filename} (relevance: {score:.3f}) ===\n{content}\n")

        return "\n".join(results)

    @staticmethod
    def _embeddings_are_stale(kb_path: Path, cache_path: Path) -> bool:
        """Check if any document has been modified after the embeddings were generated."""
        if not cache_path.exists():
            return True

        cache_mtime = cache_path.stat().st_mtime

        for file_path in kb_path.glob("*.md"):
            if file_path.name == "CHUNKING_NOTES.md":
                continue
            if file_path.stat().st_mtime > cache_mtime:
                print(f"  Stale: {file_path.name} was modified after embeddings were generated")
                return True

        return False

    async def _generate_and_cache_embeddings(self, kb_path: Path, cache_path: Path) -> None:
        """Generate embeddings for all documents and save to cache."""
        docs = []
        for file_path in kb_path.glob("*.md"):
            if file_path.name == "CHUNKING_NOTES.md":
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                docs.append((file_path.name, content))

        if not docs:
            print(f"Warning: No documents found in '{kb_path}'")
            return

        self.docs = docs

        print(f"Generating embeddings for {len(docs)} documents...")
        embeddings = []
        for filename, content in docs:
            response = await self.client.embeddings.create(model="text-embedding-3-small", input=content)
            embeddings.append(response.data[0].embedding)
            print(f"  {filename}")

        self.embeddings = embeddings

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {"docs": docs, "embeddings": embeddings}
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)
        print(f"Embeddings cached to {cache_path}")
