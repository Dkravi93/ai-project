"""
Logging configuration for AgentOps Hub.
"""
import logging
import os
import sys

try:
    from loguru import logger as _logger
except Exception:  # pragma: no cover - exercised only when optional dep missing
    _logger = logging.getLogger("agentops_hub")

from config.settings import get_settings

settings = get_settings()


def setup_logger():
    """Configure logger with file and console outputs."""
    if not hasattr(_logger, "add"):
        os.makedirs("logs", exist_ok=True)
        _logger.setLevel(settings.log_level)
        if not _logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)s - %(message)s"
            )
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(settings.log_level)
            console_handler.setFormatter(formatter)
            file_handler = logging.FileHandler("logs/agentops_hub.log")
            file_handler.setLevel("DEBUG")
            file_handler.setFormatter(formatter)
            _logger.addHandler(console_handler)
            _logger.addHandler(file_handler)
        _logger.info(f"AgentOps Hub running in {settings.environment} mode")
        return _logger
    
    # Remove default handler
    _logger.remove()
    
    # Console handler
    _logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    
    # File handler
    _logger.add(
        "logs/agentops_hub.log",
        rotation="10 MB",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    
    if settings.environment == "development":
        _logger.info(f"AgentOps Hub running in {settings.environment} mode")
    
    return _logger


# Initialize logger
logger = setup_logger()
