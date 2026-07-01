
"""Centralized API client with retry, timeout, and precise error handling."""
import json, time, os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
import requests
import streamlit as st
from ui.config import API_BASE_URL, API_KEY, API_TIMEOUT_CHAT, API_TIMEOUT_INGEST, API_TIMEOUT_DEFAULT


@dataclass
class APIResult:
    success: bool
    data: Optional[dict | list] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    status_code: Optional[int] = None
    latency_ms: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    def __bool__(self):
        return self.success


class APIClientError(Exception): pass
class APIConnectionError(APIClientError): pass
class APIAuthError(APIClientError): pass
class APIValidationError(APIClientError): pass
class APITimeoutError(APIClientError): pass
class APIServerError(APIClientError): pass
class APIRateLimitError(APIClientError): pass


def _classify(status_code, detail=""):
    if status_code is None:
        return APIConnectionError("Connection refused")
    if status_code in (401, 403):
        return APIAuthError(detail)
    if status_code == 422:
        return APIValidationError(detail or "Validation failed")
    if status_code == 429:
        return APIRateLimitError(detail or "Rate limited")
    if 400 <= status_code < 500:
        return APIValidationError(detail)
    if status_code >= 500:
        return APIServerError(detail)
    return APIClientError(detail)


ERROR_TEMPLATES = {}

_ERROR_CONN_REFUSED = (
    "**Connection refused** - The API server is not reachable."
    + os.linesep * 2
    + "- Ensure FastAPI is running: uvicorn api.main:app"
    + os.linesep
    + "- Check the API URL in the sidebar"
)
ERROR_TEMPLATES["connection"] = _ERROR_CONN_REFUSED

_ERROR_AUTH = (
    "**Authentication failed** - The API key was rejected."
    + os.linesep * 2
    + "- Check the API key in the sidebar"
)
ERROR_TEMPLATES["auth"] = _ERROR_AUTH

_ERROR_TIMEOUT = (
    "**Request timed out**. The server may be overloaded."
    + os.linesep * 2
    + "- Try a simpler query or smaller document"
)
ERROR_TEMPLATES["timeout"] = _ERROR_TIMEOUT

_ERROR_RATE = (
    "**Rate limited** - Too many requests."
    + os.linesep * 2
    + "- Wait before sending another request"
)
ERROR_TEMPLATES["rate"] = _ERROR_RATE


def _fmt_err(category, detail=""):
    tpl = ERROR_TEMPLATES.get(category)
    if not tpl:
        return "**Error**: " + str(detail)
    return tpl + os.linesep + str(detail) if detail else tpl


def _request(method, path, headers_extra=None, json_data=None, files=None,
             data=None, timeout=15, max_retries=1, retry_delay=1.0):
    api_base = (
        st.session_state.get("api_base_url", API_BASE_URL).rstrip("/")
        if "api_base_url" in st.session_state
        else API_BASE_URL.rstrip("/")
    )
    url = api_base + path
    api_key = (
        st.session_state.get("api_key", API_KEY)
        if "api_key" in st.session_state
        else API_KEY
    )
    headers = {"X-API-Key": api_key} if api_key else {}
    if headers_extra:
        headers.update(headers_extra)
    start = time.monotonic()
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(
                method, url, headers=headers,
                json=json_data if not files else None,
                data=data, files=files, timeout=timeout,
            )
            lat = (time.monotonic() - start) * 1000
            if resp.ok:
                try:
                    d = resp.json()
                except Exception:
                    d = {"raw": resp.text}
                return APIResult(
                    success=True, data=d,
                    status_code=resp.status_code,
                    latency_ms=round(lat, 1),
                )
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text[:500]
            # Classify error
            if resp.status_code in (401, 403):
                cat = "auth"
            elif resp.status_code == 429:
                cat = "rate"
            elif resp.status_code >= 500:
                cat = "server"
            elif resp.status_code == 422:
                cat = "validation"
            else:
                cat = "other"
            if cat in ("auth", "validation"):
                return APIResult(
                    success=False,
                    error=_fmt_err(cat, str(detail)),
                    error_type=cat.upper() + "Error",
                    status_code=resp.status_code,
                )
            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return APIResult(
                success=False,
                error=_fmt_err(cat, str(detail)) if cat != "other" else "HTTP " + str(resp.status_code) + ": " + str(detail)[:200],
                error_type=cat.upper() + "Error",
                status_code=resp.status_code,
            )
        except requests.exceptions.ConnectionError:
            lat = (time.monotonic() - start) * 1000
            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return APIResult(
                success=False,
                error=_fmt_err("connection"),
                error_type="ConnectionError",
                latency_ms=round(lat, 1),
            )
        except requests.exceptions.Timeout:
            lat = (time.monotonic() - start) * 1000
            if attempt < max_retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return APIResult(
                success=False,
                error=_fmt_err("timeout"),
                error_type="TimeoutError",
                latency_ms=round(lat, 1),
            )
        except requests.exceptions.RequestException as e:
            lat = (time.monotonic() - start) * 1000
            return APIResult(
                success=False,
                error="**Network error**: " + str(e)[:300],
                error_type="RequestException",
                latency_ms=round(lat, 1),
            )
    return APIResult(
        success=False, error="Max retries exceeded",
        error_type="MaxRetriesError",
    )


def health_check():
    return _request("GET", "/health", timeout=API_TIMEOUT_DEFAULT)


def chat(query, session_id, doc_ids=None):
    return _request(
        "POST", "/chat",
        json_data={"query": query, "session_id": session_id, "doc_ids": doc_ids or []},
        timeout=API_TIMEOUT_CHAT,
        max_retries=1,
    )


def ingest_document(file_content, filename, file_type, doc_id=None):
    files = {"file": (filename, file_content, file_type)}
    data = {"doc_id": doc_id} if doc_id else {}
    return _request("POST", "/ingest", files=files, data=data, timeout=API_TIMEOUT_INGEST)


def init_collection():
    return _request("POST", "/api/admin/init-collection", timeout=API_TIMEOUT_DEFAULT)


def collection_status():
    return _request("GET", "/api/admin/collection", timeout=API_TIMEOUT_DEFAULT)


def eval_latest():
    return _request("GET", "/eval/latest", timeout=API_TIMEOUT_DEFAULT)
