"""Assistants page: add / edit / delete assistants and their constraints."""
from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd
import streamlit as st

from context import AppContext
from models.assistant import Assistant, UnavailabilitySlot


def _parse_courses(text: str) -> list[str]:
    return [c.strip() for c in text.split(",") if c.strip()]


def _parse_unavailability(text: str) -> list[UnavailabilitySlot]:
    """Parse 'YYYY-MM-DD HH:MM-HH:MM' lines into unavailability slots."""
    slots: list[UnavailabilitySlot] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            day_part, time_part = line.split()
            start_s, end_s = time_part.split("-")
            slots.append(UnavailabilitySlot(
                day=date.fromisoformat(day_part),
                start=datetime.strptime(start_s, "%H:%M").time(),
                end=datetime.strptime(end_s, "%H:%M").time()))
        except ValueError:
            st.warning(f"Şu satır çözümlenemedi: '{line}' "
                       "(beklenen biçim: YIL-AY-GÜN SS:DD-SS:DD, "
                       "örn. 2026-05-15 08:00-23:00)")
    return slots


def _slots_to_text(slots: list[UnavailabilitySlot]) -> str:
    return "\n".join(f"{s.day.isoformat()} {s.start:%H:%M}-{s.end:%H:%M}"
                     for s in slots)


def render(ctx: AppContext) -> None:
    st.header("Asistanlar")
    assistants = ctx.assistants.list_all()

    if assistants:
        df = pd.DataFrame([{
            "ID": a.id, "Ad": a.name, "Ünvan": a.academic_status,
            "Bölüm": a.department, "Maks": a.max_invigilations,
            "Min": a.min_invigilations, "Mevcut": a.current_count,
            "Dersler": ", ".join(a.responsible_courses),
            "Müsait olmayan gün": len(a.unavailability),
        } for a in assistants])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz asistan yok — aşağıdan ekleyin.")

    st.divider()

    # --- add / edit form ----------------------------------------------
    options = {0: "➕ Yeni asistan"} | {a.id: a.name for a in assistants}
    chosen = st.selectbox("Yeni ekle veya mevcut olanı düzenle", options.keys(),
                          format_func=lambda k: options[k])
    editing = next((a for a in assistants if a.id == chosen), None)

    with st.form("assistant_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Ad", value=editing.name if editing else "")
        status = c2.text_input("Akademik ünvan",
                               value=editing.academic_status if editing else "")
        dept = c1.text_input("Bölüm",
                             value=editing.department if editing else "")
        email = c2.text_input("E-posta", value=editing.email if editing else "")
        max_inv = c1.number_input("Maksimum gözetmenlik", 0, 100,
                                  value=editing.max_invigilations if editing else 6)
        min_inv = c2.number_input("İstenen minimum gözetmenlik", 0, 100,
                                  value=editing.min_invigilations if editing else 0)
        current = c1.number_input("Mevcut atanmış sayı", 0, 100,
                                  value=editing.current_count if editing else 0)
        courses = st.text_input(
            "Sorumlu olduğu dersler (virgülle ayırın)",
            value=", ".join(editing.responsible_courses) if editing else "")
        unavail = st.text_area(
            "Müsait olmadığı zamanlar (her satıra bir tane: "
            "YIL-AY-GÜN SS:DD-SS:DD, örn. 2026-05-15 08:00-23:00)",
            value=_slots_to_text(editing.unavailability) if editing else "")
        notes = st.text_area("Kişisel notlar",
                             value=editing.personal_notes if editing else "")

        save = st.form_submit_button("Kaydet")
        if save:
            if not name.strip():
                st.error("Ad alanı zorunludur.")
            else:
                model = Assistant(
                    id=editing.id if editing else None,
                    name=name.strip(), academic_status=status,
                    department=dept, email=email,
                    max_invigilations=int(max_inv),
                    min_invigilations=int(min_inv), current_count=int(current),
                    responsible_courses=_parse_courses(courses),
                    unavailability=_parse_unavailability(unavail),
                    personal_notes=notes)
                if editing:
                    ctx.assistants.update(model)
                    st.success(f"{name} güncellendi.")
                else:
                    ctx.assistants.add(model)
                    st.success(f"{name} eklendi.")
                st.rerun()

    if editing:
        if st.button(f"🗑 {editing.name} sil", type="secondary"):
            ctx.assistants.delete(editing.id)
            st.success(f"{editing.name} silindi.")
            st.rerun()
