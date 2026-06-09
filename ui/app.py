"""Streamlit main application for AgentOps Hub."""
from __future__ import annotations

import uuid

import requests
import streamlit as st

from config.settings import get_settings

settings = get_settings()

st.set_page_config(
    page_title="AgentOps Hub",
    page_icon="A",
    layout="wide",
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("AgentOps Hub")
    api_base_url = st.text_input("API URL", value=settings.ui_api_base_url).rstrip("/")
    api_key = st.text_input("API key", value=settings.api_key, type="password")
    headers = {"X-API-Key": api_key} if api_key else {}

    st.divider()
    st.caption("System")
    health_box = st.empty()

    def render_health() -> None:
        try:
            response = requests.get(f"{api_base_url}/health", timeout=4)
            response.raise_for_status()
            payload = response.json()
            health_box.success(
                f"API {payload.get('status', 'unknown')} | "
                f"Qdrant {payload.get('qdrant', 'unknown')}"
            )
            st.caption(f"Collection: {payload.get('collection')} | dim {payload.get('embedding_dim')}")
        except Exception as exc:
            health_box.error(f"API unavailable: {exc}")

    render_health()

    if st.button("Initialize Qdrant", use_container_width=True):
        try:
            response = requests.post(
                f"{api_base_url}/api/admin/init-collection",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            st.success("Collection is ready")
        except Exception as exc:
            st.error(f"Collection init failed: {exc}")

    if st.button("New session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

st.title("AgentOps Hub")
st.caption("Autonomous multi-agent knowledge worker")

chat_tab, ingest_tab, eval_tab = st.tabs(["Chat", "Ingest", "Eval"])

with chat_tab:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("details"):
                with st.expander("Trace and guardrails"):
                    st.json(message["details"])

    prompt = st.chat_input("Ask about your indexed documents or request a workflow")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Running agent graph..."):
                try:
                    response = requests.post(
                        f"{api_base_url}/chat",
                        headers=headers,
                        json={
                            "query": prompt,
                            "session_id": st.session_state.session_id,
                            "doc_ids": [],
                        },
                        timeout=120,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    answer = payload.get("answer") or "No answer returned."
                    st.markdown(answer)

                    citations = payload.get("citations") or []
                    if citations:
                        st.caption("Citations")
                        st.dataframe(citations, use_container_width=True, hide_index=True)

                    details = {
                        "confidence": payload.get("confidence"),
                        "latency_ms": payload.get("latency_ms"),
                        "trace_id": payload.get("trace_id"),
                        "agent_trace": payload.get("agent_trace"),
                        "guardrails": payload.get("guardrails"),
                        "errors": payload.get("errors"),
                    }
                    with st.expander("Trace and guardrails"):
                        st.json(details)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "details": details,
                    })
                except Exception as exc:
                    error_text = f"Request failed: {exc}"
                    st.error(error_text)
                    st.session_state.messages.append({"role": "assistant", "content": error_text})

with ingest_tab:
    uploaded_file = st.file_uploader("Upload a TXT, PDF, or DOCX file", type=["txt", "md", "pdf", "docx"])
    doc_id = st.text_input("Document ID", placeholder="Optional stable ID")

    if st.button("Ingest document", disabled=uploaded_file is None, use_container_width=True):
        with st.spinner("Indexing document..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"doc_id": doc_id} if doc_id else {}
                response = requests.post(
                    f"{api_base_url}/ingest",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120,
                )
                response.raise_for_status()
                st.success("Document indexed")
                st.json(response.json())
            except Exception as exc:
                st.error(f"Ingestion failed: {exc}")

with eval_tab:
    if st.button("Load latest eval", use_container_width=True):
        try:
            response = requests.get(
                f"{api_base_url}/eval/latest",
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            st.json(response.json())
        except Exception as exc:
            st.error(f"Eval fetch failed: {exc}")
