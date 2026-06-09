"""
RAG (Retrieval-Augmented Generation) module for AgentOps Hub.
Handles document ingestion, embedding, and retrieval with hybrid search.
"""
from rag.qdrant_manager import QdrantManager, get_qdrant_manager

__all__ = [
    "QdrantManager",
    "get_qdrant_manager",
]
