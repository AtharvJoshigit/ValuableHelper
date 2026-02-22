from typing import List, Dict, Any, Optional
from rag.client import get_chroma_db
from rag.schema import VectorDocument, SearchResult
import uuid

class BaseVectorStore:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.chrome_db = get_chroma_db()
        self.write_collection_emb = self.chrome_db.get_collection(collection_name)
        self.query_collection_emb = self.chrome_db.get_collection(collection_name, is_query=True)
    
    def add_documents(self, documents: List[VectorDocument]):
        """Batch add documents to the store."""
        if not documents:
            return
            
        ids = [doc.id for doc in documents]
        texts = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        
        self.write_collection_emb.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

    def search(self, query: str, n_results: int = 5, where: Optional[Dict] = None) -> List[SearchResult]:
        """
        Semantic search with optional metadata filtering.
        """
        results = self.query_collection_emb.query(
            query_texts=[query],
            n_results=n_results,
            where=where
        )
        
        # Parse Chroma's weird return format into clean objects
        parsed_results = []
        if results['ids']:
            # results is a dict of lists of lists. e.g., results['ids'][0] is the result for the first query.
            count = len(results['ids'][0])
            for i in range(count):
                parsed_results.append(SearchResult(
                    id=results['ids'][0][i],
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i] or {},
                    score=results['distances'][0][i] if results['distances'] else 0.0
                ))
                
        return parsed_results
        
    def delete(self, doc_id: str):
        self.collection.delete(ids=[doc_id])
    
    def clear(self):
        """Empty the collection."""
        # Note: Chroma doesn't have a truncate, so we delete by non-empty metadata or just delete collection
        # For safety, we usually just delete the whole collection via client and recreate
        self.chrome_db.delete_collection(self.collection_name)
        return
