from db.queries import query_df, execute
from config import TABELA, TABELA_AUDITORIA, TABELA_BACKUP, MODIFICACOES_POR_BACKUP, COLUNAS


# Ações que contam como modificação
_ACOES_MODIFICACAO = {"CADASTRO", "EDICAO", "EXCLUSAO", "UPLOAD_PLANILHA"}


def _contar_modificacoes() -> int:
    """Retorna o total de modificações registradas na auditoria."""
    df = query_df(
        f"""
        SELECT COUNT(*) AS n FROM {TABELA_AUDITORIA}
        WHERE acao IN ('CADASTRO', 'EDICAO', 'EXCLUSAO', 'UPLOAD_PLANILHA')
        """
    )
    return int(df["n"].iloc[0])


def _backup_necessario() -> bool:
    """
    Verifica se o número atual de modificações é múltiplo de
    MODIFICACOES_POR_BACKUP, indicando que é hora de gerar um backup.
    """
    total = _contar_modificacoes()
    return total > 0 and total % MODIFICACOES_POR_BACKUP == 0


def gerar_backup_se_necessario(acao: str) -> bool:
    """
    Chamado após cada operação de escrita.
    Gera um snapshot dos ativos na tabela de backup se o limite foi atingido.
    Retorna True se o backup foi gerado, False caso contrário.
    """
    if acao not in _ACOES_MODIFICACAO:
        return False

    if not _backup_necessario():
        return False

    colunas_sql = ", ".join(COLUNAS)
    execute(
        f"""
        INSERT INTO {TABELA_BACKUP}
        SELECT
            {colunas_sql},
            current_timestamp() AS backup_em,
            {_contar_modificacoes()} AS modificacao_numero
        FROM {TABELA}
        """
    )
    return True