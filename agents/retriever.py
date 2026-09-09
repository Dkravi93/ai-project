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

def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> dict[str, float]:

    scores = {}

    for ranked_list in ranked_lists:
        for rank, chunk_id in enumerate(ranked_list, start=1):
            scores[chunk_id] = (
                scores.get(chunk_id, 0.0)
                + 1.0 / (k + rank)
            )

    return scores


def retriever_node(state: AgentState) -> AgentState:
    """
    Retriever node: performs hybrid search (dense + BM25).
    Returns top-5 chunks with citations.
    """
    # GUARD: If retriever already failed, skip to avoid infinite loops
    for err in state.get("errors", []):
        if "Retriever error" in err:
            logger.warning("Retriever: Skipping (previously failed)")
            state["retrieved_chunks"] = []
            return state

    query = state["query"]
    logger.info(f"Retriever: Searching for '{query[:50]}...'")

    try:
        # Step 1: Embed the query
        query_embedding = embed_query(query)

        # Step 2: Dense retrieval from Qdrant (top 20)
        logger.debug("Retriever: Performing dense retrieval...")

        # If doc_ids were provided upstream, restrict retrieval to those documents.
        doc_ids = state.get("doc_ids") or []
        qdrant_filter = None

        if doc_ids:
            try:
                from qdrant_client.models import (
                    Filter as QdrantFilter,
                    FieldCondition,
                    MatchAny,
                )

                qdrant_filter = QdrantFilter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchAny(any=doc_ids),
                        )
                    ]
                )

            except ImportError:
                # Fallback: dict format that Qdrant Pydantic models understand
                qdrant_filter = {
                    "must": [
                        {
                            "key": "doc_id",
                            "match": {
                                "any": doc_ids
                            },
                        }
                    ]
                }

        # ---------------------------------------------------------
        # Step 2: Dense retrieval from Qdrant
        # ---------------------------------------------------------

        search_results = qdrant_mgr.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_embedding,
            limit=50,
            query_filter=qdrant_filter,
        )

        if not search_results:
            logger.warning(
                "Retriever: No results found in Qdrant"
            )

            state["retrieved_chunks"] = []
            return state


        # ---------------------------------------------------------
        # Step 3: Prepare dense candidates
        # ---------------------------------------------------------

        chunks_data = []

        for result in search_results:

            payload = result.get("payload") or {}

            text = payload.get("text", "")

            raw_score = result.get(
                "score",
                0.0,
            )

            score = float(raw_score)

            chunks_data.append(
                {
                    "id": str(result.get("id")),
                    "text": str(text),
                    "score": score,
                    "payload": payload,
                }
            )


        # ---------------------------------------------------------
        # Step 4: BM25
        # ---------------------------------------------------------

        texts = [
            chunk["text"]
            for chunk in chunks_data
        ]

        if BM25Okapi is not None:

            bm25 = BM25Okapi(
                [
                    text.lower().split()
                    for text in texts
                ]
            )

            query_tokens = query.lower().split()

            bm25_scores = [
                float(score)
                for score in bm25.get_scores(
                    query_tokens
                ).tolist()
            ]

        else:

            bm25_scores = [
                float(score)
                for score in lexical_scores(
                    texts,
                    query,
                )
            ]


        # ---------------------------------------------------------
        # Step 5: Dense ranking
        # ---------------------------------------------------------

        dense_ranked_ids = [
            str(chunk["id"])
            for chunk in chunks_data
        ]


        # ---------------------------------------------------------
        # Step 6: BM25 ranking
        # ---------------------------------------------------------

        bm25_ranked_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True,
        )

        bm25_ranked_ids = [
            str(chunks_data[i]["id"])
            for i in bm25_ranked_indices
        ]


        # ---------------------------------------------------------
        # Step 7: RRF
        # ---------------------------------------------------------

        rrf_scores = reciprocal_rank_fusion(
            [
                dense_ranked_ids,
                bm25_ranked_ids,
            ],
            k=60,
        )


        # ---------------------------------------------------------
        # Step 8: Combined ranking
        # ---------------------------------------------------------

        ranked_ids = sorted(
            rrf_scores.keys(),
            key=lambda chunk_id: rrf_scores[chunk_id],
            reverse=True,
        )


        logger.info(
            "Retriever rankings:\n"
            f"Dense: {dense_ranked_ids[:10]}\n"
            f"BM25:  {bm25_ranked_ids[:10]}\n"
            f"RRF:   {ranked_ids[:10]}"
        )


        # ---------------------------------------------------------
        # Step 9: Map IDs back to chunks
        # ---------------------------------------------------------

        chunks_by_id = {
            str(chunk["id"]): chunk
            for chunk in chunks_data
        }


        # ---------------------------------------------------------
        # Step 10: Return top 5
        # ---------------------------------------------------------

        retrieved_chunks = []

        for rank, chunk_id in enumerate(
            ranked_ids[:5],
            start=1,
        ):

            chunk = chunks_by_id.get(chunk_id)

            if not chunk:
                continue

            payload = chunk.get("payload") or {}

            source = str(
                payload.get(
                    "source",
                    "unknown",
                )
            )

            page = payload.get("page")

            if page is not None:
                try:
                    page = int(page)
                except (TypeError, ValueError):
                    pass

            chunk_index = payload.get(
                "chunk_index",
                0,
            )

            if chunk_index is not None:
                try:
                    chunk_index = int(chunk_index)
                except (TypeError, ValueError):
                    pass

            citation = Citation(
                source=source,
                page=page,
                chunk_index=chunk_index,
            )

            retrieved_chunks.append(
                RetrievedChunk(
                    # DO NOT truncate
                    text=str(chunk["text"]),

                    citation=citation,

                    relevance_score=float(
                        rrf_scores[chunk_id]
                    ),

                    embedding_distance=float(
                        chunk["score"]
                    ),
                )
            )


        state["retrieved_chunks"] = retrieved_chunks

        return state

    except Exception as e:
        logger.exception(
            "Retriever error"
        )

        state["errors"].append(
            f"Retriever error: {str(e)}"
        )

        state["retrieved_chunks"] = []

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
        chunks = chunk_document(file_content, chunk_size=1200, overlap=64)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 2: Embed chunks
        embeddings = embed_documents(chunks)
        
        # Step 3: Store in Qdrant
        collection_ready = qdrant_mgr.create_collection(settings.qdrant_collection_name)
        if not collection_ready:
            logger.error(f"Failed to create/verify collection '{settings.qdrant_collection_name}' - Qdrant may not be running")
            return {
                'doc_id': doc_id,
                'chunks_indexed': 0,
                'error': f'Qdrant collection creation failed - check Qdrant server is running at {settings.qdrant_host}:{settings.qdrant_port}',
                'embedding_model': settings.embedding_model,
                'embedding_fallback': SentenceTransformer is None,
            }
        
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
        stored = qdrant_mgr.add_points_batch(
            collection_name=settings.qdrant_collection_name,
            points=points,
        )
        
        if not stored:
            logger.error(f"Failed to store {len(points)} points in Qdrant")
            return {
                'doc_id': doc_id,
                'chunks_indexed': 0,
                'error': 'Qdrant upsert failed - check Qdrant server is running',
                'embedding_model': settings.embedding_model,
                'embedding_fallback': SentenceTransformer is None,
            }
        
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


def chunk_document(text: str, chunk_size: int = 1200, overlap: int = 64) -> list[str]:
    """Simple chunking by character count with overlap."""
    chunks = []
    step = chunk_size - overlap
    
    for i in range(0, len(text), step):
        chunk = text[i:i+chunk_size]
        if len(chunk) > 50:  # Skip tiny chunks
            chunks.append(chunk)
    
    return chunks
