# AgentOps Hub - Setup Guide

## ?? Quick Start

### 1. Clone & Setup Environment

```bash
cd ai-project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and fill in API keys:
# - GROQ_API_KEY: https://console.groq.com/
# - TAVILY_API_KEY: https://tavily.com/
# - QDRANT_API_KEY: (optional, for cloud deployment)
```

### 4. Start Services (Docker)

```bash
docker-compose up -d
```

Services will be available at:

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Qdrant**: http://localhost:6333
- **MLflow**: http://localhost:5000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin:admin)

### 5. Run the API (without Docker)

```bash
uvicorn api.main:app --reload
```

### 6. Run the Streamlit UI

```bash
streamlit run ui/app.py
```

## ??? Project Structure

```
agentops-hub/
+-- api/                 # FastAPI application
�   +-- main.py         # Main app & routes
�   +-- middleware/      # Auth, rate limiting, etc.
�   +-- routers/         # API route modules
+-- agents/              # LangGraph agents
�   +-- state.py        # Shared state schema
�   +-- supervisor.py   # Orchestration
�   +-- retriever.py    # RAG retriever
�   +-- coder.py        # Code executor
�   +-- web_search.py   # Web search agent
�   +-- writer.py       # Answer synthesis
+-- rag/                 # Retrieval-Augmented Generation
�   +-- ingestion.py    # Document loading & chunking
�   +-- embeddings.py   # Embedding pipeline
�   +-- retrieval.py    # Hybrid search
+-- guardrails/          # Security & compliance
�   +-- injection.py    # Prompt injection check
�   +-- pii.py         # PII detection & scrubbing
�   +-- toxicity.py    # Toxicity detection
�   +-- ragas.py       # Hallucination detection
+-- eval/               # Evaluation framework
�   +-- metrics.py     # RAGAS metrics
�   +-- batch.py       # Batch evaluation jobs
+-- observability/      # Monitoring & logging
�   +-- mlflow.py      # MLflow integration
�   +-- langsmith.py   # LangSmith tracing
�   +-- prometheus.py  # Prometheus metrics
+-- ui/                 # Streamlit frontend
�   +-- app.py         # Main UI app
�   +-- pages/         # Streamlit pages
�   +-- components/    # Reusable UI components
+-- tests/              # Test suite
�   +-- unit/          # Unit tests
�   +-- integration/   # Integration tests
�   +-- eval/          # Evaluation tests
+-- config/             # Configuration
�   +-- settings.py    # Settings management
�   +-- logger.py      # Logging setup
+-- logs/               # Application logs
+-- requirements.txt    # Python dependencies
+-- docker-compose.yml  # Local services
+-- Dockerfile         # API container image
+-- pytest.ini         # Pytest configuration
+-- .env.example       # Example environment variables
```

## ?? Development

### Running Tests

```bash
pytest                  # Run all tests
pytest -v              # Verbose output
pytest --cov          # With coverage
pytest tests/unit     # Only unit tests
```

### Linting & Formatting

```bash
ruff check .           # Lint with ruff
black .                # Format with black
mypy .                 # Type check with mypy
```

### Docker Compose Services

Start individual services:

```bash
docker-compose up api         # FastAPI only
docker-compose up qdrant      # Qdrant only
docker-compose up postgres    # Database only
```

View logs:

```bash
docker-compose logs api       # API logs
docker-compose logs -f api    # Follow logs
```

## ?? Architecture

### 6-Layer Design

1. **UI Layer** (Streamlit): File upload, chat interface, trace panel
2. **API Layer** (FastAPI): REST endpoints, auth, rate limiting
3. **Agent Orchestration** (LangGraph): Multi-agent state machine
4. **Retrieval Layer** (Qdrant + BM25): Hybrid search with re-ranking
5. **Guardrails Layer** (Presidio, Detoxify, RAGAS): Input/output validation
6. **Observability** (MLflow, LangSmith): Metrics, traces, monitoring

### Request Lifecycle

1. User query ? Streamlit UI
2. FastAPI input guardrails (PII, injection, token budget)
3. LangGraph supervisor routes to agents
4. Agents execute (Retriever, Coder, WebSearch, Writer)
5. Output guardrails (faithfulness, toxicity, PII)
6. Response + citations + metrics ? User

## ?? Environment Variables

See `.env.example` for all available variables. Key ones:

```bash
GROQ_API_KEY=              # LLM provider
TAVILY_API_KEY=            # Web search
QDRANT_HOST=localhost      # Vector DB
DATABASE_URL=              # PostgreSQL
API_KEY=your_secret_key    # API authentication
```

## ?? Documentation

- **System Design**: See `AgentOps_Hub_System_Design.docx`
- **API Docs**: http://localhost:8000/docs (auto-generated)
- **Agent Reference**: See `agents/` module
- **RAG Guide**: See `rag/` module

## ?? Next Steps

1. ? Environment setup
2. ? Project structure created
3. ? Implement core agents
4. ? Build RAG pipeline
5. ? Add guardrails
6. ? Integrate observability
7. ? Build Streamlit UI
8. ? Deploy to Render/Railway
