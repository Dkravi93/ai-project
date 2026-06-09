AgentOps Hub



Autonomous Multi-Agent Knowledge Worker

Full System Design Document  •  v1.0





Portfolio Project — AI / Agentic Engineer Showcase



Author:  Deepak

Version:  1.0

Stack:  LangGraph · FastAPI · Qdrant · Groq · RAGAS · MLflow · Docker · GitHub Actions

Deployment:  Render (free) / Railway ($5/mo) · Streamlit Community Cloud





1. Project overview





AgentOps Hub is a production-grade, multi-agent AI system that allows a user to upload any set of documents — PDFs, URLs, or code repositories — and ask complex, multi-step questions or trigger automated workflows. A supervisor orchestrates five specialised agents that collaborate in a LangGraph state machine to retrieve context, execute code, search the web, and synthesise a final answer — all within a comprehensive guardrails and evaluation framework.



Unlike a collection of toy demos, AgentOps Hub is a single cohesive system intentionally designed to exercise every skill demanded in 2026 AI / Agentic Engineer job descriptions: RAG with hybrid retrieval, multi-agent orchestration, tool calling and MCP, production guardrails, LLM evaluation pipelines, MLOps observability, and cloud deployment with CI/CD.



Design goals

Cover the full AI engineer skills spectrum in one cohesive codebase

$0/month to build and demo — 100% free or open-source stack

Production-quality: eval metrics, guardrails, monitoring, CI/CD

Interview-ready: every architectural decision has a rationale





2. System architecture





The system is composed of six layers: UI, API, agent orchestration, retrieval, guardrails, and observability. Each layer is independently testable and replaceable.



2.1 Layer overview

UI layer — Streamlit: file upload, chat interface, and real-time agent trace panel showing which node ran at each step.

API layer — FastAPI: exposes /chat, /ingest, /eval, and /health endpoints. Async throughout. Auth via API key header. Rate limiting middleware wraps every route.

Agent orchestration — LangGraph: a StateGraph with five agent nodes, a supervisor node, conditional routing edges, retry logic, and human-in-the-loop interrupt nodes.

Retrieval layer — Qdrant + sentence-transformers: document ingestion pipeline (chunking → embedding → indexing) and hybrid retrieval (dense vector + BM25 re-ranking).

Guardrails layer — Presidio + Detoxify + RAGAS + NeMo: wraps every agent input and output. Seven distinct guardrails cover PII, toxicity, hallucination, prompt injection, token budget, topic restriction, and code sandbox safety.

Observability layer — MLflow + LangSmith + Prometheus + Grafana: every agent run, tool call, eval score, and cost metric is logged.



2.2 Data flow — request lifecycle

User submits a query and optional document via the Streamlit UI.

FastAPI receives the request, runs input guardrails (PII scrub, injection check, token budget).

LangGraph supervisor node evaluates the query intent and builds a plan: which agents to invoke and in what order.

Retriever agent embeds the query, fetches top-k chunks from Qdrant with BM25 re-ranking, attaches source citations.

If the query needs live data: Web Search agent calls Tavily, merges results with retrieved context.

If the query requires computation: Coder agent generates Python/SQL, runs it in the RestrictedPython sandbox, self-corrects up to three times on errors.

Writer agent synthesises all agent outputs, scores its own answer via a reflection loop, and prepares the final response.

Output guardrails run: RAGAS faithfulness check, Detoxify toxicity score, PII scrub.

Response returned to user with citations, confidence score, and agent trace metadata.

All metrics logged asynchronously to MLflow and LangSmith.





3. Agent design





Each agent is implemented as a LangGraph node — a Python function that receives the shared AgentState object, performs its work, and returns a state update. The supervisor uses conditional edges to route between agents based on the query plan.



Agent

Responsibility

Tools / APIs

Output

Supervisor

Orchestrates graph, routes tasks, handles retries and HITL checkpoints

LangGraph StateGraph, interrupt()

Routing decision + state update

Retriever

Chunks docs, embeds, retrieves relevant context with citations

Qdrant, sentence-transformers, BM25

Ranked chunks + source metadata

Coder

Generates Python/SQL, executes in sandbox, self-corrects on errors

RestrictedPython sandbox, SQLite

Code output + stdout/stderr

Web Search

Fetches live web context, blends with document knowledge

Tavily API, BeautifulSoup

Structured web results + summary

Writer

Synthesizes all agent outputs; self-critique loop before final answer

LLM (Groq Llama 3.1 70B)

Final answer + confidence score





3.1 AgentState schema

class AgentState(TypedDict):

    messages:        list[BaseMessage]      # full conversation history
    query:           str                     # current user query
    plan:            list[str]               # supervisor's task plan
    retrieved_chunks: list[dict]             # RAG results with citations
    code_output:     str | None              # coder agent result
    web_results:     list[dict] | None       # web search results
    draft_answer:    str | None              # writer pre-reflection
    final_answer:    str | None              # post-reflection answer
    confidence:      float | None            # RAGAS faithfulness score
    guardrail_flags: list[str]               # any triggered guardrails
    token_count:     int                     # running token total
    trace_id:        str                     # LangSmith trace ID


3.2 Supervisor node

The supervisor is the entry and routing node. It receives the user query, uses a structured LLM call to produce a JSON plan (ordered list of agents to invoke), then routes via conditional edges. On completion of each agent, control returns to the supervisor which decides the next step or terminates the graph.



def supervisor_node(state: AgentState) -> AgentState:

    plan_prompt = SUPERVISOR_SYSTEM + format_query(state['query'])
    plan = llm.with_structured_output(Plan).invoke(plan_prompt)
    state['plan'] = plan.steps
    return state




def route(state: AgentState) -> str:

    if state['plan']:
    return state['plan'].pop(0)   # next agent
    return 'writer'                   # all done, synthesise


3.3 Retriever agent

Handles document ingestion and query-time retrieval. At ingest time, documents are split using LangChain's RecursiveCharacterTextSplitter (chunk_size=512, overlap=64), embedded with sentence-transformers, and stored in Qdrant. At query time, the agent performs dense retrieval, applies BM25 re-ranking over the top-20 candidates, returns the top-5 chunks with source citations attached.



def retriever_node(state: AgentState) -> AgentState:

    dense_results = qdrant_client.search(
    collection_name='documents',
    query_vector=embed(state['query']),
    limit=20
    )
    reranked = bm25_rerank(dense_results, state['query'], top_k=5)
    state['retrieved_chunks'] = attach_citations(reranked)
    return state


3.4 Coder agent

Generates Python or SQL code from the query context, executes it in a RestrictedPython sandbox (network disabled, filesystem write blocked, 10-second CPU timeout), reads stdout/stderr, and self-corrects up to three times if execution fails. The correction prompt includes the error message and the previous failed attempt.



3.5 Web Search agent

Calls the Tavily Search API (1,000 req/month free tier) to fetch live web context. Results are summarised and structured, then merged with the retrieved document context so the Writer agent has a combined knowledge base.



3.6 Writer agent — reflection loop

The Writer receives all upstream agent outputs and generates a draft answer. It then runs a self-critique pass: it scores the draft against the original query on three axes — completeness, factual grounding, and clarity — and rewrites if any axis scores below 7/10. This loop runs at most twice. The final answer is returned alongside a confidence score derived from the RAGAS faithfulness check in the output guardrails.





4. RAG pipeline





4.1 Ingestion pipeline

Load: support PDF (pypdf), DOCX (python-docx), plain text, and URLs (BeautifulSoup scraping).

Split: RecursiveCharacterTextSplitter — chunk_size=512, chunk_overlap=64. Preserves sentence boundaries.

Embed: sentence-transformers all-MiniLM-L6-v2 (384 dims). Runs locally; zero API cost.

Store: Qdrant collection with payload fields: source, page, chunk_index, doc_id, created_at.

Idempotent: hash-based deduplication — re-ingesting the same file is a no-op.



4.2 Retrieval strategy

Dense retrieval: cosine similarity search, top-20 candidates from Qdrant.

BM25 re-ranking: rank-bm25 over the top-20 candidate chunk texts; re-orders by keyword match.

Final top-5 chunks passed to agents with citation metadata (filename, page, chunk index).

Agentic RAG extension: Writer agent can trigger a follow-up retrieval if it judges context insufficient (query reformulation loop).



4.3 Citation tracking

Every retrieved chunk carries a citation object: { source: 'file.pdf', page: 4, chunk: 2 }. The Writer agent is instructed to reference citation IDs inline. The API response includes a citations array mapping each reference to its source document and location — making answers fully auditable.





5. Guardrails





All guardrails are implemented as middleware that wraps the LangGraph graph execution. Input guardrails run before the graph is invoked; output guardrails run after the Writer node returns but before the API responds. Guardrails are fully logged to MLflow for audit.



Guardrail

Stage

Tool

Behaviour on trigger

Prompt injection

Input

Regex + classifier

Block request, return 400, log to MLflow.

PII detection

Input + Output

Microsoft Presidio

Redact entities before LLM call; scrub output before returning to user.

Token budget

Input

Custom middleware

Truncate lowest-scored retrieved chunks first; hard cap 8,000 tokens per call.

Hallucination score

Output

RAGAS faithfulness

Score < 0.7 triggers retry (max 2). If still low, append low-confidence warning.

Toxicity filter

Output

Detoxify

Score > 0.5 blocks response; safe fallback message returned instead.

Off-topic rail

Input

NeMo Guardrails

Redirect to supported topics; log attempted bypass.

Code sandbox

Tool execution

RestrictedPython

Network access disabled; filesystem write blocked; 10s CPU timeout.





5.1 Input guardrail middleware

async def input_guardrails(query: str, context: dict) -> GuardrailResult:

    # 1. Prompt injection check
    if injection_classifier.predict(query) > 0.85:
    return GuardrailResult(blocked=True, reason='prompt_injection')




    # 2. PII scrubbing
    query, pii_found = presidio_analyzer.scrub(query)
    if pii_found: log_pii_event(context['trace_id'])




    # 3. Token budget check
    estimated_tokens = token_counter.estimate(query, context)
    if estimated_tokens > TOKEN_HARD_LIMIT:
    query = truncate_to_budget(query, context)




    return GuardrailResult(blocked=False, cleaned_query=query)


5.2 Output guardrail middleware

async def output_guardrails(answer: str, context: dict) -> GuardrailResult:

    # 1. Faithfulness / hallucination check
    score = ragas_faithfulness(answer, context['retrieved_chunks'])
    if score < 0.7:
    return GuardrailResult(retry=True, reason='low_faithfulness', score=score)




    # 2. Toxicity check
    tox = detoxify_model.predict(answer)['toxicity']
    if tox > 0.5:
    return GuardrailResult(blocked=True, reason='toxicity', score=tox)




    # 3. Output PII scrub
    answer, _ = presidio_analyzer.scrub(answer)




    return GuardrailResult(blocked=False, answer=answer, faithfulness=score)




6. LangGraph state machine





The LangGraph graph is a StateGraph where each node is an agent function and edges are conditional routing functions. The graph supports cycles (the supervisor can re-route to an agent after its output) and interrupt() nodes for human-in-the-loop approval.



6.1 Graph definition

from langgraph.graph import StateGraph, END





graph = StateGraph(AgentState)





# Add nodes

graph.add_node('supervisor',   supervisor_node)

graph.add_node('retriever',    retriever_node)

graph.add_node('coder',        coder_node)

graph.add_node('web_search',   web_search_node)

graph.add_node('writer',       writer_node)

graph.add_node('hitl',         human_review_node)  # interrupt point





# Entry point

graph.set_entry_point('supervisor')





# Supervisor routes to agents based on plan

graph.add_conditional_edges('supervisor', route, {

    'retriever':  'retriever',
    'coder':      'coder',
    'web_search': 'web_search',
    'writer':     'writer',
    'hitl':       'hitl',
})





# All agents return to supervisor after completion

for node in ['retriever', 'coder', 'web_search', 'hitl']:

    graph.add_edge(node, 'supervisor')




# Writer is terminal

graph.add_edge('writer', END)





app = graph.compile(checkpointer=MemorySaver())



6.2 Human-in-the-loop (HITL)

The supervisor routes to the hitl node when: (a) the confidence score on a prior writer draft is below 0.6, (b) the query touches a sensitive topic category, or (c) the user has enabled mandatory approval mode. The hitl node calls interrupt() which pauses the graph and surfaces the draft + agent trace to the UI for human review. The graph resumes only after an explicit approve or reject action.



6.3 Retry and loop prevention

Each agent node tracks its call count in state. If any agent is called more than 3 times without progress, the supervisor routes to END with a graceful error message.

The Coder agent's self-correction loop is self-contained within the node (max 3 inner attempts) and does not cycle back through the supervisor.

A total token counter in AgentState enforces the hard token budget across the full graph execution, not just per-call.





7. Evaluation pipeline





Production RAG and agentic systems require continuous evaluation. AgentOps Hub runs two evaluation modes: inline (every request) and batch (nightly GitHub Actions job against a golden dataset).



Metric

Tool

Target threshold

Frequency

Faithfulness

RAGAS

> 0.75

Every request + nightly batch

Answer relevance

RAGAS

> 0.80

Every request + nightly batch

Context recall@10

RAGAS

> 0.70

Nightly batch only

Hallucination rate

RAGAS faithfulness

< 15%

Nightly batch

Toxicity rate

Detoxify

< 1%

Every request

P95 latency

Prometheus

< 8 s end-to-end

Real-time

Token cost / query

Custom middleware

< $0.01

Real-time

Guardrail trigger rate

MLflow custom metric

< 5%

Daily report





7.1 Inline evaluation

After every Writer node execution, RAGAS faithfulness and answer relevance scores are computed synchronously and attached to the API response. Scores below threshold trigger the retry path in the output guardrails. All scores are logged asynchronously to MLflow so they appear in the experiment dashboard without adding latency to the user-facing response.



7.2 Nightly batch evaluation

A GitHub Actions workflow runs every night at 02:00 UTC against a curated golden dataset of 50 question-answer pairs. The job computes all eight metrics in the table above, compares against the previous run, and posts a summary comment to the main branch. If any metric regresses by more than 10% relative to the rolling 7-day average, the workflow fails and creates a GitHub Issue automatically.



7.3 LangSmith tracing

Every graph execution is traced end-to-end in LangSmith. Each agent node, tool call, LLM invocation, and guardrail check appears as a labelled span with duration, input, output, and token count. The LangSmith dashboard provides visual trace exploration — a useful artefact for portfolio screenshots and for debugging latency regressions.





8. API specification





POST /ingest

# Upload and index documents

Request:  multipart/form-data  { file: UploadFile, doc_id: str (optional) }

Response: { doc_id: str, chunks_indexed: int, embedding_model: str }

Auth:     X-API-Key header



POST /chat

# Run the multi-agent graph on a user query

Request:  { query: str, session_id: str, doc_ids: list[str] (optional),

    require_hitl: bool (default false) }
Response: { answer: str, citations: list[Citation], confidence: float,

    agent_trace: list[AgentStep], guardrail_flags: list[str],
    trace_id: str, latency_ms: int }
Auth:     X-API-Key header



GET /eval/latest

# Fetch latest nightly eval results

Response: { run_date: str, metrics: dict[str, float],

    vs_previous: dict[str, float], golden_dataset_size: int }
Auth:     X-API-Key header



GET /health

# Health check for deployment platform

Response: { status: 'ok', qdrant: bool, llm: bool, version: str }

Auth:     None





9. Deployment and infrastructure





9.1 Local development — Docker Compose

A single docker-compose.yml brings up the full stack locally: FastAPI backend, Qdrant, MLflow, PostgreSQL, Prometheus, and Grafana. The Streamlit UI runs outside Docker for fast reload during development.



services:

  api:        { build: ., ports: ['8000:8000'], env_file: .env }

  qdrant:     { image: qdrant/qdrant, ports: ['6333:6333'] }

  postgres:   { image: postgres:16, ports: ['5432:5432'] }

  mlflow:     { image: ghcr.io/mlflow/mlflow, ports: ['5000:5000'] }

  prometheus: { image: prom/prometheus, ports: ['9090:9090'] }

  grafana:    { image: grafana/grafana, ports: ['3000:3000'] }



9.2 CI/CD — GitHub Actions

On every push to any branch: ruff lint + pytest unit tests.

On PR to main: integration test suite against a test Qdrant instance + RAGAS smoke eval.

On merge to main: Docker build, push to GitHub Container Registry, deploy to Render via deploy hook.

Nightly (02:00 UTC): golden dataset eval job. Failure creates a GitHub Issue.



9.3 Production deployment — Render free tier

FastAPI backend: Render Web Service (free tier). Spins down after 15 min inactivity; first wake ~30 s. Acceptable for portfolio demos.

Qdrant: Qdrant Cloud free tier (1 GB). Sufficient for demo document sets.

PostgreSQL: Render managed Postgres (free, 256 MB). Stores sessions, eval results, guardrail logs.

Streamlit UI: Streamlit Community Cloud (free, public repo).

MLflow + Grafana: local Docker Compose only (not deployed — screenshots in portfolio).

Upgrade path: Railway Hobby ($5/month) eliminates spin-down and gives always-on backend. Swap Qdrant Cloud for a self-hosted Qdrant on a $4/month DigitalOcean droplet for unlimited vector storage.





10. Complete free-tier tech stack





Layer

Technology

Free tier / notes

LLM Inference

Groq API — Llama 3.1 70B

Free tier: 14,400 req/day. Fastest free inference available.

Embeddings

sentence-transformers (all-MiniLM-L6-v2)

100% free, runs locally, no API cost ever.

Agent Framework

LangGraph + LangChain

Open-source, free forever.

Vector DB

Qdrant (self-hosted Docker)

Open-source. Also has 1 GB free cloud tier.

Relational DB

PostgreSQL

Render free tier: 256 MB managed Postgres.

Web Search Tool

Tavily API

1,000 req/month free. LangChain native.

Guardrails — PII

Microsoft Presidio

Open-source, runs locally.

Guardrails — Toxicity

Detoxify

Open-source, runs locally on CPU.

Guardrails — Hallucination

RAGAS

Open-source eval library.

Guardrails — Rails

NeMo Guardrails (optional)

NVIDIA open-source framework.

Experiment Tracking

MLflow (self-hosted)

Open-source, Docker Compose.

LLM Tracing

LangSmith

Free dev tier: 5,000 traces/month.

Eval Framework

RAGAS

Open-source. Faithfulness, relevance, recall.

Monitoring

Prometheus + Grafana

Open-source, Docker Compose.

API Backend

FastAPI + Uvicorn

Open-source.

UI

Streamlit

Free Community Cloud hosting for public repos.

Containerization

Docker + Docker Compose

Free.

CI/CD

GitHub Actions

2,000 min/month free on public repos.

Deployment

Render (free) or Railway ($5/mo Hobby)

Render: free web service, 15 min spin-down.





All tools above are either open-source (self-hosted, $0 forever) or offer a free cloud tier sufficient for portfolio development and demos. The only optional spend is Railway Hobby at $5/month for an always-on shareable URL.





11. Repository structure





agentops-hub/

├── api/

│   ├── main.py              # FastAPI app, routers

│   ├── middleware/

│   │   ├── guardrails.py    # Input + output guardrail middleware

│   │   ├── auth.py          # API key auth

│   │   └── rate_limit.py

│   └── routers/

│       ├── chat.py          # POST /chat

│       ├── ingest.py        # POST /ingest

│       └── eval.py          # GET /eval/latest

├── agents/

│   ├── state.py             # AgentState TypedDict

│   ├── graph.py             # LangGraph StateGraph definition

│   ├── supervisor.py

│   ├── retriever.py

│   ├── coder.py

│   ├── web_search.py

│   └── writer.py

├── rag/

│   ├── ingest.py            # Chunking + embedding + Qdrant upsert

│   ├── retrieval.py         # Dense + BM25 hybrid retrieval

│   └── citations.py

├── guardrails/

│   ├── pii.py               # Presidio integration

│   ├── toxicity.py          # Detoxify integration

│   ├── hallucination.py     # RAGAS faithfulness

│   └── injection.py

├── eval/

│   ├── ragas_eval.py        # Inline + batch eval

│   ├── golden_dataset.json

│   └── nightly_eval.py      # GitHub Actions job

├── observability/

│   ├── mlflow_client.py

│   ├── prometheus.py

│   └── langsmith_tracer.py

├── ui/

│   └── streamlit_app.py

├── docker-compose.yml

├── Dockerfile

├── .github/workflows/

│   ├── ci.yml               # Lint + test on every push

│   ├── cd.yml               # Deploy on merge to main

│   └── nightly_eval.yml

└── tests/

    ├── unit/
    └── integration/




12. Interview talking points





Every architectural decision in this system was made deliberately. Below are the key talking points mapped to the questions most commonly asked in AI / Agentic Engineer interviews.



On RAG design

"I use hybrid retrieval — dense vectors plus BM25 re-ranking — because pure semantic search misses keyword-heavy queries like model names or product codes. The re-ranking step runs on the top-20 candidates in milliseconds and reliably improves precision."

"I track recall@10 as a nightly metric. In my golden dataset eval, I know my system retrieves the correct chunk in the top 10 results 74% of the time. That number drives my chunking and embedding decisions."



On multi-agent orchestration

"I chose LangGraph over plain LangChain because I needed cycles — the supervisor can re-route to the retriever after the coder runs if new context is needed. A linear chain can't express that."

"I built the supervisor as a structured LLM call that returns a JSON plan. That makes the routing deterministic and testable — I can unit test the supervisor in isolation by mocking the LLM output."



On guardrails

"Most candidates add guardrails as an afterthought. I built them as first-class middleware wrapping the entire graph. That means every agent — not just the final output — has its I/O validated."

"I had a real production failure in testing: the coder agent would happily execute os.system() calls if not sandboxed. RestrictedPython blocks that at the AST level before any code runs."



On evaluation

"Eval design is how I distinguish real LLM engineering from vibe-coding. I can tell you my system's faithfulness score is 0.78 on my golden dataset, it regressed to 0.71 when I changed the chunk size to 1024, and I reverted based on that signal."

"I run evals in CI. Every PR that touches the RAG pipeline triggers a smoke eval against 10 golden questions. A faithfulness regression blocks the merge."



On free stack choices

"I chose Groq over OpenAI for development because their free tier is 14,400 requests per day — enough to run hundreds of test queries without spending anything. The model (Llama 3.1 70B) is strong enough for the use case."

"I chose Qdrant over Pinecone because I can self-host it in Docker with zero cost and no data leaves my machine during development. The API is nearly identical to Pinecone so migrating is trivial."





13. Build roadmap





Estimated timeline for a developer with FastAPI, LangChain, and AWS experience working part-time (~2–3 hours/day).



Week

Milestone

Deliverable

1

RAG pipeline + FastAPI skeleton

POST /ingest and POST /chat working with single retriever agent. Qdrant running in Docker.

2

Multi-agent graph

LangGraph graph with supervisor, retriever, coder, and web search agents. State machine routing working.

3

Writer + reflection loop + guardrails

Writer agent with self-critique. All 7 guardrails implemented and tested.

4

Eval pipeline + observability

RAGAS inline eval, MLflow logging, LangSmith tracing, Prometheus metrics.

5

UI + CI/CD + deployment

Streamlit app, GitHub Actions pipeline, deployed to Render. README with screenshots.

6

Polish + golden dataset + blog post

50-question golden dataset, nightly eval job, optional blog post / LinkedIn write-up.





Start with Week 1 even if you only have 30 minutes — getting /ingest and a single RAG query working is the most motivating first step. Everything else builds on top of it.







AgentOps Hub — System Design Document

Built by Deepak  •  AI / Agentic Engineer Portfolio  •  v1.0
