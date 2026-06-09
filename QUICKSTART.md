# ?? Quick Start Checklist

## Phase 1: Environment Setup (5-10 min)

- [ ] **Install dependencies**
  ```bash
  pip install -r requirements.txt
  ```
  After this completes, verify: `python -c "import langchain; import fastapi; print('? Dependencies OK')"`

- [ ] **Create .env file**
  ```bash
  cp .env.example .env
  ```
  Edit .env and add:
  - [ ] GROQ_API_KEY (get from https://console.groq.com/)
  - [ ] TAVILY_API_KEY (get from https://tavily.com/)
  - [ ] API_KEY (any secure string for testing)

- [ ] **Start local services**
  ```bash
  docker-compose up -d
  ```
  Wait 30 seconds for services to be ready.
  
  Verify:
  - [ ] Qdrant: `curl http://localhost:6333/health`
  - [ ] PostgreSQL: psql running (check in Docker)
  - [ ] MLflow: Visit http://localhost:5000

## Phase 2: Verify Setup (2-3 min)

- [ ] **Test FastAPI**
  ```bash
  uvicorn api.main:app --reload
  ```
  Visit http://localhost:8000/docs
  Check GET /health endpoint works

- [ ] **Check folder structure**
  ```bash
  python -c "import api.main; import agents.state; import config.settings; print('? All modules importable')"
  ```

## Phase 3: Next Work Items

### High Priority (Start Here)
1. [ ] **Implement Supervisor Agent** (`agents/supervisor.py`)
   - Structured prompt for task planning
   - Route between agents based on query

2. [ ] **Implement Retriever Agent** (`rag/` module)
   - Document chunking & embedding
   - Qdrant integration
   - BM25 re-ranking

3. [ ] **Create LangGraph State Machine** (`agents/graph.py`)
   - Connect all agents
   - Define routing edges
   - Test with sample queries

### Medium Priority
4. [ ] Implement Coder Agent (RestrictedPython)
5. [ ] Implement Writer Agent (reflection loop)
6. [ ] Build Guardrails Layer
7. [ ] Create API Routes (/ingest, /chat)

### Lower Priority
8. [ ] WebSearch Agent
9. [ ] Streamlit UI
10. [ ] Observability (MLflow tracking)

## ?? Monitoring Services

### While Working

- **API Docs**: http://localhost:8000/docs (auto-updates)
- **MLflow**: http://localhost:5000 (track experiments)
- **Qdrant Console**: http://localhost:6333/dashboard
- **Prometheus**: http://localhost:9090 (metrics)

### View Logs

```bash
# Docker logs
docker-compose logs -f api        # FastAPI
docker-compose logs -f qdrant     # Qdrant
docker-compose logs -f postgres   # Database

# Application logs
tail -f logs/agentops_hub.log
```

## ?? Troubleshooting

**Q: `ModuleNotFoundError` when importing**
```bash
# Ensure venv is activated
source venv/bin/activate    # macOS/Linux
# or
venv\Scripts\activate       # Windows
```

**Q: Qdrant not responding**
```bash
# Check if container is running
docker ps | grep qdrant
# Restart if needed
docker-compose restart qdrant
```

**Q: Port already in use (e.g., 8000)**
```bash
# Kill the process using that port
lsof -i :8000           # Find process ID
kill -9 <PID>           # Kill it
```

**Q: Docker services not starting**
```bash
# Check logs
docker-compose logs
# Rebuild
docker-compose down
docker-compose up --build
```

## ?? Development Tips

1. **Use VS Code + Python extension** for debugging
2. **Enable auto-format** with Black: `black --check .`
3. **Run linter**: `ruff check .`
4. **Type checking**: `mypy .`
5. **Tests**: `pytest -v` (currently minimal)

## ?? Reference Files

- `SETUP.md` - Full development guide
- `IMPLEMENTATION_STATUS.md` - Work breakdown
- `config/settings.py` - All environment variables
- `agents/state.py` - AgentState schema
- `Readme.md` - System design document

---

**Ready? Start with Phase 1! ?**
