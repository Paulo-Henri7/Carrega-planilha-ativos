"""
utils/session_logs.py

Gerencia logs estruturados da sessão Streamlit com formato de linha única,
similar a logs de produção (timestamp ISO 8601 | NÍVEL | mensagem estruturada).

Exemplo:
2026-05-02T14:30:15.123Z INFO novo-ativo patrimonio='PAT-001' modelo='Dell XPS' usuario='joao@empresa.com'
2026-05-02T14:30:22.456Z WARN upload skipped_rows=3 total_imported=50 arquivo='ativos.xlsx'
2026-05-02T14:31:05.789Z ERROR exclusao_ativo patrimonio='PAT-999' erro='Patrimônio não encontrado'
"""

import streamlit as st
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional

class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERROR"

def init_logs():
    """Inicializa o session_state para logs."""
    if "app_logs" not in st.session_state:
        st.session_state.app_logs = []

def _format_log_line(level: LogLevel, service: str, data: Dict[str, Any]) -> str:
    """
    Formata um log em linha única estruturada (estilo produção).
    
    Exemplo:
    2026-05-02T14:30:15.123Z INFO | novo-ativo patrimonio=PAT-001 modelo=Dell_XPS responsavel=João
    2026-05-02T14:30:20.456Z WARN | upload arquivo=ativos.xlsx linhas=150 
    2026-05-02T14:30:25.789Z ERROR | exclusao patrimonio=PAT-999 erro=Not_found
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # Montar pares key=value (sem aspas, underscores no lugar de espaços)
    data_str = " ".join(
        f"{k}={str(v).replace(' ', '_')}"
        for k, v in data.items()
    )
    
    return f"{timestamp} {level.value} | {service} {data_str}".strip()

def add_log(
    service: str,
    level: LogLevel = LogLevel.INFO,
    **kwargs
):
    """
    Adiciona um log estruturado.
    
    Args:
        service: Nome do serviço/operação (ex: 'novo-ativo', 'upload', 'edicao')
        level: LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR
        **kwargs: Pares chave=valor que serão adicionados ao log
    
    Exemplos:
        add_log("novo-ativo", patrimonio="PAT-001", modelo="Dell XPS")
        add_log("upload", LogLevel.WARNING, skipped_rows=3, total=50)
        add_log("exclusao", LogLevel.ERROR, patrimonio="PAT-999", erro="Não encontrado")
    """
    init_logs()
    
    log_line = _format_log_line(level, service, kwargs)
    st.session_state.app_logs.append(log_line)
    
    # Manter apenas últimas 100 linhas
    if len(st.session_state.app_logs) > 100:
        st.session_state.app_logs = st.session_state.app_logs[-100:]

def display_logs(max_lines: int = 20, show_title: bool = True):
    """
    Exibe os logs em formato tabular.
    
    Args:
        max_lines: Número máximo de linhas a exibir
        show_title: Se deve mostrar o título
    """
    init_logs()
    
    if not st.session_state.app_logs:
        return
    
    if show_title:
        st.subheader("📋 Logs da Sessão")
    
    # Pegar últimas N linhas
    logs_display = st.session_state.app_logs[-max_lines:]
    
    # Exibir em caixa de texto (monospace, como logs reais)
    log_text = "\n".join(logs_display)
    st.code(log_text, language="plaintext")
    
    # Botão para limpar
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🗑️ Limpar", key="btn_clear_logs"):
            st.session_state.app_logs = []
            st.rerun()

def get_logs_df():
    """
    Retorna um DataFrame parseado dos logs para análises.
    
    Returns:
        DataFrame com colunas: timestamp, level, service, details
    """
    init_logs()
    
    import pandas as pd
    import re
    
    parsed_logs = []
    
    for log_line in st.session_state.app_logs:
        # Parsear: 2026-05-02T14:30:15.123Z INFO | service key=value key=value...
        match = re.match(
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\s+(INFO|WARN|ERROR)\s+\|\s+(\S+)\s*(.*)',
            log_line
        )
        
        if match:
            timestamp, level, service, details = match.groups()
            parsed_logs.append({
                "timestamp": timestamp,
                "level": level,
                "service": service,
                "details": details.strip() if details else ""
            })
    
    return pd.DataFrame(parsed_logs) if parsed_logs else pd.DataFrame()

def clear_logs():
    """Limpa todos os logs da sessão."""
    init_logs()
    st.session_state.app_logs = []