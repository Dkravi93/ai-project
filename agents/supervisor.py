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
- coder: Executes Python or SQL code (ONLY if the query explicitly asks for data analysis, calculations, or code generation)
- web_search: Fetches live web data (ONLY if the query asks for current/realtime information)
- writer: Synthesizes final answer

Rules:
- Always end with 'writer' agent
- Start with 'retriever' for document-grounded queries
- ONLY use 'coder' if the query literally asks to write/run/execute code or do computation
- ONLY use 'web_search' if the query needs current/real-time information
- Skip coder and web_search for general ask-your-documents questions
- Keep steps minimal (2-3 steps typically)
- Prefer: retriever -> writer for document QA
"""



def supervisor_node(state: AgentState) -> AgentState:
    """Supervisor node: analyzes query and creates task plan."""

    logger.info(
        f"Supervisor: Processing query: {state['query'][:50]}..."
    )

    # -----------------------------------------
    # 1. Handle previous failures
    # -----------------------------------------
    for err in state.get("errors", []):
        if (
            "Retriever error" in err
            or "Coder error" in err
            or "WebSearch error" in err
        ):
            logger.warning(
                f"Supervisor: Agent failure detected "
                f"({err[:60]}), routing directly to writer"
            )

            state["plan"] = ["writer"]

            state["agent_trace"].append({
                "agent": "supervisor",
                "timestamp": datetime.utcnow().isoformat(),
                "input_summary": f"Query: {state['query'][:50]}...",
                "output_summary": "Fallback plan: writer",
                "duration_ms": 0,
                "token_count": 0,
            })

            return state

    # -----------------------------------------
    # 2. Continue existing plan
    # -----------------------------------------
    if state.get("plan"):
        logger.info(
            f"Supervisor: Continuing existing plan "
            f"({' -> '.join(state['plan'])})"
        )
        return state

    # -----------------------------------------
    # 3. IMPORTANT:
    # Document QA always uses Retriever
    # -----------------------------------------
    doc_ids = state.get("doc_ids") or []

    logger.info(
        f"Supervisor: doc_ids={doc_ids}"
    )

    if doc_ids:
        logger.info(
            "Supervisor: Documents selected. "
            "Using deterministic document QA plan."
        )

        state["plan"] = [
            "retriever",
            "writer",
        ]

        state["agent_trace"].append({
            "agent": "supervisor",
            "timestamp": datetime.utcnow().isoformat(),
            "input_summary": f"Query: {state['query'][:50]}...",
            "output_summary": "Plan: retriever -> writer",
            "duration_ms": 0,
            "token_count": 0,
        })

        return state

    # -----------------------------------------
    # 4. No documents selected
    # Let LLM decide
    # -----------------------------------------
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.3,
    )

    structured_llm = llm.with_structured_output(TaskPlan)

    messages = [
        ("system", SUPERVISOR_SYSTEM),
        ("user", f"Query: {state['query']}"),
    ]

    try:
        plan = structured_llm.invoke(messages)

        state["plan"] = plan.steps

        state["agent_trace"].append({
            "agent": "supervisor",
            "timestamp": datetime.utcnow().isoformat(),
            "input_summary": f"Query: {state['query'][:50]}...",
            "output_summary": f"Plan: {' -> '.join(plan.steps)}",
            "duration_ms": 0,
            "token_count": 0,
        })

        logger.info(
            f"Supervisor: Plan created "
            f"{' -> '.join(plan.steps)}"
        )

        return state

    except Exception as e:
        error_message = str(e)

        if (
            "tool calling" in error_message.lower()
            or "tool_use" in error_message.lower()
        ):
            logger.warning(
                "Supervisor model does not support tool calling; "
                "using document-QA fallback plan"
            )

            state["plan"] = [
                "retriever",
                "writer",
            ]

            return state

        logger.exception("Supervisor error")

        state["errors"].append(
            f"Supervisor error: {str(e)}"
        )

        state["plan"] = ["writer"]

        return state


def route_next_agent(state: AgentState) -> str:
    """Determine next agent."""

    state["attempt_count"] = state.get("attempt_count", 0) + 1

    if state["attempt_count"] > 5:
        logger.warning("Max attempts reached -> writer")
        return "writer"

    if state.get("plan"):
        next_agent = state["plan"].pop(0)

        valid_agents = {
            "retriever",
            "coder",
            "web_search",
            "writer",
        }

        if next_agent not in valid_agents:
            logger.error(
                f"Invalid agent in plan: {next_agent}"
            )
            return "writer"

        logger.info(
            f"Routing to: {next_agent} "
            f"(attempt {state['attempt_count']})"
        )

        return next_agent

    return "writer"
