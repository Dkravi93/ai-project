"""
Configuration module for AgentOps Hub.
Loads environment variables and provides settings across the application.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # LLM & API Keys
    groq_api_key: str = ""
    tavily_api_key: str = ""

    # Qdrant Vector Database
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "documents"
    qdrant_timeout_seconds: float = 3.0

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ui_api_base_url: str = "http://localhost:8000"
    api_key: str = ""
    rate_limit_requests: int = 100
    rate_limit_period: int = 60

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/agentops_hub"

    # Observability
    mlflow_tracking_uri: str = "http://localhost:5000"
    langsmith_api_key: str = ""
    langsmith_project: str = "agentops-hub"
    prometheus_scrape_port: int = 8001

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_cache_dir: str = "./models"

    # Guardrails
    presidio_operators_enabled: bool = True
    detoxify_batch_size: int = 32
    ragas_threshold: float = 0.7
    pii_threshold: float = 0.5
    toxicity_threshold: float = 0.6
    severe_toxicity_threshold: float = 0.8
    prompt_injection_threshold: float = 0.7
    token_hard_limit: int = 8000

    # Coder Sandbox
    sandbox_timeout_seconds: int = 10
    sandbox_max_attempts: int = 3

    # Deployment
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
