"""
Observability module for AgentOps Hub.
Handles MLflow, LangSmith, Prometheus, and Grafana integrations.
"""
import mlflow
from config.settings import get_settings
from config.logger import logger

settings = get_settings()

# Initialize MLflow
mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
mlflow.set_experiment("agentops-hub")


def start_mlflow_run(run_name: str, tags: dict = None):
    """Start an MLflow run for tracking."""
    run = mlflow.start_run(run_name=run_name)
    if tags:
        mlflow.set_tags(tags)
    logger.info(f"Started MLflow run: {run_name}")
    return run


def log_metrics(metrics: dict):
    """Log metrics to MLflow."""
    mlflow.log_metrics(metrics)


def end_mlflow_run():
    """End the current MLflow run."""
    mlflow.end_run()


class ObservabilityContext:
    """Context manager for observability tracking."""
    
    def __init__(self, run_name: str, tags: dict = None):
        self.run_name = run_name
        self.tags = tags or {}
        self.run = None
    
    def __enter__(self):
        self.run = start_mlflow_run(self.run_name, self.tags)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            mlflow.log_param("error", str(exc_val))
        end_mlflow_run()
