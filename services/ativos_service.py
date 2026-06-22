import pandas as pd
from db.queries import query_df, execute
from db.connection import get_connection
from config import TABELA, COLUNAS


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
