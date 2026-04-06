import streamlit as st

import api_client
from streamlit_app.ui_guard import require_api

st.set_page_config(page_title="Документ по хэшу", layout="wide")
st.title("Контекст по SHA-256")

require_api()

h = st.text_input("SHA-256 содержимого файла (64 hex)", placeholder="вставьте хэш из загрузки или списка документов")
if st.button("Загрузить") and h.strip():
    h = h.strip().lower()
    try:
        payload = api_client.document_by_hash(h)
    except Exception as e:
        st.error(f"Не найдено или ошибка: {e}")
        st.stop()
    meta = payload.get("document") or {}
    st.subheader("Метаданные")
    st.json(meta)
    st.subheader("Сущности (NER / аудит)")
    st.dataframe(payload.get("entities") or [], width="stretch", hide_index=True)
    st.subheader("Связи")
    st.dataframe(payload.get("relations") or [], width="stretch", hide_index=True)
    st.subheader("Цепочки")
    chains = payload.get("relation_chains") or []
    for c in chains:
        st.code(" → ".join(str(x) for x in c))
    st.subheader("Бизнес-процессы (из ответа модели)")
    st.dataframe(payload.get("business_processes") or [], width="stretch", hide_index=True)
