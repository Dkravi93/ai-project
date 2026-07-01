
"""Chat panel: conversation with citations, traces, and guardrail display."""
import streamlit as st
from ui.utils.api_client import chat


def render_chat_tab():
    st.subheader("Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None
    _render_messages()
    prompt = st.chat_input("Ask about your documents...", max_chars=2000)
    if prompt and prompt.strip():
        _send_message(prompt.strip())
    st.caption("Press Enter to send")


def _render_messages():
    msgs = st.session_state.get("messages", [])
    if not msgs:
        st.info("No messages yet. Ask a question or upload docs in the **Ingest** tab.", icon=chr(0x1f4ac))
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Summarize docs", use_container_width=True, type="secondary"):
                _send_message("Summarize my indexed documents")
        with col2:
            if st.button("What can I do?", use_container_width=True, type="secondary"):
                _send_message("What capabilities do you have?")
        with col3:
            if st.button("List documents", use_container_width=True, type="secondary"):
                _send_message("What documents are indexed?")
        return
    for msg in msgs:
        with st.chat_message(msg["role"]):
            st.markdown(msg.get("content", ""))
            if msg["role"] == "assistant" and msg.get("details"):
                _render_details(msg["details"])


def _render_details(details):
    with st.expander("Response details", expanded=False):
        tabs = st.tabs(["Metrics", "Citations", "Agent Trace", "Guardrails", "Errors"])
        with tabs[0]:
            conf = details.get("confidence")
            lat = details.get("latency_ms")
            tid = details.get("trace_id")
            c1, c2, c3 = st.columns(3)
            with c1:
                if conf is not None:
                    st.metric("Confidence", f"{conf:.1%}")
                else:
                    st.metric("Confidence", "N/A")
            with c2:
                st.metric("Latency", f"{lat:.0f}ms" if lat else "N/A")
            with c3:
                if tid:
                    st.caption("Trace: " + str(tid)[:20] + "...")
        with tabs[1]:
            cit = details.get("citations", [])
            if cit:
                import pandas as pd
                st.dataframe(pd.DataFrame(cit), use_container_width=True, hide_index=True)
                st.caption(str(len(cit)) + " citation(s)")
            else:
                st.caption("No citations")
        with tabs[2]:
            trace = details.get("agent_trace", [])
            if trace:
                for step in trace:
                    agent = step.get("agent", "?")
                    summary = step.get("summary") or step.get("output_summary", "")
                    ts = step.get("timestamp", "")
                    icon_map = {"supervisor": chr(0x1f9e0), "retriever": chr(0x1f4c4),
                                "coder": chr(0x1f4bb), "web_search": chr(0x1f310),
                                "writer": chr(0x270d)+chr(0xfe0f)}
                    icon = icon_map.get(agent, chr(0x2699)+chr(0xfe0f))
                    st.markdown(
                        "<div style='padding:0.3rem 0; border-left:3px solid #4F8BF9; padding-left:0.5rem; margin:0.2rem 0; font-size:0.85rem;'>"
                        "<strong>" + icon + " " + agent.title() + "</strong>"
                        "<br/><span style='color:#555;'>" + summary[:200] + "</span>"
                        "</div>",
                        unsafe_allow_html=True)
            else:
                st.caption("No agent trace")
        with tabs[3]:
            gr = details.get("guardrails", {})
            if gr:
                for gr_name, gr_data in gr.items():
                    st.markdown("**" + gr_name.replace("_", " ").title() + "**")
                    if isinstance(gr_data, dict):
                        for k, v in gr_data.items():
                            if isinstance(v, bool):
                                badge = "PASS" if not v else "FAIL"
                                st.caption("  " + k + ": " + badge)
                            elif isinstance(v, (int, float)):
                                st.caption("  " + k + ": " + f"{v:.3f}")
            else:
                st.caption("No guardrail data")
        with tabs[4]:
            errs = details.get("errors", [])
            if errs:
                for e in errs:
                    st.error(str(e), icon=chr(0x274c))
            else:
                st.success("No errors", icon=chr(0x2705))


def _send_message(text):
    if text == st.session_state.get("pending_query"):
        return
    st.session_state.pending_query = text
    st.session_state.messages.append({"role": "user", "content": text})
    st.session_state.messages.append({"role": "assistant", "content": "", "details": None, "status": "pending"})
    st.rerun()


def execute_pending():
    msgs = st.session_state.get("messages", [])
    if not msgs:
        return
    last = msgs[-1]
    if last.get("status") != "pending":
        return
    # Find the user message before this assistant message
    user_msg = None
    for m in reversed(msgs[:-1]):
        if m["role"] == "user":
            user_msg = m["content"]
            break
    if not user_msg:
        last["status"] = "error"
        last["content"] = "Error: No user message found"
        return
    doc_ids = st.session_state.get("ingested_doc_ids", [])
    sid = st.session_state.get("session_id", "default")
    last["status"] = "executing"
    with st.spinner("Running agent graph..."):
        r = chat(user_msg, sid, doc_ids)
    if r.success:
        d = r.data or {}
        last["content"] = d.get("answer") or "No answer returned."
        last["details"] = {
            "confidence": d.get("confidence"),
            "latency_ms": d.get("latency_ms") or r.latency_ms,
            "trace_id": d.get("trace_id"),
            "citations": d.get("citations", []),
            "agent_trace": d.get("agent_trace", []),
            "guardrails": d.get("guardrails", {}),
            "errors": d.get("errors", []),
        }
        last["status"] = "done"
        if len(st.session_state.messages) > 100:
            st.session_state.messages = st.session_state.messages[-100:]
    else:
        last["content"] = r.error or "An unknown error occurred"
        last["details"] = {"errors": [r.error or "Unknown error"]}
        last["status"] = "error"
    st.rerun()
