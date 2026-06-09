"""
Shared agent state schema for LangGraph execution.
Defines all fields that flow through the multi-agent system.
"""
from typing import TypedDict, Optional, Any
from datetime import datetime


class Citation(TypedDict):
    """Source citation metadata."""
    source: str              # filename or URL
    page: Optional[int]      # page number if available
    chunk_index: int        # which chunk within source


class AgentStep(TypedDict):
    """Record of a single agent node execution."""
    agent: str              # agent name (supervisor, retriever, coder, etc.)
    timestamp: datetime
    input_summary: str
    output_summary: str
    duration_ms: float
    token_count: int


class RetrievedChunk(TypedDict):
    """A retrieved document chunk with citation."""
    text: str
    citation: Citation
    relevance_score: float
    embedding_distance: Optional[float]


class AgentState(TypedDict):
    """Main state object flowing through LangGraph execution."""
    
    # Conversation
    messages: list[dict]        # full conversation history
    query: str                  # current user query
    
    # Orchestration
    plan: list[str]             # supervisor's ordered task list
    agent_trace: list[AgentStep]  # execution trace for UI
    
    # Retrieval
    retrieved_chunks: list[RetrievedChunk]  # RAG results with citations
    
    # Agent outputs
    code_output: Optional[str]      # coder agent result
    web_results: Optional[list[dict]]  # web search results
    draft_answer: Optional[str]     # writer pre-reflection
    final_answer: Optional[str]     # post-reflection answer
    
    # Quality metrics
    confidence: Optional[float]     # RAGAS faithfulness score (0-1)
    answer_relevance: Optional[float]  # RAGAS relevance score
    faithfulness: Optional[float]   # RAGAS faithfulness
    
    # Security & Compliance
    guardrail_flags: list[str]      # triggered guardrails
    pii_detected: bool              # if any PII was found
    toxicity_score: Optional[float] # detoxify output
    
    # Resource tracking
    token_count: int                # running token total
    total_latency_ms: float         # end-to-end latency
    
    # Observability
    trace_id: str                   # LangSmith trace ID
    session_id: str                 # user session ID
    doc_ids: list[str]              # document IDs used
    
    # Control flow
    require_hitl: bool              # human-in-the-loop required?
    human_approved: Optional[bool]  # human decision
    
    # Error handling
    errors: list[str]               # accumulated error messages
    attempt_count: int              # agent call attempts
