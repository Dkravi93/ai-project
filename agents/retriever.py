"""
Retriever Agent - Handles document ingestion and hybrid retrieval.
Uses Qdrant for dense retrieval + BM25 for re-ranking.
"""
from typing import Optional
from datetime import datetime
import hashlib
from config.settings import get_settings
from config.logger import logger
from agents.state import AgentState, RetrievedChunk, Citation
from qdrant_client.models import PointStruct
from rag import get_qdrant_manager

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:  # pragma: no cover - optional local model dependency
    SentenceTransformer = None
    logger.warning(f"sentence-transformers unavailable, using hash embeddings: {e}")

try:
    from rank_bm25 import BM25Okapi
except Exception as e:  # pragma: no cover - optional local dependency
    BM25Okapi = None
    logger.warning(f"rank-bm25 unavailable, using lexical overlap reranking: {e}")

settings = get_settings()

qdrant_mgr = get_qdrant_manager()

_embedding_model = None


def _hash_embedding(text: str) -> list[float]:
    """Deterministic lightweight fallback embedding for local smoke tests."""
    vector = [0.0] * settings.embedding_dim
    for token in text.lower().split():
        digest = hashlib.md5(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % settings.embedding_dim
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


def _get_embedding_model():
    global _embedding_model
    if SentenceTransformer is None:
        return None
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def embed_query(text: str) -> list[float]:
    model = _get_embedding_model()
    if model is None:
        return _hash_embedding(text)
    return model.encode(text, convert_to_tensor=False).tolist()


def embed_documents(chunks: list[str]) -> list[list[float]]:
    model = _get_embedding_model()
    if model is None:
        return [_hash_embedding(chunk) for chunk in chunks]
    return [embedding.tolist() for embedding in model.encode(chunks, show_progress_bar=False, convert_to_tensor=False)]


def lexical_scores(texts: list[str], query: str) -> list[float]:
    query_tokens = set(query.lower().split())
    if not query_tokens:
        return [0.0 for _ in texts]
    scores = []
    for text in texts:
        text_tokens = set(text.lower().split())
        scores.append(len(query_tokens & text_tokens) / len(query_tokens))
    return scores


def retriever_node(state: AgentState) -> AgentState:
    """
    Retriever node: performs hybrid search (dense + BM25).
    Returns top-5 chunks with citations.
    """
    query = state['query']
    logger.info(f"Retriever: Searching for '{query[:50]}...'")
    
    try:
        # Step 1: Embed the query
        query_embedding = embed_query(query)
        
        # Step 2: Dense retrieval from Qdrant (top 20)
        logger.debug("Retriever: Performing dense retrieval...")
        search_results = qdrant_mgr.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_embedding,
            limit=20,
        )
        
        if not search_results:
            logger.warning("Retriever: No results found in Qdrant")
            state['retrieved_chunks'] = []
            return state
        
        # Step 3: Extract texts for BM25 re-ranking
        chunks_data = []
        for result in search_results:
            payload = result.get("payload") or {}
            text = payload.get("text", "")
            chunks_data.append({
                'id': result.get("id"),
                'text': text,
                'score': result.get("score", 0.0),
                'payload': payload,
            })
        
        # Step 4: BM25 re-ranking
        logger.debug("Retriever: Applying BM25 re-ranking...")
        texts = [c['text'] for c in chunks_data]
        if BM25Okapi is not None:
            bm25 = BM25Okapi([text.split() for text in texts])
            query_tokens = query.lower().split()
            bm25_scores = bm25.get_scores(query_tokens)
        else:
            bm25_scores = lexical_scores(texts, query)
        
        # Combine scores (60% dense, 40% BM25)
        combined_scores = []
        for i, chunk in enumerate(chunks_data):
            # Normalize scores
            dense_score = (chunk['score'] + 1) / 2  # Map [-1, 1] to [0, 1]
            bm25_score = bm25_scores[i] / (max(bm25_scores) + 1e-6)  # Normalize
            combined = 0.6 * dense_score + 0.4 * bm25_score
            combined_scores.append((i, combined))
        
        # Sort by combined score
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Step 5: Return top 5 with citations
        retrieved_chunks = []
        for rank, (idx, score) in enumerate(combined_scores[:5]):
            chunk = chunks_data[idx]
            citation = Citation(
                source=chunk['payload'].get('source', 'unknown'),
                page=chunk['payload'].get('page', None),
                chunk_index=chunk['payload'].get('chunk_index', idx),
            )
            retrieved_chunks.append(RetrievedChunk(
                text=chunk['text'][:500],  # Limit text length
                citation=citation,
                relevance_score=score,
                embedding_distance=chunk['score'],
            ))
        
        state['retrieved_chunks'] = retrieved_chunks
        
        logger.info(f"Retriever: Found {len(retrieved_chunks)} relevant chunks")
        state['agent_trace'].append({
            'agent': 'retriever',
            'timestamp': datetime.utcnow().isoformat(),
            'input_summary': f"Query: {query[:50]}...",
            'output_summary': f"Retrieved {len(retrieved_chunks)} chunks",
            'duration_ms': 0,
            'token_count': 0,
        })
        
        return state
        
    except Exception as e:
        logger.error(f"Retriever error: {str(e)}")
        state['errors'].append(f"Retriever error: {str(e)}")
        state['retrieved_chunks'] = []
        return state


def ingest_document(
    file_path: str,
    file_content: str,
    doc_id: Optional[str] = None,
    source_name: str = "document",
) -> dict:
    """
    Ingest a document: chunk, embed, and store in Qdrant.
    
    Args:
        file_path: Path or name of file
        file_content: Full text content
        doc_id: Optional document ID (generated if not provided)
        source_name: Name of source
        
    Returns:
        Ingestion result with doc_id and chunks_indexed
    """
    logger.info(f"Ingesting document: {file_path}")
    
    # Generate doc_id if not provided
    if not doc_id:
        doc_id = hashlib.md5(file_content.encode()).hexdigest()[:8]
    
    try:
        # Step 1: Chunk the document
        chunks = chunk_document(file_content, chunk_size=512, overlap=64)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 2: Embed chunks
        embeddings = embed_documents(chunks)
        
        # Step 3: Store in Qdrant
        qdrant_mgr.create_collection(settings.qdrant_collection_name)
        points = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=int(hashlib.md5(f"{doc_id}_{i}".encode()).hexdigest(), 16) % (2**63),
                    vector=embedding,
                    payload={
                    'text': chunk_text,
                    'source': source_name,
                    'doc_id': doc_id,
                    'chunk_index': i,
                    'created_at': datetime.utcnow().isoformat(),
                    },
                )
            )
        
        # Upsert to Qdrant
        qdrant_mgr.add_points_batch(
            collection_name=settings.qdrant_collection_name,
            points=points,
        )
        
        logger.info(f"Stored {len(points)} points in Qdrant")
        return {
            'doc_id': doc_id,
            'chunks_indexed': len(chunks),
            'embedding_model': settings.embedding_model,
            'embedding_fallback': SentenceTransformer is None,
        }
        
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise


def chunk_document(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Simple chunking by character count with overlap."""
    chunks = []
    step = chunk_size - overlap
    
    for i in range(0, len(text), step):
        chunk = text[i:i+chunk_size]
        if len(chunk) > 50:  # Skip tiny chunks
            chunks.append(chunk)
    
    return chunks
