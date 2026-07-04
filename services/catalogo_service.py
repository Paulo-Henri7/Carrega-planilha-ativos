import pandas as pd
import streamlit as st

CATALOGO_PATH = "catalogo/modelos.csv"


@st.cache_data
def carregar_catalogo() -> pd.DataFrame:
    return pd.read_csv(CATALOGO_PATH)


def tipos_disponiveis() -> list[str]:
    df = carregar_catalogo()
    return sorted(df["tipo"].dropna().unique().tolist())


def modelos_por_tipo(tipo: str) -> list[str]:
    df = carregar_catalogo()
    return sorted(df[df["tipo"] == tipo]["modelo"].dropna().unique().tolist())


def tipo_do_modelo(modelo: str) -> str | None:
    """Busca reversa: dado um modelo, retorna o tipo correspondente no catálogo."""
    df = carregar_catalogo()
    resultado = df[df["modelo"] == modelo]
    return resultado["tipo"].iloc[0] if not resultado.empty else None