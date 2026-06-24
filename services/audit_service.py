import json
from db.queries import execute
from config import TABELA_AUDITORIA


def registrar_evento(usuario, acao, patrimonio, detalhes: dict | str):
    if isinstance(detalhes, dict):
        detalhes = json.dumps(detalhes, ensure_ascii=False)

    execute(
        f"""
        INSERT INTO {TABELA_AUDITORIA}
        (data_hora, usuario, acao, patrimonio, detalhes)
        VALUES (current_timestamp(), :usuario, :acao, :patrimonio, :detalhes)
        """,
        {
            "usuario": usuario,
            "acao": acao,
            "patrimonio": patrimonio,
            "detalhes": detalhes,
        },
    )
