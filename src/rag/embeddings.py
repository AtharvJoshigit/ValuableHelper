from chromadb.utils import embedding_functions
from rag.config import settings
import logging

logger = logging.getLogger(__name__)

def get_embedding_function(**kwargs):
    """
    Factory to return the appropriate ChromaDB embedding function 
    based on configuration.
    """
    provider = settings.EMBEDDING_PROVIDER.lower()
    
    try:
        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not set.")
            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.EMBEDDING_MODEL_NAME
            )
            
        elif provider == "gemini" or provider == "google":
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set.")
            return embedding_functions.GoogleGenerativeAiEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL_NAME,
                api_key=settings.GEMINI_API_KEY,
                task_type=kwargs.get("task_type", "RETRIEVAL_DOCUMENT")
            )
            
        elif provider == "sentence-transformers":
            # Default local fallback
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL_NAME
            )
            
        else:
            logger.warning(f"Unknown provider '{provider}', falling back to default.")
            return embedding_functions.DefaultEmbeddingFunction()
            
    except Exception as e:
        logger.error(f"Failed to initialize embedding function: {e}")
        raise e
