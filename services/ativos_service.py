import pandas as pd
import streamlit as st
from db.queries import query_df, execute
from db.connection import get_connection
from config import TABELA, COLUNAS

@st.cache_data(ttl=300)  # 5 min — rede de segurança; o cache já é invalidado após toda escrita
def carregar_ativos():
    return query_df(f"SELECT * FROM {TABELA}")

def patrimonio_existe(patrimonio):
    df = query_df(
        f"SELECT COUNT(*) as n FROM {TABELA} WHERE patrimonio = :p",
        {"p": patrimonio},
    )
    return int(df["n"].iloc[0]) > 0

def substituir_todos(df: pd.DataFrame):
    """
    Trunca a tabela e reinsere todos os registros do DataFrame.
    """
    execute(f"TRUNCATE TABLE {TABELA}")

    registros = df[COLUNAS].to_dict("records")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                f"""
                INSERT INTO {TABELA}
                (patrimonio, modelo, departamento, responsavel, serial_number)
                VALUES (:patrimonio, :modelo, :departamento, :responsavel, :serial_number)
                """,
                registros,
            )

def inserir_ativo(patrimonio, modelo, departamento, responsavel, serial_number):
    execute(
        f"""
        INSERT INTO {TABELA}
        (patrimonio, modelo, departamento, responsavel, serial_number)
        VALUES (:pat, :mod, :dep, :resp, :serial)
        """,
        {
            "pat": patrimonio,
            "mod": modelo,
            "dep": departamento,
            "resp": responsavel,
            "serial": serial_number,
        },
    )

def atualizar_ativo(patrimonio, modelo, departamento, responsavel):
    execute(
        f"""
        UPDATE {TABELA}
        SET responsavel  = :resp,
            departamento = :dep,
            modelo       = :mod
        WHERE patrimonio = :pat
        """,
        {
            "resp": responsavel,
            "dep": departamento,
            "mod": modelo,
            "pat": patrimonio,
        },
    )

def excluir_ativo(patrimonio):
    execute(
        f"DELETE FROM {TABELA} WHERE patrimonio = :pat",
        {"pat": patrimonio},
    )