"""Custom CSS styles for AgentOps Hub UI."""
import streamlit as st
def apply_custom_styles():
    st.markdown("""
    <style>
        .main > div { padding-bottom: 2rem; }
        .stChatMessage { border-radius: 12px; padding: 1rem; margin-bottom: 0.5rem; }
        div[data-testid="metric-container"] {
            background: #f0f2f6; border-radius: 10px; padding: 1rem 0.8rem;
            border: 1px solid #e0e3e9;
        }
        section[data-testid="stSidebar"] { width: 300px !important; }
        .stFileUploader > div { border: 2px dashed #ccc; border-radius: 12px; padding: 1.5rem; }
        .stFileUploader > div:hover { border-color: #4F8BF9; }
        .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
        .status-dot.ok { background: #0f9d58; }
        .status-dot.degraded { background: #f4b400; }
        .status-dot.error { background: #db4437; }
        .confidence-high { color: #0f9d58; font-weight: 600; }
        .confidence-mid { color: #f4b400; font-weight: 600; }
        .confidence-low { color: #db4437; font-weight: 600; }
        .guardrail-tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px;
                         font-size: 0.75rem; font-weight: 500; margin: 0.15rem; }
        .guardrail-pass { background: #e6f4ea; color: #1e7e34; }
        .guardrail-fail { background: #fce8e6; color: #c5221f; }
        .guardrail-warn { background: #fef7e0; color: #e37400; }
        .trace-step { padding: 0.4rem 0.8rem; border-left: 3px solid #4F8BF9; margin: 0.3rem 0; font-size: 0.85rem; }
        .trace-step.supervisor { border-left-color: #673ab7; }
        .trace-step.retriever { border-left-color: #2196f3; }
        .trace-step.coder { border-left-color: #ff9800; }
        .trace-step.web_search { border-left-color: #00bcd4; }
        .trace-step.writer { border-left-color: #4caf50; }
    </style>
    """, unsafe_allow_html=True)
