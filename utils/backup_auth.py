import os

# E-mails autorizados a visualizar e restaurar backups.
# Adicione ou remova entradas conforme necessário.
# Também pode ser sobrescrito pela variável de ambiente BACKUP_ADMINS
# (lista separada por vírgula, ex: "admin@empresa.com,ti@empresa.com").

_ENV_ADMINS = os.environ.get("BACKUP_ADMINS", "")

ADMINS: list[str] = (
    [e.strip().lower() for e in _ENV_ADMINS.split(",") if e.strip()]
    if _ENV_ADMINS
    else [
        # Fallback — edite aqui se não usar variável de ambiente
        # Adicionei aqui o email com permissão para realizar backup
        "mikesulivar@gmail.com",
    ]
)


def tem_acesso_backup(usuario: str) -> bool:
    """Retorna True se o usuário está na lista de autorizados."""
    return usuario.strip().lower() in ADMINS