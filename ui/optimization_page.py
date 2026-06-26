"""Optimization page: run the solver and present results + exports."""
from __future__ import annotations

import streamlit as st

from context import AppContext
from models.assignment import Assignment, SolveStatus
from optimization.solver import InvigilationSolver
from reporting.exporters import export_excel, export_pdf
from reporting.reports import assignments_dataframe, workload_dataframe

# Turkish display labels for solver statuses.
STATUS_TR = {
    SolveStatus.OPTIMAL: "OPTİMAL",
    SolveStatus.FEASIBLE: "UYGUN",
    SolveStatus.INFEASIBLE: "UYGUN DEĞİL",
    SolveStatus.UNKNOWN: "BİLİNMİYOR",
}


def render(ctx: AppContext) -> None:
    st.header("Optimizasyon")

    assistants = ctx.assistants.list_all()
    exams = ctx.exams.list_all()
    constraints = ctx.constraints.list_all()

    if not assistants or not exams:
        st.warning("Önce en az bir asistan ve bir sınav ekleyin.")
        return

    time_limit = st.slider("Çözücü süre limiti (saniye)", 5, 120, 20)

    if st.button("⚙️ Çizelge Oluştur", type="primary"):
        with st.spinner("Atama problemi çözülüyor…"):
            solver = InvigilationSolver(assistants, exams, constraints,
                                        max_time_seconds=float(time_limit))
            result = solver.solve()
        # Persist both the result (for this session) and the assignments.
        st.session_state["solve_result"] = result
        if result.feasible:
            ctx.assignments.replace_all(
                [Assignment(exam_id=a.exam_id, assistant_id=a.assistant_id)
                 for a in result.assignments])

    result = st.session_state.get("solve_result")
    if result is None:
        st.info("Optimize etmek için **Çizelge Oluştur** düğmesine basın.")
        return

    status_label = STATUS_TR.get(result.status, result.status.value)

    # --- solver status -------------------------------------------------
    if result.feasible:
        st.success(f"Çözücü durumu: **{status_label}** "
                   f"({result.solve_time_seconds} sn)")
    else:
        st.error(f"Çözücü durumu: **{status_label}** — "
                 "uygun bir çizelge bulunamadı.")
        st.subheader("Kısıt İhlali Raporu")
        for d in result.diagnostics:
            st.markdown(f"- {d}")
        return

    # --- fairness metrics ---------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Bölüm ortalaması", result.department_average)
    c2.metric("İş yükü farkı (maks−min)", result.spread)
    c3.metric("Atama sayısı", len(result.assignments))

    st.subheader("Atamalar")
    st.dataframe(assignments_dataframe(result, assistants, exams),
                 use_container_width=True, hide_index=True)

    st.subheader("İş Yükü Özeti")
    st.dataframe(workload_dataframe(result),
                 use_container_width=True, hide_index=True)

    if result.warnings:
        st.subheader("Adalet Notları")
        for w in result.warnings:
            st.warning(w)

    # --- exports -------------------------------------------------------
    st.subheader("Dışa Aktar")
    col1, col2 = st.columns(2)
    col1.download_button(
        "⬇️ Excel İndir", data=export_excel(result, assistants, exams),
        file_name="gozetmenlik_cizelgesi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    col2.download_button(
        "⬇️ PDF İndir", data=export_pdf(result, assistants, exams),
        file_name="gozetmenlik_cizelgesi.pdf", mime="application/pdf")
