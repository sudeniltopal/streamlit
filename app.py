"""Streamlit entry point for the Exam Invigilation Assignment System.

Run with:  streamlit run app.py

User-facing text is Turkish; code, identifiers and comments stay in English so
the project remains maintainable. State lives in SQLite (``exam_system.db``)
and survives restarts; only the in-memory solve result is session-scoped.
"""
from __future__ import annotations

import streamlit as st

from context import AppContext
from scripts.seed_data import seed
from ui import (assistants_page, constraints_page, dashboard, exams_page,
                optimization_page)

st.set_page_config(page_title="Sınav Gözetmenlik Sistemi",
                   page_icon="📝", layout="wide")


@st.cache_resource
def get_context() -> AppContext:
    """One AppContext per server process (cached across reruns)."""
    return AppContext()


def main() -> None:
    ctx = get_context()

    st.sidebar.title("📝 Gözetmenlik Sistemi")
    page = st.sidebar.radio(
        "Menü",
        ["Kontrol Paneli", "Asistanlar", "Sınavlar", "Kısıtlar", "Optimizasyon"])

    st.sidebar.divider()
    if st.sidebar.button("Örnek veri yükle"):
        seed(ctx.db)
        st.session_state.pop("solve_result", None)
        st.sidebar.success("Örnek veri yüklendi.")
        st.rerun()
    if st.sidebar.button("Tüm verileri temizle"):
        ctx.db.reset()
        st.session_state.pop("solve_result", None)
        st.sidebar.success("Tüm veriler temizlendi.")
        st.rerun()

    # Keys must match the radio labels above.
    pages = {
        "Kontrol Paneli": dashboard.render,
        "Asistanlar": assistants_page.render,
        "Sınavlar": exams_page.render,
        "Kısıtlar": constraints_page.render,
        "Optimizasyon": optimization_page.render,
    }
    pages[page](ctx)


if __name__ == "__main__":
    main()
