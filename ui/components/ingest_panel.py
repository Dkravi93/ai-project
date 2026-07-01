
"""Ingest panel: document upload with validation and progress."""
import streamlit as st
from ui.utils.api_client import ingest_document


def render_ingest_tab():
    st.subheader("Ingest Documents")
    if "ingested_docs" not in st.session_state:
        st.session_state.ingested_docs = []
    if "ingested_doc_ids" not in st.session_state:
        st.session_state.ingested_doc_ids = []
    _render_upload()
    _render_history()


def _render_upload():
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader(
            "Choose a document", type=["txt", "md", "pdf", "docx"],
            label_visibility="collapsed",
        )
    with col2:
        doc_id = st.text_input("Doc ID", placeholder="optional", help="A stable identifier")
    if uploaded is not None:
        fb = uploaded.getvalue()
        fsz = len(fb) / 1024
        # Validate
        bad_type = _validate_ext(uploaded.name)
        bad_size = len(fb) > 50 * 1024 * 1024
        with st.container(border=True):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.markdown("**" + uploaded.name + "**")
            with cols[1]:
                if fsz < 1024:
                    st.caption(f"{fsz:.1f} KB")
                else:
                    st.caption(f"{fsz / 1024:.1f} MB")
            with cols[2]:
                st.caption(uploaded.type or "unknown")
            if bad_type:
                st.error(bad_type, icon=chr(0x26a0))
                return
            if bad_size:
                st.error("File exceeds 50MB limit", icon=chr(0x26a0))
                return
            if st.button("Ingest Document", use_container_width=True, type="primary", key="ingest_btn"):
                _do_ingest(uploaded, fb, doc_id)


def _validate_ext(filename):
    exts = {"txt", "md", "pdf", "docx"}
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in exts:
        return "Unsupported file type . Supported: " + ", ".join(sorted(exts))
    return None


def _do_ingest(uploaded, fb, doc_id):
    with st.status("Indexing document...", expanded=True) as status:
        st.write("Sending to API...")
        r = ingest_document(fb, uploaded.name, uploaded.type or "application/octet-stream", doc_id or None)
        if r.success:
            d = r.data or {}
            status.update(label="Document indexed successfully!", state="complete")
            st.success("**" + str(d.get("chunks_indexed", 0)) + "** chunks indexed")
            with st.expander("Response details", expanded=False):
                st.json(d)
            did = d.get("doc_id") or doc_id or uploaded.name
            if did not in st.session_state.ingested_doc_ids:
                st.session_state.ingested_doc_ids.append(did)
            st.session_state.ingested_docs.append({
                "filename": uploaded.name,
                "doc_id": did,
                "chunks": d.get("chunks_indexed", 0),
            })
            st.info("Ready! Switch to the **Chat** tab to ask questions.", icon=chr(0x1f4a1))
        else:
            status.update(label="Ingestion failed", state="error")
            st.error(r.error or "Unknown error during ingestion")


def _render_history():
    docs = st.session_state.get("ingested_docs", [])
    if not docs:
        st.info("No documents ingested yet. Upload a file above.", icon=chr(0x1f4c4))
        return
    st.divider()
    st.markdown("**Ingested Documents** (" + str(len(docs)) + " total)")
    for i, doc in enumerate(reversed(docs)):
        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.markdown("**" + doc.get("filename", "?") + "**")
                if doc.get("doc_id"):
                    st.caption("ID: " + doc["doc_id"])
            with cols[1]:
                st.metric("Chunks", doc.get("chunks", 0))
            with cols[2]:
                if st.button("Remove", key="rm_" + str(i), use_container_width=True, type="secondary"):
                    did = doc.get("doc_id")
                    if did and did in st.session_state.ingested_doc_ids:
                        st.session_state.ingested_doc_ids.remove(did)
                    st.session_state.ingested_docs.remove(doc)
                    st.rerun()
