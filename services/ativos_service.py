import math
import pandas as pd
import streamlit as st
from db.queries import query_df, execute
from db.connection import get_connection
from config import TABELA, COLUNAS


def sanitizar_valor(v, eh_data=False):
    """
    Normaliza um valor antes de enviar como parâmetro SQL.
    Necessário porque o conector do Databricks não sabe inferir o tipo de
    um pandas.Timestamp (comum quando os dados vêm de planilha Excel ou
    de uma consulta SQL anterior) — precisa virar datetime.date nativo.
    NaN/NaT também viram None (NULL no banco).
    
    Args:
        v: Valor a normalizar
        eh_data: Se True, tenta converter para date ou retorna None se inválido
    """
    if v is None:
        return None
    
    # Se é um campo de data, fazer conversão ou retornar None
    if eh_data:
        if isinstance(v, pd.Timestamp):
            return None if pd.isna(v) else v.date()
        try:
            # Tentar converter string para data
            d = pd.to_datetime(v)
            return None if pd.isna(d) else d.date()
        except (ValueError, TypeError, AttributeError):
            # Se não conseguir converter, retornar None (NULL no banco)
            return None
    
    # Para valores não-data
    if isinstance(v, pd.Timestamp):
        return None if pd.isna(v) else v.date()
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def sanitizar_registro(dados: dict) -> dict:
    """Aplica sanitizar_valor em todos os valores de um dict."""
    return {k: sanitizar_valor(v) for k, v in dados.items()}


@st.cache_data(ttl=300)  # 5 min — rede de segurança; o cache já é invalidado após toda escrita
def carregar_ativos():
    colunas_sql = ", ".join(COLUNAS)
    return query_df(f"SELECT {colunas_sql} FROM {TABELA}")


def patrimonio_existe(patrimonio):
    df = query_df(
        f"SELECT COUNT(*) as n FROM {TABELA} WHERE patrimonio = :p",
        {"p": patrimonio},
    )
    return int(df["n"].iloc[0]) > 0


def substituir_todos(df: pd.DataFrame):
    """
    Trunca a tabela e reinsere todos os registros do DataFrame.
    Colunas de config.COLUNAS ausentes na planilha são preenchidas com NULL.
    
    Campos de data (COLUNAS_DATA) são validados e convertidos automaticamente.
    Se um valor não puder ser convertido para data, será inserido como NULL.
    """
    from config import COLUNAS_DATA
    
    execute(f"TRUNCATE TABLE {TABELA}")

    df = df.copy()
    for coluna in COLUNAS:
        if coluna not in df.columns:
            df[coluna] = None

    # Sanitizar com validação de datas
    registros = []
    for r in df[COLUNAS].to_dict("records"):
        registro_sanitizado = {}
        for c in COLUNAS:
            eh_data = c in COLUNAS_DATA
            registro_sanitizado[c] = sanitizar_valor(r.get(c), eh_data=eh_data)
        registros.append(registro_sanitizado)
    
    colunas_sql = ", ".join(COLUNAS)
    placeholders = ", ".join(f":{c}" for c in COLUNAS)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {TABELA} ({colunas_sql}) VALUES ({placeholders})",
                registros,
            )


def inserir_ativo(dados: dict):
    """
    Insere um novo ativo.
    `dados` deve ser um dict com chaves correspondentes a config.COLUNAS
    (chaves ausentes são gravadas como NULL).
    
    Campos de data (COLUNAS_DATA) são validados e convertidos automaticamente.
    Se um valor não puder ser convertido para data, será inserido como NULL.
    """
    from config import COLUNAS_DATA
    
    # Sanitizar com validação de datas
    registro = {}
    for c in COLUNAS:
        eh_data = c in COLUNAS_DATA
        registro[c] = sanitizar_valor(dados.get(c), eh_data=eh_data)
    
    colunas_sql = ", ".join(COLUNAS)
    placeholders = ", ".join(f":{c}" for c in COLUNAS)
    execute(
        f"INSERT INTO {TABELA} ({colunas_sql}) VALUES ({placeholders})",
        registro,
    )


def atualizar_ativo(patrimonio, dados: dict):
    """
    Atualiza os campos de um ativo já existente (identificado pelo patrimônio).
    `dados` deve ser um dict com chaves correspondentes a config.COLUNAS
    (exceto "patrimonio", que é usado apenas como filtro).
    
    Campos de data (COLUNAS_DATA) são validados e convertidos automaticamente.
    Se um valor não puder ser convertido para data, será inserido como NULL.
    """
    from config import COLUNAS_DATA
    
    campos = [c for c in COLUNAS if c != "patrimonio"]
    set_sql = ", ".join(f"{c} = :{c}" for c in campos)
    
    # Sanitizar com validação de datas
    params = {}
    for c in campos:
        eh_data = c in COLUNAS_DATA
        params[c] = sanitizar_valor(dados.get(c), eh_data=eh_data)
    
    params["pat"] = patrimonio
    execute(
        f"UPDATE {TABELA} SET {set_sql} WHERE patrimonio = :pat",
        params,
    )


def excluir_ativo(patrimonio):
    execute(
        f"DELETE FROM {TABELA} WHERE patrimonio = :pat",
        {"pat": patrimonio},
    )