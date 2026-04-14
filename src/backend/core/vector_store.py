"""ChromaDB vector store for D&D rules corpus."""

from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from markdown_it import MarkdownIt
from rich.console import Console

from .config import settings

console = Console()


class VectorStore:
    """
    ChromaDB vector store for semantic search over D&D rules.

    Indexes markdown files from the corpus and provides semantic search.
    """

    def __init__(self):
        persist_path = settings.project_root / settings.chromadb.persist_directory
        persist_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection_name = settings.chromadb.collection_name
        self._collection: Optional[chromadb.Collection] = None
        self._md_parser = MarkdownIt()

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create the corpus collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "D&D 5e rules corpus"},
            )
        return self._collection

    def is_indexed(self) -> bool:
        """Check if the corpus has been indexed."""
        return self.collection.count() > 0

    def index_corpus(self, force: bool = False) -> int:
        """
        Index all markdown files from the corpus directory.

        Args:
            force: If True, reindex even if already indexed

        Returns:
            Number of chunks indexed
        """
        if self.is_indexed() and not force:
            console.print("[yellow]Corpus already indexed. Use --force to reindex.[/yellow]")
            return self.collection.count()

        if force:
            self.client.delete_collection(self.collection_name)
            self._collection = None

        corpus_path = settings.corpus_path
        if not corpus_path.exists():
            console.print(f"[red]Corpus directory not found: {corpus_path}[/red]")
            return 0

        md_files = list(corpus_path.glob("*.md"))
        if not md_files:
            console.print(f"[red]No markdown files found in {corpus_path}[/red]")
            return 0

        total_chunks = 0
        for md_file in md_files:
            console.print(f"  Indexing {md_file.name}...", end="")
            chunks = self._index_file(md_file)
            total_chunks += chunks
            console.print(f" {chunks} chunks")

        console.print(f"[green]Indexed {total_chunks} chunks from {len(md_files)} files[/green]")
        return total_chunks

    def _index_file(self, file_path: Path) -> int:
        """
        Index a single markdown file.

        Splits the file into chunks by headers and paragraphs.
        """
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Parse markdown and extract text chunks
        chunks = self._split_into_chunks(content, file_path.stem)

        if not chunks:
            return 0

        # Add to collection
        self.collection.add(
            ids=[chunk["id"] for chunk in chunks],
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[chunk["metadata"] for chunk in chunks],
        )

        return len(chunks)

    def _split_into_chunks(self, content: str, source: str, chunk_size: int = 1000) -> list[dict]:
        """
        Split markdown content into searchable chunks.

        Tries to split on section headers, falling back to paragraphs.
        """
        chunks = []
        current_section = ""
        current_text = []
        chunk_id = 0

        lines = content.split("\n")
        for line in lines:
            # Check for header
            if line.startswith("#"):
                # Save current chunk if not empty
                if current_text:
                    text = "\n".join(current_text).strip()
                    if text and len(text) > 50:  # Skip very short chunks
                        chunks.append({
                            "id": f"{source}_{chunk_id}",
                            "text": text,
                            "metadata": {"source": source, "section": current_section},
                        })
                        chunk_id += 1
                    current_text = []

                # Update section
                current_section = line.lstrip("#").strip()
                current_text.append(line)
            else:
                current_text.append(line)

                # Check if chunk is getting too large
                current_size = sum(len(t) for t in current_text)
                if current_size > chunk_size and line.strip() == "":
                    text = "\n".join(current_text).strip()
                    if text and len(text) > 50:
                        chunks.append({
                            "id": f"{source}_{chunk_id}",
                            "text": text,
                            "metadata": {"source": source, "section": current_section},
                        })
                        chunk_id += 1
                    current_text = []

        # Don't forget the last chunk
        if current_text:
            text = "\n".join(current_text).strip()
            if text and len(text) > 50:
                chunks.append({
                    "id": f"{source}_{chunk_id}",
                    "text": text,
                    "metadata": {"source": source, "section": current_section},
                })

        return chunks

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """
        Search the corpus for relevant content.

        Args:
            query: Search query
            n_results: Number of results to return

        Returns:
            List of matching documents with metadata
        """
        if not self.is_indexed():
            console.print("[yellow]Corpus not indexed. Run 'index-corpus' first.[/yellow]")
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        matches = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                matches.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })

        return matches


# Global vector store instance
vector_store = VectorStore()
