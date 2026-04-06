import streamlit as st

import api_client


def require_api() -> None:
    if api_client.health():
        return
    st.error("API недоступен.")
    st.markdown(api_client.api_unreachable_hint())
    st.stop()
