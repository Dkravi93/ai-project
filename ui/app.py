"""AgentOps Hub - Streamlit Frontend Main Entry Point."""
from __future__ import annotations
import os as _os
import sys as _sys
import uuid
import streamlit as st

PROJECT_ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in _sys.path:
    _sys.path.insert(0, PROJECT_ROOT)

from ui.config import APP_TITLE, APP_SUBTITLE, PAGE_ICON
from ui.styles import apply_custom_styles
from ui.components.sidebar import render_sidebar
from ui.components.chat_panel import render_chat_tab, execute_pending
from ui.components.ingest_panel import render_ingest_tab
from ui.components.eval_panel import render_eval_tab

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/agentops-hub",
        "Report a bug": "https://github.com/agentops-hub/issues",
        "About": APP_TITLE + " v1.0.0 - Autonomous Multi-Agent Knowledge Worker",
    },
)

for key, default in [
    ("session_id", str(uuid.uuid4())),
    ("messages", []),
    ("ingested_doc_ids", []),
    ("ingested_docs", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

from ui.config import API_BASE_URL, API_KEY
if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = API_BASE_URL
if "api_key" not in st.session_state:
    st.session_state.api_key = API_KEY

apply_custom_styles()
render_sidebar()

st.title(chr(0x1f9e0) + " " + APP_TITLE)
st.caption(APP_SUBTITLE)

chat_tab, ingest_tab, eval_tab = st.tabs(["Chat", "Ingest", "Eval"])

with chat_tab:
    render_chat_tab()

with ingest_tab:
    render_ingest_tab()

with eval_tab:
    render_eval_tab()

execute_pending()
