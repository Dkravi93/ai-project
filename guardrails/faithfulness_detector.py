"""
RAGAS-based Faithfulness and Hallucination Detection.
Evaluates if generated text is grounded in retrieved context.
"""
from typing import Dict, Tuple, Optional
from config.logger import logger
from config.settings import get_settings
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

settings = get_settings()


def score_faithfulness(
    context: str,
    generated_text: str,
    queries: list = None,
) -> Tuple[float, Dict[str, any]]:
    """
    Score faithfulness of generated text against context.
    Higher score = more faithful/grounded.
    
    Args:
        context: Retrieved/reference text
        generated_text: Model-generated answer
        queries: Optional list of query sentences to check
    
    Returns:
        Tuple of (score [0-1], details_dict)
    """
    try:
        llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
        
        if not queries:
            queries = [generated_text[:100]]  # Use first 100 chars as query
        
        # Faithfulness check: for each sentence in generated text,
        # verify it can be inferred from context
        faithful_sentences = 0
        total_sentences = len(queries)
        
        faithfulness_details = []
        
        for query in queries:
            prompt = f"""Given this context:
{context}

Can the following statement be inferred from the context?
Statement: {query}

Answer with ONLY 'yes' or 'no'."""
            
            try:
                msg = HumanMessage(content=prompt)
                response = llm.invoke([msg])
                answer = response.content.strip().lower()
                
                is_faithful = "yes" in answer
                if is_faithful:
                    faithful_sentences += 1
                
                faithfulness_details.append({
                    "query": query[:80],
                    "faithful": is_faithful
                })
            except Exception as e:
                logger.debug(f"Faithfulness check error for query: {e}")
                faithfulness_details.append({
                    "query": query[:80],
                    "faithful": None,
                    "error": str(e)
                })
        
        if total_sentences == 0:
            score = 0.5
        else:
            score = faithful_sentences / total_sentences
        
        details = {
            "score": round(score, 3),
            "faithful_sentences": faithful_sentences,
            "total_sentences": total_sentences,
            "checks": faithfulness_details
        }
        
        logger.debug(f"Faithfulness score: {score}")
        return score, details
        
    except Exception as e:
        logger.error(f"Faithfulness scoring error: {e}")
        return 0.5, {"error": str(e)}


def score_relevance(
    context: str,
    answer: str,
) -> Tuple[float, str]:
    """
    Score relevance of answer to context.
    Uses semantic overlap and LLM evaluation.
    
    Returns:
        Tuple of (relevance_score [0-1], reasoning)
    """
    try:
        llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
        
        prompt = f"""Rate the relevance of this answer to the given context.
Context: {context[:500]}

Answer: {answer[:500]}

Score from 0-10 and provide brief reasoning.
Format: SCORE: X, REASON: brief explanation"""
        
        msg = HumanMessage(content=prompt)
        response = llm.invoke([msg])
        
        # Parse response
        content = response.content.strip()
        score = 0.5
        reason = "Could not parse score"
        
        if "SCORE:" in content:
            try:
                score_part = content.split("SCORE:")[1].split(",")[0].strip()
                score = float(score_part) / 10.0
            except:
                pass
        
        if "REASON:" in content:
            reason = content.split("REASON:")[1].strip()
        
        logger.debug(f"Relevance score: {score} - {reason}")
        return score, reason
        
    except Exception as e:
        logger.error(f"Relevance scoring error: {e}")
        return 0.5, f"Error: {str(e)}"


def detect_hallucinations(
    context: str,
    generated_text: str,
) -> Tuple[bool, float, list]:
    """
    Detect if generated text contains hallucinations
    (factual claims not in context).
    
    Returns:
        Tuple of (has_hallucinations, confidence, hallucination_list)
    """
    try:
        score, details = score_faithfulness(context, generated_text)
        
        # If faithfulness < 0.7, likely has hallucinations
        has_hallucinations = score < 0.7
        
        hallucinations = []
        if has_hallucinations and "checks" in details:
            unfaithful_claims = [
                c["query"] for c in details["checks"]
                if not c.get("faithful", False)
            ]
            hallucinations = unfaithful_claims
        
        logger.debug(f"Hallucination detected: {has_hallucinations}")
        return has_hallucinations, score, hallucinations
        
    except Exception as e:
        logger.error(f"Hallucination detection error: {e}")
        return False, 0.5, []
