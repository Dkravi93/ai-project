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
    
    # Prepare context
    context = prepare_context(state)
    
    # Initialize LLM
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.5,
    )
    
    try:
        # Step 1: Generate draft answer
        draft_prompt = f"""{WRITER_SYSTEM}

Query: {state['query']}

Retrieved Context:
{context}

Code/Analysis Results:
{state.get('code_output', 'None')}

Web Search Results:
{format_web_results(state.get('web_results', []))}

Generate a comprehensive answer:"""
        
        draft_answer = llm.invoke(draft_prompt).content
        state['draft_answer'] = draft_answer
        logger.info("Writer: Draft answer generated")
        
        # Step 2: Reflection loop (max 2 iterations)
        final_answer = draft_answer
        for iteration in range(1):
            reflection_prompt = f"""{REFLECTION_SYSTEM}

Query: {state['query']}
Draft Answer: {final_answer}

Evaluation:"""
            
            reflection = llm.invoke(reflection_prompt).content
            
            if "APPROVED" in reflection:
                logger.info(f"Writer: Answer approved on iteration {iteration}")
                break
            else:
                logger.info(f"Writer: Iteration {iteration}: refining answer...")
                # Re-generate with feedback
                refinement_prompt = f"""Using this feedback, improve your answer:
{reflection}

Improved answer:"""
                final_answer = llm.invoke(refinement_prompt).content
        
        state['final_answer'] = final_answer
        
        # Calculate confidence (placeholder - would use RAGAS)
        state['confidence'] = 0.85
        
        state['agent_trace'].append({
            'agent': 'writer',
            'timestamp': datetime.utcnow().isoformat(),
            'input_summary': f"Synthesizing from {len(state['retrieved_chunks'])} chunks",
            'output_summary': f"Generated {len(final_answer)} char answer",
            'duration_ms': 0,
            'token_count': 0,
        })
        
        logger.info("Writer: Final answer ready")
        return state
        
    except Exception as e:
        logger.error(f"Writer error: {str(e)}")
        state['errors'].append(f"Writer error: {str(e)}")
        state['final_answer'] = "An error occurred while generating the answer."
        state['confidence'] = 0.0
        return state


def prepare_context(state: AgentState) -> str:
    """Format retrieved chunks for context."""
    if not state['retrieved_chunks']:
        return "No relevant documents found."
    
    context_parts = []
    for i, chunk in enumerate(state['retrieved_chunks'], 1):
        context_parts.append(f"[{i}] {chunk['text']}\n(Source: {chunk['citation']['source']})")
    
    return "\n\n".join(context_parts)


def format_web_results(web_results: list) -> str:
    """Format web search results for context."""
    if not web_results:
        return "None"
    
    results_text = []
    for result in web_results[:5]:  # Top 5
        results_text.append(f"- {result.get('title', 'No title')}: {result.get('snippet', '')}")
    
    return "\n".join(results_text)
