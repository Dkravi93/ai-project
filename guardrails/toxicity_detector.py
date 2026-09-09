"""
Toxicity Detection using Detoxify.
Detects harmful, offensive, or toxic content in text.
"""
from typing import Dict, Tuple
from config.logger import logger
from config.settings import get_settings

settings = get_settings()

try:
    from detoxify import Detoxify
except Exception as e:  # pragma: no cover - optional local model dependency
    Detoxify = None
    logger.warning(f"Detoxify unavailable, using lexical toxicity fallback: {e}")

_detoxify_model = None
_SEVERE_TERMS = {"kill", "murder", "terrorist", "bomb"}
_INSULT_TERMS = {"idiot", "stupid", "worthless", "hate"}


def _get_model():
    global _detoxify_model
    if Detoxify is None:
        return None
    if _detoxify_model is None:
        _detoxify_model = Detoxify(settings.detoxify_model_name, device="cpu")
    return _detoxify_model


def _fallback_scores(text: str) -> Dict[str, float]:
    normalized = f" {text.lower()} "
    severe = 0.9 if any(f" {term} " in normalized for term in _SEVERE_TERMS) else 0.0
    insult = 0.65 if any(f" {term} " in normalized for term in _INSULT_TERMS) else 0.0
    toxicity = max(severe, insult)
    return {
        "toxicity": toxicity,
        "severe_toxicity": severe,
        "obscene": 0.0,
        "threat": severe,
        "insult": insult,
        "identity_attack": 0.0,
    }


def detect_toxicity(text: str, threshold: float = 0.5) -> Tuple[bool, Dict[str, float]]:
    """
    Detect toxicity in text using Detoxify.
    
    Returns:
        Tuple of (is_toxic, scores_dict)
        scores_dict contains toxicity, severe_toxicity, obscene, threat, insult, identity_attack
    """
    try:
        model = _get_model()
        predictions = model.predict(text) if model else _fallback_scores(text)
        
        # Check if any toxicity score exceeds threshold
        is_toxic = any(score > threshold for score in predictions.values())
        
        if is_toxic:
            logger.warning(f"Toxicity detected: {predictions}")
        
        return is_toxic, predictions
        
    except Exception as e:
        logger.warning(f"Toxicity fallback after Detoxify error: {e}")
        predictions = _fallback_scores(text)
        return any(score > threshold for score in predictions.values()), predictions


def get_toxicity_level(scores: Dict[str, float]) -> str:
    """
    Get human-readable toxicity level based on scores.
    
    Returns: 'clean', 'mild', 'moderate', 'severe'
    """
    if not scores:
        return "unknown"
    
    max_score = max(scores.values())
    
    if max_score < 0.3:
        return "clean"
    elif max_score < 0.6:
        return "mild"
    elif max_score < 0.8:
        return "moderate"
    else:
        return "severe"


def is_severe_toxicity(scores: Dict[str, float], severity_threshold: float = 0.7) -> bool:
    """Check if text has severe toxicity."""
    if not scores:
        return False
    
    # Check severe_toxicity specifically
    severe = scores.get("severe_toxicity", 0)
    threat = scores.get("threat", 0)
    
    return severe > severity_threshold or threat > severity_threshold
