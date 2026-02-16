import chromadb
from chromadb.config import Settings
from src.rag.config import settings
from src.rag.embeddings import get_embedding_function
import logging

logger = logging.getLogger(__name__)

class ChromaClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaClient, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        """Initializes the persistent ChromaDB client."""
        logger.info(f"Initializing ChromaDB at {settings.CHROMA_PERSIST_DIR}")
        
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR
        )
        self.embedding_fn_write = get_embedding_function()
        self.embedding_fn_query = get_embedding_function(task_type="RETRIEVAL_QUERY")

    def get_collection(self, name: str, is_query: bool = False):
        """Get or create a specific collection."""
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_fn_query if is_query else self.embedding_fn_write
        )

    def delete_collection(self, name: str):
        """DANGER: Deletes a collection."""
        try:
            self.client.delete_collection(name)
        except ValueError:
            logger.warning(f"Collection {name} does not exist.")

# Global instance for easy import
def get_chroma_db() : 
    chroma_db = ChromaClient()
    return chroma_db
