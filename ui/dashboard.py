"""Dashboard page: high-level counts and the latest assignment status."""
from __future__ import annotations

import streamlit as st

from context import AppContext


def render(ctx: AppContext) -> None:
    st.header("Kontrol Paneli")

    assistants = ctx.assistants.list_all()
    exams = ctx.exams.list_all()
    assignments = ctx.assignments.list_all()

    required_total = sum(e.required_invigilators for e in exams)
    avg = round(required_total / len(assistants), 2) if assistants else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Asistanlar", len(assistants))
    col2.metric("Sınavlar", len(exams))
    col3.metric("Asistan başına ort. gözetmenlik", avg)
    status = "Oluşturuldu" if assignments else "Oluşturulmadı"
    col4.metric("Atama durumu", status)

    st.divider()

    if not assistants or not exams:
        st.info("Asistan ve sınav ekleyin, ardından çizelge oluşturmak için "
                "**Optimizasyon** sekmesine gidin.")
        return

    if assignments:
        st.success(f"Şu anda {len(assignments)} atama kaydı saklanıyor. "
                   "İncelemek veya yeniden oluşturmak için **Optimizasyon** "
                   "sekmesini açın.")
    else:
        st.warning("Henüz çizelge oluşturulmadı. **Optimizasyon → "
                   "Çizelge Oluştur** adımına gidin.")

    # Quick demand-vs-capacity sanity bar.
    capacity = sum(max(0, a.max_invigilations - a.current_count)
                   for a in assistants)
    st.caption(f"Toplam gözetmen ihtiyacı: **{required_total}** · "
               f"Toplam kalan kapasite: **{capacity}**")
    if required_total > capacity:
        st.error("İhtiyaç kapasiteyi aşıyor — asistan ekleyene veya üst "
                 "limitleri artırana kadar çizelge oluşturulamaz.")
