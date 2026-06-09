"""
Unified Guardrails Middleware.
Orchestrates PII, toxicity, and faithfulness checks for input/output.
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from config.logger import logger
from config.settings import get_settings
from guardrails.pii_detector import detect_pii, redact_pii
from guardrails.toxicity_detector import detect_toxicity, get_toxicity_level, is_severe_toxicity
from guardrails.faithfulness_detector import detect_hallucinations, score_faithfulness
from guardrails.injection_detector import detect_prompt_injection

settings = get_settings()


@dataclass
class GuardrailResult:
    """Result of guardrails check."""
    passed: bool
    blocked: bool = False
    reason: Optional[str] = None
    cleaned_text: Optional[str] = None
    original_text: Optional[str] = None
    pii_detected: bool = False
    toxicity_score: float = 0.0
    toxicity_level: str = "clean"
    faithfulness_score: float = 1.0
    hallucinations_detected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for logging/response."""
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "reason": self.reason,
            "pii_detected": self.pii_detected,
            "toxicity_level": self.toxicity_level,
            "toxicity_score": round(self.toxicity_score, 3),
            "faithfulness_score": round(self.faithfulness_score, 3),
            "hallucinations_detected": self.hallucinations_detected,
            "metadata": self.metadata,
        }


class GuardrailsMiddleware:
    """Main guardrails middleware for input/output validation."""
    
    def __init__(
        self,
        pii_threshold: float = None,
        toxicity_threshold: float = None,
        min_faithfulness: float = None,
    ):
        self.pii_threshold = settings.pii_threshold if pii_threshold is None else pii_threshold
        self.toxicity_threshold = settings.toxicity_threshold if toxicity_threshold is None else toxicity_threshold
        self.min_faithfulness = settings.ragas_threshold if min_faithfulness is None else min_faithfulness
        logger.info("GuardrailsMiddleware initialized")
    
    async def check_input(self, query: str) -> GuardrailResult:
        """
        Run input guardrails: PII check, toxicity check, injection detection.
        """
        logger.debug(f"Running input guardrails on: {query[:50]}...")
        
        result = GuardrailResult(passed=True, original_text=query)
        
        # 1. Token budget estimate
        estimated_tokens = max(1, len(query) // 4)
        result.metadata["estimated_tokens"] = estimated_tokens
        if estimated_tokens > settings.token_hard_limit:
            result.blocked = True
            result.passed = False
            result.reason = f"Token budget exceeded: {estimated_tokens} > {settings.token_hard_limit}"
            logger.warning(result.reason)
            return result

        # 2. Prompt injection / unsafe instruction check
        injection_detected, injection_score, injection_meta = detect_prompt_injection(
            query,
            threshold=settings.prompt_injection_threshold,
        )
        result.metadata["prompt_injection"] = {
            "detected": injection_detected,
            "score": injection_score,
            **injection_meta,
        }
        if injection_detected:
            result.blocked = True
            result.passed = False
            result.reason = "Potential prompt injection detected"
            logger.warning(f"Input BLOCKED - prompt injection: {injection_meta}")
            return result

        # 3. Check for PII
        has_pii, pii_entities, _ = detect_pii(query, self.pii_threshold)
        result.pii_detected = has_pii
        
        if has_pii:
            logger.warning(f"Input PII detected: {len(pii_entities)} entities")
            result.metadata["pii_entities"] = pii_entities
            result.cleaned_text = redact_pii(query, self.pii_threshold)
            # Don't block on PII in input, but log it
        else:
            result.cleaned_text = query
        
        # 4. Check for toxicity
        is_toxic, tox_scores = detect_toxicity(query, self.toxicity_threshold)
        result.toxicity_score = max(tox_scores.values()) if tox_scores else 0.0
        result.toxicity_level = get_toxicity_level(tox_scores)
        
        if is_severe_toxicity(tox_scores, severity_threshold=settings.severe_toxicity_threshold):
            result.blocked = True
            result.passed = False
            result.reason = "Input contains severe toxic content"
            logger.warning(f"Input BLOCKED - severe toxicity: {result.toxicity_score}")
            return result
        
        result.metadata["toxicity_scores"] = tox_scores
        
        logger.debug(f"Input passed guardrails")
        return result
    
    async def check_output(
        self,
        answer: str,
        context: str = "",
        original_query: str = "",
    ) -> GuardrailResult:
        """
        Run output guardrails: PII redaction, toxicity check, faithfulness/hallucination check.
        """
        logger.debug(f"Running output guardrails on: {answer[:50]}...")
        
        result = GuardrailResult(passed=True, original_text=answer)
        
        # 1. Redact any PII in output
        has_pii, pii_entities, _ = detect_pii(answer, self.pii_threshold)
        result.pii_detected = has_pii
        
        if has_pii:
            logger.warning(f"Output PII detected: {len(pii_entities)} entities")
            result.cleaned_text = redact_pii(answer, self.pii_threshold)
            result.metadata["pii_entities"] = pii_entities
        else:
            result.cleaned_text = answer
        
        # 2. Check for toxicity
        is_toxic, tox_scores = detect_toxicity(answer, self.toxicity_threshold)
        result.toxicity_score = max(tox_scores.values()) if tox_scores else 0.0
        result.toxicity_level = get_toxicity_level(tox_scores)
        
        if is_severe_toxicity(tox_scores, severity_threshold=settings.severe_toxicity_threshold):
            result.blocked = True
            result.passed = False
            result.reason = "Output contains severe toxic content"
            logger.warning(f"Output BLOCKED - severe toxicity: {result.toxicity_score}")
            return result
        
        result.metadata["toxicity_scores"] = tox_scores
        
        # 3. Check faithfulness/hallucinations if context provided
        if context:
            try:
                has_hallucinations, faith_score, hallucs = detect_hallucinations(context, answer)
                result.faithfulness_score = faith_score
                result.hallucinations_detected = has_hallucinations
                
                if has_hallucinations and faith_score < self.min_faithfulness:
                    result.blocked = True
                    result.passed = False
                    result.reason = f"Output contains ungrounded claims (faithfulness: {faith_score})"
                    logger.warning(f"Output BLOCKED - hallucinations detected: {hallucs}")
                    result.metadata["hallucinations"] = hallucs
                
                result.metadata["faithfulness_score"] = faith_score
                
            except Exception as e:
                logger.debug(f"Faithfulness check skipped: {e}")
        
        logger.debug(f"Output passed guardrails")
        return result
    
    async def validate_token_budget(self, total_tokens: int, max_tokens: int = None) -> bool:
        """Check if token usage is within budget."""
        max_tokens = max_tokens or settings.token_hard_limit
        within_budget = total_tokens <= max_tokens
        if not within_budget:
            logger.warning(f"Token budget exceeded: {total_tokens} > {max_tokens}")
        return within_budget
