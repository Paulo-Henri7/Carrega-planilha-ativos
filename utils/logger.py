"""
utils/logger.py — Logging estruturado com structlog

Em desenvolvimento: Logs legíveis no console
Em produção (Databricks): Logs em JSON estruturado (searchable)

Uso:
    logger = get_logger(__name__)
    logger.info("operacao_realizada", usuario="joao@empresa.com", patrimonio="PT001")
    logger.error("erro_na_operacao", usuario=usuario, exc_info=True)
"""

import os
import sys
import structlog
from contextvars import ContextVar

# Context vars para rastreamento distribuído (opcional)
_request_id: ContextVar[str] = ContextVar("request_id", default=None)
_usuario_atual: ContextVar[str] = ContextVar("usuario_atual", default=None)


def set_user_context(usuario: str):
    """Define o usuário no contexto para todos os logs seguintes."""
    _usuario_atual.set(usuario)


def set_request_id(request_id: str):
    """Define um ID de request para rastreamento distribuído."""
    _request_id.set(request_id)


def _add_context(logger, method_name, event_dict):
    """Adiciona contexto automaticamente a cada log."""
    # Adicionar variáveis de contexto se disponíveis
    usuario = _usuario_atual.get()
    if usuario:
        event_dict.setdefault("usuario", usuario)
    
    request_id = _request_id.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    
    return event_dict


def configure_logging():
    """
    Configura structlog baseado no ambiente.
    
    Desenvolvimento: Logs coloridos e legíveis no console
    Produção: JSON estruturado para parseabilidade
    """
    is_dev = os.environ.get("LOG_LEVEL", "INFO").upper() == "DEBUG"
    is_json_mode = os.environ.get("LOG_FORMAT", "").lower() == "json" or not is_dev
    
    if is_json_mode:
        # Produção: JSON estruturado
        structlog.configure(
            processors=[
                _add_context,  # Adiciona usuário/request_id
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(default=_json_serializer),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # Desenvolvimento: Legível e colorido
        structlog.configure(
            processors=[
                _add_context,  # Adiciona usuário/request_id
                structlog.processors.TimeStamper(fmt="%H:%M:%S"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )


def _json_serializer(obj):
    """Serializer customizado para objetos não-JSON — chamado por json.dumps()."""
    from datetime import datetime, date
    from decimal import Decimal
    
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "__dict__"):
        return str(obj)
    
    # Fallback para objetos desconhecidos
    try:
        return repr(obj)
    except Exception:
        return "<não-serializável>"


def get_logger(name: str):
    """Retorna um logger estruturado do structlog."""
    return structlog.get_logger(name)


# Configurar na importação
configure_logging()


# ============================================================
# Helpers para compatibilidade com código existente (opcional)
# ============================================================

class BoundLogger:
    """Wrapper simples para usar structlog como context manager."""
    
    def __init__(self, logger, context: dict = None):
        self._logger = logger
        self._context = context or {}
    
    def bind(self, **kw):
        """Vincula contexto (retorna nova instância)."""
        return BoundLogger(self._logger.bind(**kw), {**self._context, **kw})
    
    def info(self, msg: str, **kw):
        """Log INFO."""
        self._logger.info(msg, **{**self._context, **kw})
    
    def error(self, msg: str, **kw):
        """Log ERROR."""
        self._logger.error(msg, **{**self._context, **kw})
    
    def warning(self, msg: str, **kw):
        """Log WARNING."""
        self._logger.warning(msg, **{**self._context, **kw})
    
    def debug(self, msg: str, **kw):
        """Log DEBUG."""
        self._logger.debug(msg, **{**self._context, **kw})


def get_bound_logger(name: str, **context):
    """Retorna um logger com contexto pré-vinculado."""
    logger = structlog.get_logger(name)
    return BoundLogger(logger, context)