import streamlit as st

import api_client
from streamlit_app.ui_guard import require_api

st.set_page_config(page_title="Справочник", layout="wide")
st.title("Справочник процессов и загруженные документы")

require_api()

st.subheader("Каталог (из business_processes.json → БД)")
try:
    procs = api_client.list_processes()
    st.dataframe(procs, width="stretch", hide_index=True)
except Exception as e:
    st.error(str(e))

st.subheader("Документы в базе")
try:
    docs = api_client.list_documents()
    st.dataframe(docs, width="stretch", hide_index=True)
except Exception as e:
    st.error(str(e))

st.caption("Поле `content_sha256` используйте на странице «Документ по хэшу».")
