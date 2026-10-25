"""Session state and shared context management for the Streamlit dashboard."""

import os
from typing import Optional

import streamlit as st

from artemis.db import ArtemisRepository
from artemis.llm import LLMProvider, get_llm_provider
from artemis.service import ArtemisScoutingService

DEFAULT_DB_PATH = os.getenv("ARTEMIS_DB_PATH", "artemis.db")


def init_session_state() -> None:
    """Initialize necessary keys in Streamlit session state."""
    if "db_path" not in st.session_state:
        st.session_state["db_path"] = DEFAULT_DB_PATH

    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "Dashboard"

    if "selected_professor_id" not in st.session_state:
        st.session_state["selected_professor_id"] = None

    if "selected_paper_id" not in st.session_state:
        st.session_state["selected_paper_id"] = None

    if "selected_draft_id" not in st.session_state:
        st.session_state["selected_draft_id"] = None

    if "notification" not in st.session_state:
        st.session_state["notification"] = None


def get_db_path() -> str:
    """Return the active database path."""
    return st.session_state.get("db_path", DEFAULT_DB_PATH)


def set_db_path(path: str) -> None:
    """Set the active database path and reset cached resources."""
    st.session_state["db_path"] = path.strip()
    if "_cached_repo" in st.session_state:
        del st.session_state["_cached_repo"]
    if "_cached_service" in st.session_state:
        del st.session_state["_cached_service"]


def get_repository() -> ArtemisRepository:
    """Retrieve or initialize the cached ArtemisRepository."""
    db_path = get_db_path()
    # Cache per session state
    cached_repo = st.session_state.get("_cached_repo")
    cached_path = st.session_state.get("_cached_db_path")
    if cached_repo and cached_path == db_path:
        return cached_repo

    repo = ArtemisRepository(db=db_path)
    st.session_state["_cached_repo"] = repo
    st.session_state["_cached_db_path"] = db_path
    return repo


def get_service() -> ArtemisScoutingService:
    """Retrieve or initialize the cached ArtemisScoutingService."""
    repo = get_repository()
    cached_service = st.session_state.get("_cached_service")
    if cached_service and cached_service.repo == repo:
        return cached_service

    service = ArtemisScoutingService(repo=repo)
    st.session_state["_cached_service"] = service
    return service


def get_active_llm_provider(provider_type: Optional[str] = None) -> LLMProvider:
    """Return configured LLM provider (mock or gemini)."""
    return get_llm_provider(provider_name=provider_type)
