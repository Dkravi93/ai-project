"""
PII Detection and Removal using Presidio.
Detects and redacts personally identifiable information.
"""
import re
from typing import Tuple
from config.logger import logger
from config.settings import get_settings

settings = get_settings()

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
except Exception as e:  # pragma: no cover - depends on optional local models
    AnalyzerEngine = None
    AnonymizerEngine = None
    logger.warning(f"Presidio unavailable, using regex PII fallback: {e}")

_analyzer = None
_anonymizer = None

_FALLBACK_PATTERNS = [
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("PHONE_NUMBER", re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("API_KEY", re.compile(r"\b(?:sk|pk|ghp|xoxb|AIza)[A-Za-z0-9_\-]{16,}\b")),
]


def _get_engines():
    global _analyzer, _anonymizer
    if AnalyzerEngine is None or AnonymizerEngine is None:
        return None, None
    if _analyzer is None or _anonymizer is None:
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        # Use small spaCy model (~12 MB) instead of default large (~400 MB)
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": settings.spacy_model}
            ]
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        _anonymizer = AnonymizerEngine()
    return _analyzer, _anonymizer


def _fallback_detect(text: str) -> Tuple[bool, list, str]:
    entities_found = []
    for entity_type, pattern in _FALLBACK_PATTERNS:
        for match in pattern.finditer(text):
            entities_found.append({
                "entity_type": entity_type,
                "start": match.start(),
                "end": match.end(),
                "score": 0.8,
                "text_sample": match.group(0),
            })
    return bool(entities_found), entities_found, text


def detect_pii(text: str, threshold: float = 0.5) -> Tuple[bool, list, str]:
    """
    Detect PII entities in text.
    Returns (has_pii, entities_found, original_text)
    """
    try:
        analyzer, _ = _get_engines()
        if analyzer is None:
            return _fallback_detect(text)

        results = analyzer.analyze(text=text, language="en", threshold=threshold)
        
        if not results:
            logger.debug("No PII detected")
            return False, [], text
        
        entities_found = []
        for result in results:
            entities_found.append({
                "entity_type": result.entity_type,
                "start": result.start,
                "end": result.end,
                "score": result.score,
                "text_sample": text[result.start : result.end]
            })
        
        logger.warning(f"PII detected: {len(entities_found)} entities")
        return True, entities_found, text
        
    except Exception as e:
        logger.warning(f"PII detection fallback after Presidio error: {e}")
        return _fallback_detect(text)


def redact_pii(text: str, threshold: float = 0.5) -> str:
    """Redact PII from text using Presidio anonymizer."""
    try:
        analyzer, anonymizer = _get_engines()
        if analyzer is None or anonymizer is None:
            redacted = text
            for entity_type, pattern in _FALLBACK_PATTERNS:
                redacted = pattern.sub(f"<{entity_type}>", redacted)
            return redacted

        results = analyzer.analyze(text=text, language="en", threshold=threshold)
        
        if not results:
            return text
        
        redacted = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={"DEFAULT": {"type": "redact"}}
        )
        
        logger.debug(f"PII redacted: {len(results)} entities removed")
        return redacted.text
        
    except Exception as e:
        logger.warning(f"PII redaction fallback after Presidio error: {e}")
        redacted = text
        for entity_type, pattern in _FALLBACK_PATTERNS:
            redacted = pattern.sub(f"<{entity_type}>", redacted)
        return redacted
