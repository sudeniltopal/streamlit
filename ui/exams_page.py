"""Exams page: add / edit / delete exams.

The ``department_type`` values are stored in English ("Internal"/"External")
because the solver and reports key off them; only their *display* is Turkish.
"""
from __future__ import annotations

from datetime import date, time

import pandas as pd
import streamlit as st

from context import AppContext
from models.exam import Exam

# Stored value -> Turkish label (and back for the form default).
DEPT_TYPE_TR = {"Internal": "Bölüm İçi", "External": "Bölüm Dışı"}


def render(ctx: AppContext) -> None:
    st.header("Sınavlar")
    exams = ctx.exams.list_all()
    assistants = ctx.assistants.list_all()
    name_by_id = {a.id: a.name for a in assistants}

    if exams:
        df = pd.DataFrame([{
            "ID": e.id, "Tarih": e.day.isoformat(),
            "Saat": f"{e.start:%H:%M}–{e.end:%H:%M}",
            "Ders Kodu": e.course_code, "Ders Adı": e.course_name,
            "Tür": DEPT_TYPE_TR.get(e.department_type, e.department_type),
            "Gerekli": e.required_invigilators,
            "Sorumlu": ", ".join(name_by_id.get(i, f"#{i}")
                                 for i in e.responsible_assistant_ids),
            "Yalnız sorumlu": "Evet" if e.only_responsible else "",
            "Yer": e.location,
        } for e in exams])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz sınav yok — aşağıdan ekleyin.")

    st.divider()

    options = {0: "➕ Yeni sınav"} | {e.id: f"{e.course_code} ({e.day})"
                                      for e in exams}
    chosen = st.selectbox("Yeni ekle veya mevcut olanı düzenle", options.keys(),
                          format_func=lambda k: options[k])
    editing = next((e for e in exams if e.id == chosen), None)

    with st.form("exam_form"):
        c1, c2 = st.columns(2)
        code = c1.text_input("Ders kodu",
                             value=editing.course_code if editing else "")
        cname = c2.text_input("Ders adı",
                              value=editing.course_name if editing else "")
        dtype = c1.selectbox(
            "Bölüm türü", ["Internal", "External"],
            index=0 if not editing or editing.department_type == "Internal"
            else 1,
            format_func=lambda v: DEPT_TYPE_TR[v])
        day = c2.date_input("Tarih",
                            value=editing.day if editing else date.today())
        start = c1.time_input("Başlangıç saati",
                              value=editing.start if editing else time(9, 0))
        end = c2.time_input("Bitiş saati",
                            value=editing.end if editing else time(11, 0))
        required = c1.number_input("Gerekli gözetmen sayısı", 1, 20,
                                   value=editing.required_invigilators
                                   if editing else 1)
        location = c2.text_input("Yer",
                                 value=editing.location if editing else "")
        resp = st.multiselect(
            "Sorumlu asistan(lar)", options=list(name_by_id.keys()),
            default=editing.responsible_assistant_ids if editing else [],
            format_func=lambda i: name_by_id.get(i, f"#{i}"))
        only_resp = st.checkbox(
            "Yalnızca sorumlu asistanlar gözetmenlik yapabilir (katı kısıt)",
            value=editing.only_responsible if editing else False)
        notes = st.text_area("Özel notlar",
                             value=editing.notes if editing else "")

        if st.form_submit_button("Kaydet"):
            if not code.strip():
                st.error("Ders kodu zorunludur.")
            elif end <= start:
                st.error("Bitiş saati başlangıç saatinden sonra olmalıdır.")
            else:
                model = Exam(
                    id=editing.id if editing else None,
                    course_code=code.strip(), course_name=cname,
                    department_type=dtype, day=day, start=start, end=end,
                    required_invigilators=int(required),
                    responsible_assistant_ids=list(resp),
                    only_responsible=only_resp, location=location, notes=notes)
                if editing:
                    ctx.exams.update(model)
                    st.success(f"{code} güncellendi.")
                else:
                    ctx.exams.add(model)
                    st.success(f"{code} eklendi.")
                st.rerun()

    if editing:
        if st.button(f"🗑 {editing.course_code} sil", type="secondary"):
            ctx.exams.delete(editing.id)
            st.success(f"{editing.course_code} silindi.")
            st.rerun()
