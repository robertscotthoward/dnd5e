"""ChromaDB vector store for D&D rules corpus, powered by LlamaIndex."""

from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from rich.console import Console

from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    Settings as LlamaSettings,
)
from llama_index.core.embeddings import resolve_embed_model
from llama_index.vector_stores.chroma import ChromaVectorStore

from .config import settings

console = Console()


def _configure_llamaindex() -> None:
    """Configure LlamaIndex to use local embeddings (no OpenAI key needed)."""
    import os
    from llama_index.core.llms import MockLLM
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    LlamaSettings.embed_model = resolve_embed_model("local:BAAI/bge-small-en-v1.5")
    # Set MockLLM explicitly so LlamaIndex doesn't warn about implicit fallback.
    # We never use the LlamaIndex LLM path — Ollama is called directly in ai_client.py.
    LlamaSettings.llm = MockLLM()


class VectorStore:
    """
    ChromaDB vector store for semantic search over D&D rules.

    Uses LlamaIndex SimpleDirectoryReader + VectorStoreIndex for ingestion
    and ChromaDB for persistence.
    """

    def __init__(self):
        persist_path = settings.project_root / settings.chromadb.persist_directory
        persist_path.mkdir(parents=True, exist_ok=True)

        self._persist_path = persist_path
        self.collection_name = settings.chromadb.collection_name
        self._chroma_client: Optional[chromadb.PersistentClient] = None
        self._index: Optional[VectorStoreIndex] = None

    @property
    def chroma_client(self) -> chromadb.PersistentClient:
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(
                path=str(self._persist_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._chroma_client

    def _get_collection(self) -> chromadb.Collection:
        return self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "D&D 5e rules corpus"},
        )

    def is_indexed(self) -> bool:
        """Check if the corpus has been indexed."""
        try:
            col = self.chroma_client.get_collection(self.collection_name)
            return col.count() > 0
        except Exception:
            return False

    def index_corpus(self, force: bool = False) -> int:
        """
        Ingest all markdown files from data/corpus/ into ChromaDB via LlamaIndex.

        Reports file count and chunk count on completion.

        Args:
            force: Re-index even if already indexed.

        Returns:
            Total number of chunks (nodes) indexed.
        """
        if self.is_indexed() and not force:
            console.print("[yellow]Corpus already indexed. Use --force to reindex.[/yellow]")
            count = self._get_collection().count()
            console.print(f"[dim]Current chunk count: {count}[/dim]")
            return count

        if force:
            try:
                self.chroma_client.delete_collection(self.collection_name)
            except Exception:
                pass
            self._index = None

        corpus_path = settings.corpus_path
        if not corpus_path.exists():
            console.print(f"[red]Corpus directory not found: {corpus_path}[/red]")
            return 0

        md_files = list(corpus_path.glob("**/*.md"))
        if not md_files:
            console.print(f"[red]No markdown files found in {corpus_path}[/red]")
            return 0

        console.print(f"Found {len(md_files)} markdown file(s) in {corpus_path}")
        for f in md_files:
            console.print(f"  - {f.name}")

        console.print("[bold]Configuring LlamaIndex embeddings (local model)...[/bold]")
        _configure_llamaindex()

        console.print("[bold]Loading documents...[/bold]")
        reader = SimpleDirectoryReader(
            input_dir=str(corpus_path),
            recursive=True,
            required_exts=[".md"],
        )
        documents = reader.load_data()
        console.print(f"Loaded {len(documents)} document segment(s)")

        console.print("[bold]Building vector index in ChromaDB...[/bold]")
        chroma_collection = self._get_collection()
        chroma_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_ctx = StorageContext.from_defaults(vector_store=chroma_store)

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_ctx,
            show_progress=True,
        )

        chunk_count = chroma_collection.count()
        console.print(
            f"\n[green]Indexed {len(md_files)} file(s) -> {chunk_count} chunk(s) into ChromaDB.[/green]"
        )
        return chunk_count

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Search the corpus for relevant content.

        Args:
            query: Search query text.
            n_results: Number of results to return.

        Returns:
            List of matching documents with metadata.
        """
        if not self.is_indexed():
            console.print("[yellow]Corpus not indexed. Run 'index-corpus' first.[/yellow]")
            return []

        _configure_llamaindex()

        chroma_collection = self._get_collection()
        chroma_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_ctx = StorageContext.from_defaults(vector_store=chroma_store)

        index = VectorStoreIndex.from_vector_store(
            chroma_store,
            storage_context=storage_ctx,
        )
        retriever = index.as_retriever(similarity_top_k=n_results)
        nodes = retriever.retrieve(query)

        matches = []
        for node in nodes:
            matches.append({
                "text": node.get_content(),
                "metadata": node.metadata or {},
                "distance": 1.0 - node.score if node.score is not None else None,
            })

        return matches


# Global vector store instance
vector_store = VectorStore()
