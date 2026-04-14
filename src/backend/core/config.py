"""Application configuration for the D&D 5e game engine."""

from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """Ollama LLM configuration."""

    model: str = "qwen2.5:14b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    request_timeout: float = 120.0


class MemgraphConfig(BaseModel):
    """Memgraph graph database configuration."""

    uri: str = "bolt://localhost:7687"
    user: str = ""
    password: str = ""


class ChromaDBConfig(BaseModel):
    """ChromaDB vector database configuration."""

    persist_directory: str = "data/chromadb"
    collection_name: str = "dnd5e_corpus"


class Settings(BaseModel):
    """Application settings."""

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)
    corpus_path: Path = Field(default=None)
    worlds_path: Path = Field(default=None)

    # Services
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    memgraph: MemgraphConfig = Field(default_factory=MemgraphConfig)
    chromadb: ChromaDBConfig = Field(default_factory=ChromaDBConfig)

    # Game settings
    default_seed: Optional[int] = None  # None means random
    world_resolution: int = 5  # feet

    def model_post_init(self, __context) -> None:
        """Set derived paths after initialization."""
        if self.corpus_path is None:
            self.corpus_path = self.project_root / "data" / "corpus"
        if self.worlds_path is None:
            self.worlds_path = self.project_root / "data" / "worlds"

    @classmethod
    def from_yaml(cls, config_path: Path) -> "Settings":
        """Load settings from a YAML file."""
        if not config_path.exists():
            return cls()
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def to_yaml(self, config_path: Path) -> None:
        """Save settings to a YAML file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(self.model_dump(mode="json", exclude={"project_root", "corpus_path", "worlds_path"}), f)


def load_settings() -> Settings:
    """Load settings from config.yaml if it exists."""
    project_root = Path(__file__).parent.parent.parent.parent
    config_path = project_root / "config.yaml"
    return Settings.from_yaml(config_path)


# Global settings instance
settings = load_settings()
