"""
audit_service.py

Serviço de auditoria — registra eventos estruturados de alteração de ativos.

Schema da tabela ativos_auditoria (Opção 2 — campos estruturados):
  - data_hora: TIMESTAMP (auto)
  - usuario: STRING
  - acao: STRING (CADASTRO, EDICAO, EXCLUSAO, CADASTRO_LOTE, UPLOAD_PLANILHA, RESTORE_BACKUP)
  - patrimonio: STRING (pode ser NULL para ações em lote)
  - detalhes: STRING (dados extras em JSON, opcional — mantido para compatibilidade)
  - campo_alterado: STRING (qual campo mudou: "modelo", "responsavel", etc)
  - valor_anterior: STRING (antes da alteração)
  - valor_novo: STRING (depois da alteração)
  - quantidade: INT (para operações em lote)
  - motivo: STRING (observações opcionais)
"""

from db.queries import execute
from config import TABELA_AUDITORIA


def registrar_evento(
    usuario: str,
    acao: str,
    patrimonio: str = None,
    campo_alterado: str = None,
    valor_anterior: str = None,
    valor_novo: str = None,
    quantidade: int = None,
    motivo: str = None,
    detalhes: str = None,  # compatibilidade com código antigo
):
    """
    Registra um evento de auditoria na tabela ativos_auditoria.

    Args:
        usuario: Email do usuário que fez a ação
        acao: Tipo de ação (CADASTRO, EDICAO, EXCLUSAO, CADASTRO_LOTE, UPLOAD_PLANILHA, etc)
        patrimonio: Patrimônio do ativo afetado (NULL para operações em lote)
        campo_alterado: Nome do campo que foi alterado (e.g., "modelo", "responsavel")
        valor_anterior: Valor antes da alteração
        valor_novo: Valor depois da alteração
        quantidade: Número de ativos afetados (para CADASTRO_LOTE, UPLOAD_PLANILHA)
        motivo: Observações/justificativa da ação
        detalhes: (LEGADO) String de detalhes extra — preferir usar campo_alterado+valores
    """

    # Sanitizar strings vazias para None
    campo_alterado = campo_alterado.strip() if campo_alterado and isinstance(campo_alterado, str) else None
    valor_anterior = str(valor_anterior).strip() if valor_anterior and valor_anterior is not None else None
    valor_novo = str(valor_novo).strip() if valor_novo and valor_novo is not None else None
    motivo = motivo.strip() if motivo and isinstance(motivo, str) else None
    patrimonio = patrimonio.strip() if patrimonio and isinstance(patrimonio, str) else None

    execute(
        f"""
        INSERT INTO {TABELA_AUDITORIA}
        (data_hora, usuario, acao, patrimonio, campo_alterado, valor_anterior, valor_novo, quantidade, motivo, detalhes)
        VALUES (current_timestamp(), :usuario, :acao, :patrimonio, :campo_alterado, :valor_anterior, :valor_novo, :quantidade, :motivo, :detalhes)
        """,
        {
            "usuario": usuario,
            "acao": acao,
            "patrimonio": patrimonio,
            "campo_alterado": campo_alterado,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
            "quantidade": quantidade,
            "motivo": motivo,
            "detalhes": detalhes,
        },
    )