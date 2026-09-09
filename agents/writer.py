"""
Writer Agent - Synthesizes answer from all upstream agents.
Includes self-critique reflection loop and RAGAS scoring.
"""
from datetime import datetime
from langchain_groq import ChatGroq
from config.settings import get_settings
from config.logger import logger
from agents.state import AgentState

settings = get_settings()


WRITER_SYSTEM = """You are the final synthesis agent. Your job is to:
1. Take all upstream agent outputs
2. Synthesize a comprehensive, accurate answer
3. Include citations from retrieved documents
4. Be clear, concise, and factual

Format your response with:
- Main answer (1-2 paragraphs)
- Key findings (bulleted list)
- Sources (numbered citations)
"""


REFLECTION_SYSTEM = """You are a critical evaluator. Review the draft answer and score it on:
1. Completeness: Does it fully address the query? (0-10)
2. Factual Grounding: Is it grounded in source material? (0-10)
3. Clarity: Is it well-written and easy to understand? (0-10)

If overall score >= 7.0, respond with: APPROVED

Otherwise, respond with specific improvements needed.
"""


def writer_node(state: AgentState) -> AgentState:
    """
    Writer node: synthesizes final answer with reflection loop.
    """
    logger.info("Writer: Synthesizing answer...")

    context = prepare_context(state)

    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.5,
    )

    try:
        # -----------------------------------------
        # Step 1: Generate draft
        # -----------------------------------------

        draft_prompt = f"""{WRITER_SYSTEM}

Query:
{state['query']}

Retrieved Context:
{context}

Code/Analysis Results:
{state.get('code_output') or 'None'}

Web Search Results:
{format_web_results(state.get('web_results') or [])}

Generate a comprehensive answer.

IMPORTANT:
- Answer the query directly.
- Use only information supported by the supplied context.
- Do not invent facts.
- Include citations.
"""

        draft_answer = llm.invoke(draft_prompt).content.strip()

        logger.info(
            f"Writer DRAFT: {draft_answer!r}"
        )

        logger.info(
            f"Writer DRAFT length: {len(draft_answer)}"
        )

        state["draft_answer"] = draft_answer

        # -----------------------------------------
        # Step 2: Reflection
        # -----------------------------------------

        final_answer = draft_answer

        reflection_prompt = f"""{REFLECTION_SYSTEM}

        Query:
        {state['query']}

        Retrieved Context:
        {context}

        Draft Answer:
        {final_answer}

        Evaluation:
        """

        reflection = llm.invoke(
            reflection_prompt
        ).content.strip()

        logger.info(f"Writer: Reflection: {reflection!r}")
        logger.info(f"Writer: Draft: {draft_answer!r}")
        logger.info(f"Writer: Reflection: {reflection!r}")

        # -----------------------------------------
        # Step 3: Refine if necessary
        # -----------------------------------------

        if reflection == "APPROVED":
            logger.info("Writer: Answer approved")
        else:
            logger.info(
                "Writer: Refining answer..."
            )

            refinement_prompt = f"""You are the final answer writer.

Original Query:
{state['query']}

Retrieved Context:
{context}

Current Draft Answer:
{final_answer}

Reviewer Feedback:
{reflection}

Improve the current draft using the reviewer feedback.

IMPORTANT:
- Answer the ORIGINAL QUERY.
- Preserve correct information from the draft.
- Use ONLY information supported by the retrieved context.
- Do not invent facts.
- Include citations where appropriate.
- Return ONLY the final answer.
- Do not return reviewer comments.
- Do not return a score.
- Do not return JSON unless explicitly requested.

Improved Final Answer:
"""

            refined_answer = llm.invoke(
                refinement_prompt
            ).content.strip()

            # Safety check: don't replace a valid answer
            # with an obviously invalid empty response.
            if refined_answer:
                final_answer = refined_answer
            else:
                logger.warning(
                    "Writer: Refinement returned empty answer; "
                    "keeping draft"
                )
            
        # -----------------------------------------
        # Step 4: Save final answer
        # -----------------------------------------

        state["final_answer"] = final_answer

        # Temporary placeholder
        state["confidence"] = 0.85

        state["agent_trace"].append({
            "agent": "writer",
            "timestamp": datetime.utcnow().isoformat(),
            "input_summary": (
                f"Synthesizing from "
                f"{len(state['retrieved_chunks'])} chunks"
            ),
            "output_summary": (
                f"Generated "
                f"{len(final_answer)} char answer"
            ),
            "duration_ms": 0,
            "token_count": 0,
        })

        logger.info(
            f"Writer: Final answer ready "
            f"({len(final_answer)} chars)"
        )

        return state

    except Exception as e:
        logger.exception(
            "Writer error"
        )

        state["errors"].append(
            f"Writer error: {str(e)}"
        )

        state["final_answer"] = (
            "An error occurred while generating the answer."
        )

        state["confidence"] = 0.0

        return state

def prepare_context(state: AgentState) -> str:
    """Format retrieved chunks for context."""
    if not state['retrieved_chunks']:
        return "No relevant documents found."
    
    context_parts = []
    for i, chunk in enumerate(state['retrieved_chunks'], 1):
        citation = chunk["citation"]

        context_parts.append(
            f"[{i}] {chunk['text']}\n"
            f"(Source: {citation['source']}, "
            f"Page: {citation.get('page')}, "
            f"Chunk: {citation.get('chunk_index')})"
        )
    
    return "\n\n".join(context_parts)


def format_web_results(web_results: list) -> str:
    """Format web search results for context."""
    if not web_results:
        return "None"
    
    results_text = []
    for result in web_results[:5]:  # Top 5
        results_text.append(f"- {result.get('title', 'No title')}: {result.get('snippet', '')}")
    
    return "\n".join(results_text)
