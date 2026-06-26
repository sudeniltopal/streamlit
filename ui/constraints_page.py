"""Constraints page: define data-driven constraints without touching code.

The form renders different parameter widgets depending on the chosen
:class:`ConstraintType`, then stores a plain ``params`` dict. The solver's
handler registry interprets it -- so this page needs no change when a new
constraint type/handler is added (only the ``_param_form`` dispatch below and
a label in ``TYPE_LABELS_TR``).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from context import AppContext
from models.constraint import Constraint, ConstraintType

# Turkish display labels for each constraint type. The stored enum *values*
# stay in English so existing database rows keep working.
TYPE_LABELS_TR = {
    ConstraintType.MUST_WORK_TOGETHER: "Birlikte Çalışmalı",
    ConstraintType.CANNOT_WORK_TOGETHER: "Birlikte Çalışamaz",
    ConstraintType.ONLY_RESPONSIBLE: "Yalnız Sorumlu Asistan",
    ConstraintType.FORBIDDEN_ASSISTANT: "Yasaklı Asistan",
    ConstraintType.MAX_DAILY: "Günlük Maksimum",
    ConstraintType.MAX_WEEKLY: "Haftalık Maksimum",
    ConstraintType.PREFERRED_ASSISTANT: "Tercih Edilen Asistan",
    ConstraintType.EVENING_RULE: "Akşam Kuralı",
}


def _type_label(t: ConstraintType) -> str:
    return TYPE_LABELS_TR.get(t, t.value)


def _assistant_picker(label: str, name_by_id: dict, key: str,
                      default=None, allow_all: bool = False):
    ids = list(name_by_id.keys())
    if allow_all:
        ids = [None] + ids
    return st.selectbox(
        label, ids, key=key,
        index=ids.index(default) if default in ids else 0,
        format_func=lambda i: "Tüm asistanlar" if i is None
        else name_by_id.get(i, f"#{i}"))


def _param_form(ctype: ConstraintType, name_by_id: dict,
                exam_label_by_id: dict) -> dict:
    """Render type-specific inputs and return the params dict."""
    p: dict = {}
    if ctype in (ConstraintType.MUST_WORK_TOGETHER,
                 ConstraintType.CANNOT_WORK_TOGETHER):
        p["assistant_a"] = _assistant_picker("A Asistanı", name_by_id, "ca")
        p["assistant_b"] = _assistant_picker("B Asistanı", name_by_id, "cb")
        if ctype == ConstraintType.MUST_WORK_TOGETHER:
            p["evening_only"] = st.checkbox(
                "Yalnızca akşam sınavlarına uygula (başlangıç ≥ 17:30)")
    elif ctype == ConstraintType.ONLY_RESPONSIBLE:
        p["exam_id"] = st.selectbox(
            "Sınav", list(exam_label_by_id.keys()),
            format_func=lambda i: exam_label_by_id[i])
    elif ctype == ConstraintType.FORBIDDEN_ASSISTANT:
        p["exam_id"] = st.selectbox(
            "Sınav", list(exam_label_by_id.keys()),
            format_func=lambda i: exam_label_by_id[i])
        p["assistant_id"] = _assistant_picker("Yasaklı asistan",
                                              name_by_id, "cf")
    elif ctype == ConstraintType.PREFERRED_ASSISTANT:
        p["exam_id"] = st.selectbox(
            "Sınav", list(exam_label_by_id.keys()),
            format_func=lambda i: exam_label_by_id[i])
        p["assistant_id"] = _assistant_picker("Tercih edilen asistan",
                                              name_by_id, "cp")
        p["weight"] = st.slider("Tercih ağırlığı", 1, 50, 5)
    elif ctype == ConstraintType.MAX_DAILY:
        p["assistant_id"] = _assistant_picker("Kapsam", name_by_id,
                                              "cmd", allow_all=True)
        p["limit"] = st.number_input("Günlük maksimum sınav", 1, 20, 2)
    elif ctype == ConstraintType.MAX_WEEKLY:
        p["assistant_id"] = _assistant_picker("Kapsam", name_by_id,
                                              "cmw", allow_all=True)
        p["limit"] = st.number_input("Haftalık maksimum sınav", 1, 50, 5)
        p["week_start"] = st.date_input("Hafta başlangıcı (Pazartesi)",
                                        value=date.today()).isoformat()
    elif ctype == ConstraintType.EVENING_RULE:
        p["assistant_id"] = _assistant_picker("Kapsam", name_by_id,
                                              "cer", allow_all=True)
        p["max_evening"] = st.number_input("Tercih edilen maksimum akşam görevi",
                                           0, 20, 1)
        p["weight"] = st.slider("Ağırlık", 1, 50, 8)
    return p


def render(ctx: AppContext) -> None:
    st.header("Kısıtlar")
    constraints = ctx.constraints.list_all()
    assistants = ctx.assistants.list_all()
    exams = ctx.exams.list_all()
    name_by_id = {a.id: a.name for a in assistants}
    exam_label_by_id = {e.id: f"{e.course_code} ({e.day})" for e in exams}

    if constraints:
        df = pd.DataFrame([{
            "ID": c.id, "Tür": _type_label(c.type),
            "Katı/Esnek": "Katı" if c.is_hard else "Esnek",
            "Aktif": "✅" if c.enabled else "⬜",
            "Parametreler": str(c.params),
            "Açıklama": c.description,
        } for c in constraints])
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.caption("Mevcut bir kısıtı aç/kapat ya da sil:")
        cols = st.columns(3)
        target_id = cols[0].selectbox(
            "Kısıt", [c.id for c in constraints],
            format_func=lambda i: f"#{i}")
        if cols[1].button("Aktif Et / Pasif Et"):
            cur = next(c for c in constraints if c.id == target_id)
            ctx.constraints.set_enabled(target_id, not cur.enabled)
            st.rerun()
        if cols[2].button("Sil", type="secondary"):
            ctx.constraints.delete(target_id)
            st.rerun()
    else:
        st.info("Henüz kısıt tanımlanmadı. Yedi yapısal katı kısıt (zaman "
                "çakışması, uygunluk, gerekli sayı, maksimum iş yükü vb.) her "
                "zaman otomatik olarak uygulanır.")

    st.divider()
    st.subheader("Kısıt ekle")

    ctype = st.selectbox("Kısıt türü", list(ConstraintType),
                         format_func=_type_label)
    params = _param_form(ctype, name_by_id, exam_label_by_id)
    description = st.text_input("Açıklama (isteğe bağlı)")

    if st.button("Kısıtı ekle", type="primary"):
        a, b = params.get("assistant_a"), params.get("assistant_b")
        if a is not None and a == b:
            st.error("A ve B asistanları farklı olmalıdır.")
        else:
            ctx.constraints.add(Constraint(type=ctype, params=params,
                                           description=description))
            st.success("Kısıt eklendi.")
            st.rerun()
