"""Eval panel: evaluation metrics dashboard."""
import streamlit as st
from ui.utils.api_client import eval_latest


def render_eval_tab():
    st.subheader("Evaluation")
    if st.button("Load Latest Eval", use_container_width=True, type="primary"):
        _load_eval()
    if "eval_data" in st.session_state:
        _render_dashboard()
    else:
        st.info("No evaluation data loaded. Click **Load Latest Eval** above.", icon=chr(0x1f4ca))
        st.markdown("### Expected Metrics")
        t = """| Metric | Tool | Target |
|---|---|---|
| Faithfulness | RAGAS | > 0.75 |
| Answer Relevance | RAGAS | > 0.80 |
| Context Precision | RAGAS | > 0.80 |
| Context Recall | RAGAS | > 0.70 |"""
        st.markdown(t)


def _load_eval():
    with st.spinner("Loading evaluation results..."):
        r = eval_latest()
    if r.success:
        st.session_state.eval_data = r.data
        st.rerun()
    else:
        st.error(r.error or "Failed to load evaluation data")


def _render_dashboard():
    d = st.session_state.eval_data or {}
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Run Date", str(d.get("run_date", "?"))[:10] if d.get("run_date") else "N/A")
    with col2:
        st.metric("Dataset Size", str(d.get("golden_dataset_size", 0)) + " Q&A")
    with col3:
        st.metric("Status", str(d.get("status", "?")).title())
    metrics = d.get("metrics", {})
    vs_prev = d.get("vs_previous", {})
    if metrics:
        st.divider()
        st.markdown("### Metrics")
        cols = st.columns(min(4, len(metrics)))
        for i, (k, v) in enumerate(metrics.items()):
            with cols[i % len(cols)]:
                delta = vs_prev.get(k)
                label = k.replace("_", " ").title()
                if isinstance(v, float) and v <= 1.0:
                    val = f"{v:.0%}"
                else:
                    val = str(v)
                st.metric(label=label, value=val, delta=delta)
