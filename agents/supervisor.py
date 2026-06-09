"""
Supervisor Agent - Orchestrates LangGraph execution.
Routes queries to appropriate agents based on query intent.
"""
from typing import Literal
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage
from config.settings import get_settings
from config.logger import logger
from agents.state import AgentState
from datetime import datetime

settings = get_settings()


class TaskPlan(BaseModel):
    """Structured output: supervisor's task plan."""
    
    reasoning: str = Field(description="Reasoning for the plan")
    steps: list[str] = Field(
        description="Ordered list of agent names to invoke: 'retriever', 'coder', 'web_search', 'writer'"
    )
    confidence: float = Field(description="Confidence in plan (0.0-1.0)")


# System prompt for supervisor
SUPERVISOR_SYSTEM = """You are the supervisor agent for a multi-agent system. Your job is to:
1. Analyze the user's query
2. Determine which agents are needed
3. Order them logically

Available agents:
- retriever: Searches documents for relevant context
- coder: Executes Python or SQL code
- web_search: Fetches live web data
- writer: Synthesizes final answer

Rules:
- Always end with 'writer' agent
- Retriever is almost always needed (unless pure coding/computation)
- Web search is for real-time data needs
- Coder is for data analysis, calculations, or code execution
- Keep steps minimal (2-4 steps typically)
"""


def supervisor_node(state: AgentState) -> AgentState:
    """Supervisor node: analyzes query and creates task plan."""
    logger.info(f"Supervisor: Processing query: {state['query'][:50]}...")
    
    # Initialize LLM
    llm = ChatGroq(
        model="mixtral-8x7b-32768",
        api_key=settings.groq_api_key,
        temperature=0.3,
    )
    
    # Create structured output
    structured_llm = llm.with_structured_output(TaskPlan)
    
    # Build prompt
    user_query = state['query']
    messages = [
        ("system", SUPERVISOR_SYSTEM),
        ("user", f"Query: {user_query}"),
    ]
    
    try:
        plan = structured_llm.invoke(messages)
        state['plan'] = plan.steps
        state['attempt_count'] = 0
        
        state['agent_trace'].append({
            'agent': 'supervisor',
            'timestamp': datetime.utcnow().isoformat(),
            'input_summary': f"Query: {user_query[:50]}...",
            'output_summary': f"Plan: {' -> '.join(plan.steps)}",
            'duration_ms': 0,
            'token_count': 0,
        })
        
        logger.info(f"Supervisor: Plan created with {len(plan.steps)} steps")
        return state
        
    except Exception as e:
        logger.error(f"Supervisor error: {str(e)}")
        state['errors'].append(f"Supervisor error: {str(e)}")
        state['plan'] = ['writer']
        return state


def route_next_agent(state: AgentState) -> str:
    """Routing function: determines next agent to execute."""
    if state['attempt_count'] > 3:
        logger.warning("Max attempts reached, routing to writer")
        return 'writer'
    
    if state['plan']:
        next_agent = state['plan'].pop(0)
        logger.info(f"Routing to: {next_agent}")
        return next_agent
    
    logger.info("Plan complete, routing to writer")
    return 'writer'
