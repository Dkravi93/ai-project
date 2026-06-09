"""
Prompt injection and unsafe instruction detection.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

_INJECTION_PATTERNS = [
    (r"\b(ignore|bypass|override|forget)\b.{0,80}\b(previous|prior|system|developer|instructions?)\b", 0.9, "instruction_override"),
    (r"\b(reveal|print|show|dump|exfiltrate)\b.{0,80}\b(system prompt|developer message|hidden instructions?|api key|secret|token)\b", 0.95, "secret_exfiltration"),
    (r"\b(jailbreak|DAN mode|do anything now|unfiltered mode)\b", 0.85, "jailbreak"),
    (r"\bact as\b.{0,60}\b(system|developer|root|admin)\b", 0.7, "role_escalation"),
    (r"\btool call\b.{0,80}\bwithout\b.{0,40}\bpermission\b", 0.65, "tool_misuse"),
]

_SQL_PATTERNS = [
    (r"(--|/\*|\*/|;)", 0.35, "sql_delimiter"),
    (r"\b(drop|delete|truncate|alter|insert|update)\b\s+\b(table|from|into|database|schema)\b", 0.9, "destructive_sql"),
    (r"\bunion\b\s+\bselect\b|\bor\b\s+1\s*=\s*1\b", 0.85, "sql_injection"),
]


def detect_prompt_injection(text: str, threshold: float = 0.7) -> Tuple[bool, float, Dict[str, str]]:
    """
    Return whether text looks like prompt injection or unsafe instruction hijacking.

    This is intentionally deterministic so it can run before any model call. The
    score is a simple max over matched rules, not a calibrated probability.
    """
    normalized = re.sub(r"\s+", " ", text or "").strip()
    matches = []
    score = 0.0

    for pattern, weight, label in [*_INJECTION_PATTERNS, *_SQL_PATTERNS]:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            matches.append(label)
            score = max(score, weight)

    return score >= threshold, score, {"matches": matches}
