import os
from pydantic_settings import BaseSettings
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class RagSettings(BaseSettings):
    CHROMA_PERSIST_DIR: str = os.path.join(os.getcwd(), "chroma_db")

    EMBEDDING_PROVIDER: str = "google"
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"

    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    COLLECTION_TOOLS: str = "agent_tools"
    COLLECTION_MEMORY: str = "agent_memory"

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        extra="ignore",
    )

settings = RagSettings()
