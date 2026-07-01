"""Sidebar component for AgentOps Hub."""
import streamlit as st
import uuid
from ui.utils.api_client import health_check, collection_status, init_collection


def render_sidebar():
    with st.sidebar:
        st.header("AgentOps Hub")
        st.divider()
        with st.expander("API Configuration", expanded=True):
            api_url = st.text_input(
                "API URL",
                value=st.session_state.get("api_base_url", ""),
                key="api_url_in",
                placeholder="http://localhost:8000",
            )
            st.session_state.api_base_url = api_url.rstrip("/")
            api_key = st.text_input(
                "API Key",
                value=st.session_state.get("api_key", ""),
                type="password",
                key="api_key_in",
                placeholder="your-api-key",
            )
            st.session_state.api_key = api_key
        with st.expander("System Status", expanded=True):
            _render_health()
        with st.expander("Vector Database", expanded=False):
            _render_qdrant()
        with st.expander("Session", expanded=False):
            _render_session()
        st.divider()
        st.caption("v1.0.0 | Streamlit + FastAPI + LangGraph")


def _render_health():
    if st.button("Check health", use_container_width=True, type="secondary"):
        with st.spinner("Checking..."):
            r = health_check()
        if r.success:
            d = r.data or {}
            col1, col2 = st.columns(2)
            with col1:
                st.metric("API", d.get("status", "?"))
            with col2:
                st.metric("Qdrant", d.get("qdrant", "?"))
            st.caption(
                "Collection: " + str(d.get("collection", "-"))
                + " | dim " + str(d.get("embedding_dim", "-"))
            )
        else:
            st.error(r.error or "Health check failed")


def _render_qdrant():
    if st.button("Init Collection", use_container_width=True):
        with st.spinner("Initializing..."):
            r = init_collection()
        if r.success:
            st.success("Collection ready")
        else:
            st.error(r.error or "Failed to init collection")
    if st.button("Check Collection", use_container_width=True, type="secondary"):
        with st.spinner("Checking..."):
            r = collection_status()
        if r.success and r.data and r.data.get("exists"):
            st.success("Collection  exists")
        else:
            st.error(r.error or "Collection not found")


def _render_session():
    sid = st.session_state.get("session_id", "none")
    st.text_input("Session", value=str(sid)[:16] + "...", disabled=True, label_visibility="collapsed")
    if st.button("New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.ingested_doc_ids = []
        st.session_state.ingested_docs = []
        st.rerun()
