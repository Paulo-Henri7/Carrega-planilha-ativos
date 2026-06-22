import streamlit as st
from services.ativos_service import carregar_ativos as _carregar_ativos


@st.cache_data(ttl=600)
def carregar_ativos_cached():
    """Versão cacheada de carregar_ativos com TTL de 10 minutos."""
    return _carregar_ativos()


def limpar_cache():
    st.cache_data.clear()
