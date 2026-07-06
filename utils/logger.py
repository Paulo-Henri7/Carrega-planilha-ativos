"""
utils/logger.py

Logging JSON estruturado para o projeto.
Separado do audit_service: aqui vivem logs técnicos/operacionais
(erros, performance, falhas de conexão), não eventos de negócio.

Em Databricks Apps, stdout/stderr são capturados automaticamente
pelo painel de logs — por isso o formato JSON em uma linha por evento,
fácil de filtrar e parsear depois.
"""

import json
import logging
import os
import socket
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

_HOSTNAME = socket.gethostname()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # --- campos técnicos, vêm de graça do LogRecord ---
            "modulo": record.module,
            "funcao": record.funcName,
            "linha": record.lineno,
            "processo_id": record.process,
            "thread": record.threadName,
            "hostname": _HOSTNAME,
        }

        # Campos de contexto de negócio passados via extra={...}
        for campo in ("usuario", "pagina", "acao", "patrimonio", "duracao_ms"):
            valor = getattr(record, campo, None)
            if valor is not None:
                payload[campo] = valor

        if record.exc_info:
            tipo, valor, tb = record.exc_info
            payload["exception"] = {
                "type": tipo.__name__ if tipo else None,
                "message": str(valor),
                "traceback": traceback.format_exception(tipo, valor, tb),
            }

        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado para emitir JSON no stdout.
    Nível controlável via variável de ambiente LOG_LEVEL (default INFO).
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
        logger.propagate = False

    return logger


@contextmanager
def log_duracao(logger: logging.Logger, mensagem: str, **contexto):
    """
    Context manager para medir e logar a duração de uma operação.

    Uso:
        with log_duracao(logger, "Query de ativos", usuario=usuario, acao="CARREGAR_ATIVOS"):
            df = query_df(...)
    """
    inicio = time.perf_counter()
    try:
        yield
    except Exception:
        duracao_ms = round((time.perf_counter() - inicio) * 1000, 1)
        logger.error(mensagem, extra={**contexto, "duracao_ms": duracao_ms}, exc_info=True)
        raise
    else:
        duracao_ms = round((time.perf_counter() - inicio) * 1000, 1)
        logger.info(mensagem, extra={**contexto, "duracao_ms": duracao_ms})