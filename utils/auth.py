import streamlit as st


def obter_usuario():
    try:
        return st.context.headers.get("X-Forwarded-Email", "usuario_desconhecido")
    except Exception:
        return "usuario_desconhecido"
