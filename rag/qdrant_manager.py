"""
Qdrant Vector Database Setup and Management.
Handles collection creation, deletion, and schema validation.
"""
import socket
from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from config.logger import logger
from config.settings import get_settings

settings = get_settings()


class QdrantManager:
    """Manager for Qdrant vector database operations."""
    
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            timeout=settings.qdrant_timeout_seconds,
        )
        logger.info(f"QdrantManager initialized: {settings.qdrant_host}:{settings.qdrant_port}")
    
    def get_client(self) -> QdrantClient:
        """Get the Qdrant client."""
        return self.client
    
    def health_check(self) -> bool:
        """Check if Qdrant server is healthy."""
        try:
            with socket.create_connection(
                (settings.qdrant_host, settings.qdrant_port),
                timeout=settings.qdrant_timeout_seconds,
            ):
                pass
            self.client.get_collections()
            logger.info("Qdrant health check passed")
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    def create_collection(
        self,
        collection_name: str = None,
        vector_size: int = None,
        distance_metric: str = "cosine",
    ) -> bool:
        """
        Create a new Qdrant collection for document embeddings.
        
        Args:
            collection_name: Name of collection (default: settings.qdrant_collection_name)
            vector_size: Dimension of embeddings (default: settings.embedding_dim)
            distance_metric: Distance metric ('cosine', 'euclidean', 'manhattan')
        """
        collection_name = collection_name or settings.qdrant_collection_name
        vector_size = vector_size or settings.embedding_dim
        
        if self.collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        
        try:
            distance_map = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "manhattan": Distance.MANHATTAN,
            }
            distance = distance_map.get(distance_metric, Distance.COSINE)
            
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance,
                ),
            )
            
            logger.info(
                f"Collection '{collection_name}' created: "
                f"{vector_size}D vectors, {distance_metric} distance"
            )
            self.ensure_payload_indexes(collection_name)
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def ensure_default_collection(self) -> Dict:
        """Create the configured collection if needed and return its status."""
        collection_name = settings.qdrant_collection_name
        created = self.create_collection(collection_name)
        info = self.get_collection_info(collection_name) if created else {}
        return {
            "ready": created,
            "collection": collection_name,
            "vector_size": settings.embedding_dim,
            "info": info,
        }

    def ensure_payload_indexes(self, collection_name: str = None) -> None:
        """Create useful payload indexes when the Qdrant version supports them."""
        collection_name = collection_name or settings.qdrant_collection_name
        for field_name in ("doc_id", "source", "created_at"):
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema="keyword",
                )
            except Exception as e:
                logger.debug(f"Payload index skipped for {field_name}: {e}")
    
    def delete_collection(self, collection_name: str = None) -> bool:
        """Delete a collection."""
        collection_name = collection_name or settings.qdrant_collection_name
        
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Collection '{collection_name}' deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False
    
    def get_collection_info(self, collection_name: str = None) -> Dict:
        """Get collection info and statistics."""
        collection_name = collection_name or settings.qdrant_collection_name
        
        try:
            collection_info = self.client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "points_count": collection_info.points_count,
                "vectors_config": str(collection_info.config.params.vectors),
                "indexed_vectors_count": collection_info.indexed_vectors_count,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
    
    def add_point(
        self,
        collection_name: str,
        point_id: int,
        vector: List[float],
        payload: Dict,
    ) -> bool:
        """Add a single point to collection."""
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add point: {e}")
            return False
    
    def add_points_batch(
        self,
        collection_name: str,
        points: List[PointStruct],
    ) -> bool:
        """Add multiple points to collection."""
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.debug(f"Added {len(points)} points to '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to add points batch: {e}")
            return False
    
    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = None,
    ) -> List[Dict]:
        """
        Search for similar vectors.
        
        Returns list of results with id, score, payload.
        """
        try:
            if hasattr(self.client, "search"):
                results = self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                )
            else:
                response = self.client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                    score_threshold=score_threshold,
                )
                results = response.points
            
            return [
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload,
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete_point(
        self,
        collection_name: str,
        point_id: int,
    ) -> bool:
        """Delete a single point."""
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=[point_id],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete point: {e}")
            return False
    
    def clear_collection(self, collection_name: str = None) -> bool:
        """Clear all points from collection (keep structure)."""
        collection_name = collection_name or settings.qdrant_collection_name
        
        try:
            # Get all points and delete them
            # For large collections, better to recreate
            self.delete_collection(collection_name)
            self.create_collection(collection_name)
            logger.info(f"Collection '{collection_name}' cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False


# Singleton instance
_qdrant_manager = None


def get_qdrant_manager() -> QdrantManager:
    """Get or create Qdrant manager singleton."""
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager
