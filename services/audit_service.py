import json
import uuid
from db.queries import execute
from config import TABELA_AUDITORIA


def registrar_evento(usuario, acao, patrimonio, detalhes: dict | str):
    try:
        transaction_id = str(uuid.uuid4())

        if isinstance(detalhes, dict):
            detalhes = json.dumps(detalhes, ensure_ascii=False)

        execute(
            f"""
            INSERT INTO {TABELA_AUDITORIA}
            (data_hora, usuario, acao, patrimonio, detalhes, transaction_id)
            VALUES (current_timestamp(), :usuario, :acao, :patrimonio, :detalhes, :tx)
            """,
            {
                "usuario": usuario,
                "acao": acao,
                "patrimonio": patrimonio,
                "detalhes": detalhes,
                "tx": transaction_id,
            },
        )

    except Exception as e:
        # auditoria nunca quebra o fluxo principal
        print(f"Audit error: {e}")
