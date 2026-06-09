"""
LangGraph State Machine - Orchestrates multi-agent execution.
Defines graph structure with conditional routing and cycles.
"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from config.logger import logger
from agents.state import AgentState
from agents.supervisor import supervisor_node, route_next_agent
from agents.retriever import retriever_node
from agents.coder import coder_node
from agents.web_search import web_search_node
from agents.writer import writer_node


def create_graph():
    """
    Create the LangGraph state machine.
    
    Graph structure:
    supervisor ? (conditional routing) ? agents ? back to supervisor
                                      ? writer ? END
    """
    logger.info("Creating LangGraph state machine...")
    
    # Create state graph
    graph = StateGraph(AgentState)
    
    # Add all nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("coder", coder_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("writer", writer_node)
    
    # Set entry point
    graph.set_entry_point("supervisor")
    
    # Supervisor routes to next agent
    graph.add_conditional_edges(
        "supervisor",
        route_next_agent,
        {
            "retriever": "retriever",
            "coder": "coder",
            "web_search": "web_search",
            "writer": "writer",
        }
    )
    
    # All agents (except writer) return to supervisor
    graph.add_edge("retriever", "supervisor")
    graph.add_edge("coder", "supervisor")
    graph.add_edge("web_search", "supervisor")
    
    # Writer is terminal
    graph.add_edge("writer", END)
    
    # Compile graph with memory checkpointer
    logger.info("Compiling LangGraph...")
    compiled_graph = graph.compile(checkpointer=MemorySaver())
    
    logger.info("? LangGraph created successfully")
    return compiled_graph


# Global graph instance
_graph = None


def get_graph():
    """Get or create the graph."""
    global _graph
    if _graph is None:
        _graph = create_graph()
    return _graph


def run_agent_graph(
    query: str,
    session_id: str,
    doc_ids: list = None,
    trace_id: str = None,
) -> dict:
    """
    Run the agent graph on a query.
    
    Args:
        query: User query
        session_id: Unique session identifier
        doc_ids: Optional list of document IDs to use
        trace_id: Optional trace ID for observability
        
    Returns:
        Final state with answer, citations, and metrics
    """
    from datetime import datetime
    
    logger.info(f"Starting agent run: {query[:50]}...")
    
    # Initialize state
    initial_state = AgentState(
        messages=[],
        query=query,
        plan=[],
        retrieved_chunks=[],
        code_output=None,
        web_results=None,
        draft_answer=None,
        final_answer=None,
        confidence=None,
        answer_relevance=None,
        faithfulness=None,
        guardrail_flags=[],
        pii_detected=False,
        toxicity_score=None,
        token_count=0,
        total_latency_ms=0,
        trace_id=trace_id or f"trace_{session_id}_{int(datetime.utcnow().timestamp())}",
        session_id=session_id,
        doc_ids=doc_ids or [],
        require_hitl=False,
        human_approved=None,
        errors=[],
        attempt_count=0,
        agent_trace=[],
    )
    
    # Run graph
    graph = get_graph()
    
    try:
        start_time = datetime.utcnow()
        final_state = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
        )
        end_time = datetime.utcnow()
        
        final_state['total_latency_ms'] = (end_time - start_time).total_seconds() * 1000
        
        logger.info(f"? Agent run completed in {final_state['total_latency_ms']:.0f}ms")
        return final_state
        
    except Exception as e:
        logger.error(f"Agent graph error: {str(e)}")
        initial_state['errors'].append(f"Graph execution error: {str(e)}")
        return initial_state
