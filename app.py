import streamlit as st

try:
    from config import COLUNAS
except Exception as e:
    st.error(f"Erro ao carregar config: {e}")
    st.stop()

st.set_page_config(page_title="Controle de Ativos", layout="wide")
st.title("📋 Controle de Ativos")

pagina = st.sidebar.selectbox("Menu", ["Upload", "Ativos", "Manutenção", "Novo Ativo", "Histórico", "Diagnóstico"])


# ======================
# UPLOAD
# ======================
if pagina == "Upload":

    st.subheader("Upload de Planilha")
    st.caption(
        "⚠️ O upload SUBSTITUI todos os ativos atuais pela planilha enviada. "
        "A versão anterior continua recuperável pelo histórico da tabela Delta."
    )

    arquivo = st.file_uploader("Selecione uma planilha Excel", type=["xlsx"])

    if arquivo:
        import pandas as pd

        df = pd.read_excel(arquivo)
        st.subheader("Visualização dos dados")
        st.dataframe(df, use_container_width=True)

        faltando = [c for c in COLUNAS if c not in df.columns]
        if faltando:
            st.error(f"Colunas obrigatórias ausentes: {faltando}")
            st.stop()

        confirmar = st.checkbox("Confirmo que esta é a planilha correta")

        if confirmar and st.button("Salvar no Databricks"):
            try:
                from services.ativos_service import substituir_todos
                from services.audit_service import registrar_evento
                from utils.auth import obter_usuario
                from utils.cache import limpar_cache

                with st.spinner("Salvando..."):
                    from services.backup_service import gerar_backup_se_necessario

                    substituir_todos(df)
                    registrar_evento(
                        obter_usuario(),
                        "UPLOAD_PLANILHA",
                        "N/A",
                        {"arquivo": arquivo.name, "linhas": len(df)},
                    )
                    backup_gerado = gerar_backup_se_necessario("UPLOAD_PLANILHA")
                    limpar_cache()

                msg = f"✅ Upload realizado! {len(df)} registros salvos."
                if backup_gerado:
                    msg += " 💾 Backup gerado automaticamente."
                st.success(msg)

            except Exception as e:
                st.error(f"❌ Erro ao salvar no Databricks: {e}")


# ======================
# ATIVOS
# ======================
elif pagina == "Ativos":

    st.subheader("Consulta de Ativos")

    try:
        from services.ativos_service import carregar_ativos

        with st.spinner("Carregando ativos..."):
            df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Ativos", len(df))
        col2.metric("Departamentos", df["departamento"].nunique())
        col3.metric("Responsáveis", df["responsavel"].nunique())

        st.divider()

        # Filtros dinâmicos
        colunas_filtro = st.multiselect("Filtrar por coluna", df.columns.tolist())
        df_filtrado = df.copy()

        for coluna in colunas_filtro:
            opcoes = ["Todos"] + sorted(df[coluna].dropna().astype(str).unique().tolist())
            with st.sidebar:
                valor = st.selectbox(f"Filtro: {coluna}", opcoes, key=f"filtro_{coluna}")
            if valor != "Todos":
                df_filtrado = df_filtrado[df_filtrado[coluna].astype(str) == valor]

        colunas_visiveis = st.multiselect(
            "Colunas para exibir",
            df_filtrado.columns.tolist(),
            default=df_filtrado.columns.tolist(),
        )

        st.dataframe(df_filtrado[colunas_visiveis], use_container_width=True)
        st.caption(f"{len(df_filtrado)} ativos encontrados.")

    except Exception as e:
        st.error(f"❌ Erro ao carregar ativos: {e}")


# ======================
# MANUTENÇÃO
# ======================
elif pagina == "Manutenção":

    st.subheader("Manutenção de Ativo")

    try:
        from services.ativos_service import carregar_ativos, atualizar_ativo, excluir_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache

        df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        patrimonio = st.selectbox(
            "Selecione o patrimônio",
            sorted(df["patrimonio"].astype(str).tolist()),
        )

        ativo = df[df["patrimonio"].astype(str) == patrimonio].iloc[0]

        novo_modelo = st.text_input("Modelo", value=str(ativo["modelo"]))
        novo_departamento = st.text_input("Departamento", value=str(ativo["departamento"]))
        novo_responsavel = st.text_input("Responsável", value=str(ativo["responsavel"]))

        if st.button("Salvar Alterações"):
            detalhes = (
                f"Responsavel: {ativo['responsavel']} --> {novo_responsavel} | "
                f"Departamento: {ativo['departamento']} --> {novo_departamento} | "
                f"Modelo: {ativo['modelo']} --> {novo_modelo}"
            )
            atualizar_ativo(patrimonio, novo_modelo, novo_departamento, novo_responsavel)
            registrar_evento(obter_usuario(), "EDICAO", patrimonio, detalhes)
            backup_gerado = gerar_backup_se_necessario("EDICAO")
            limpar_cache()
            msg = "✅ Alterações salvas com sucesso!"
            if backup_gerado:
                msg += " 💾 Backup gerado automaticamente."
            st.success(msg)
            st.rerun()

        st.divider()

        confirmar_exclusao = st.checkbox("Confirmo a exclusão deste ativo")
        if confirmar_exclusao and st.button("Excluir Ativo", type="primary"):
            excluir_ativo(patrimonio)
            registrar_evento(
                obter_usuario(),
                "EXCLUSAO",
                patrimonio,
                f"Modelo={ativo['modelo']}, Responsavel={ativo['responsavel']}",
            )
            backup_gerado = gerar_backup_se_necessario("EXCLUSAO")
            limpar_cache()
            msg = "✅ Ativo removido com sucesso!"
            if backup_gerado:
                msg += " 💾 Backup gerado automaticamente."
            st.success(msg)
            st.rerun()

    except Exception as e:
        st.error(f"❌ Erro: {e}")


# ======================
# NOVO ATIVO
# ======================
elif pagina == "Novo Ativo":

    st.subheader("Cadastro de Novo Ativo")

    if st.session_state.get("cadastro_ok"):
        st.success("✅ Ativo cadastrado com sucesso!")
        del st.session_state["cadastro_ok"]

    try:
        from services.ativos_service import patrimonio_existe, inserir_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache

        novo_patrimonio = st.text_input("Patrimônio")
        novo_modelo = st.text_input("Modelo")
        novo_departamento = st.text_input("Departamento")
        novo_responsavel = st.text_input("Responsável")
        novo_serial = st.text_input("Serial Number")

        if st.button("Cadastrar Ativo"):
            if not all([novo_patrimonio, novo_modelo, novo_departamento, novo_responsavel]):
                st.warning("Preencha todos os campos obrigatórios.")
            elif patrimonio_existe(novo_patrimonio):
                st.error("❌ Já existe um ativo com este patrimônio.")
            else:
                inserir_ativo(novo_patrimonio, novo_modelo, novo_departamento, novo_responsavel, novo_serial)
                registrar_evento(
                    obter_usuario(),
                    "CADASTRO",
                    novo_patrimonio,
                    f"Modelo={novo_modelo}, Departamento={novo_departamento}",
                )
                gerar_backup_se_necessario("CADASTRO")
                limpar_cache()
                st.session_state["cadastro_ok"] = True
                st.rerun()

    except Exception as e:
        st.error(f"❌ Erro: {e}")


# ======================
# HISTÓRICO
# ======================
elif pagina == "Histórico":

    st.subheader("📜 Histórico")

    aba_auditoria, aba_backups = st.tabs(["Auditoria", "Backups"])

    # ---------- ABA AUDITORIA ----------
    with aba_auditoria:

        st.markdown("#### Registro de Eventos")

        try:
            from db.queries import query_df
            from config import TABELA_AUDITORIA

            with st.spinner("Carregando auditoria..."):
                df_audit = query_df(
                    f"SELECT * FROM {TABELA_AUDITORIA} ORDER BY data_hora DESC"
                )

            if df_audit.empty:
                st.info("Nenhum evento registrado ainda.")
            else:
                # Filtros
                col1, col2 = st.columns(2)
                with col1:
                    acoes = ["Todas"] + sorted(df_audit["acao"].dropna().unique().tolist())
                    filtro_acao = st.selectbox("Filtrar por ação", acoes)
                with col2:
                    usuarios = ["Todos"] + sorted(df_audit["usuario"].dropna().unique().tolist())
                    filtro_usuario = st.selectbox("Filtrar por usuário", usuarios)

                df_filtrado = df_audit.copy()
                if filtro_acao != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["acao"] == filtro_acao]
                if filtro_usuario != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["usuario"] == filtro_usuario]

                st.dataframe(df_filtrado, use_container_width=True)
                st.caption(f"{len(df_filtrado)} eventos encontrados.")

        except Exception as e:
            st.error(f"❌ Erro ao carregar auditoria: {e}")

    # ---------- ABA BACKUPS ----------
    with aba_backups:

        st.markdown("#### Snapshots Disponíveis")

        try:
            from db.queries import query_df, execute
            from db.connection import get_connection
            from config import TABELA_BACKUP, TABELA, COLUNAS
            from utils.cache import limpar_cache

            with st.spinner("Carregando backups..."):
                df_bkp = query_df(
                    f"""
                    SELECT DISTINCT backup_em, modificacao_numero
                    FROM {TABELA_BACKUP}
                    ORDER BY backup_em DESC
                    """
                )

            if df_bkp.empty:
                st.info("Nenhum backup gerado ainda. Os backups são criados automaticamente a cada 10 modificações.")
            else:
                st.dataframe(df_bkp, use_container_width=True)
                st.caption(f"{len(df_bkp)} snapshot(s) disponível(is).")

                st.divider()
                st.markdown("#### Restaurar Snapshot")
                st.warning(
                    "⚠️ A restauração SUBSTITUI todos os ativos atuais pelo snapshot selecionado. "
                    "O estado atual será perdido (mas continuará recuperável pelo histórico Delta)."
                )

                opcoes_snapshot = df_bkp["backup_em"].astype(str).tolist()
                snapshot_selecionado = st.selectbox("Selecione o snapshot", opcoes_snapshot)

                confirmar_restore = st.checkbox("Confirmo que desejo restaurar este snapshot")

                if confirmar_restore and st.button("Restaurar", type="primary"):
                    try:
                        from services.audit_service import registrar_evento
                        from utils.auth import obter_usuario

                        # Busca os registros do snapshot
                        df_restore = query_df(
                            f"""
                            SELECT {', '.join(COLUNAS)}
                            FROM {TABELA_BACKUP}
                            WHERE CAST(backup_em AS STRING) = :snap
                            """,
                            {"snap": snapshot_selecionado},
                        )

                        if df_restore.empty:
                            st.error("Nenhum registro encontrado neste snapshot.")
                        else:
                            # Trunca e reinseere
                            execute(f"TRUNCATE TABLE {TABELA}")
                            registros = df_restore[COLUNAS].astype(str).to_dict("records")

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

                            registrar_evento(
                                obter_usuario(),
                                "RESTAURACAO_BACKUP",
                                "N/A",
                                f"Snapshot restaurado: {snapshot_selecionado} ({len(df_restore)} registros)",
                            )
                            limpar_cache()
                            st.success(f"✅ Snapshot de {snapshot_selecionado} restaurado com sucesso! {len(df_restore)} registros reinseridos.")

                    except Exception as e:
                        st.error(f"❌ Erro ao restaurar: {e}")

        except Exception as e:
            st.error(f"❌ Erro ao carregar backups: {e}")


# ======================
# DIAGNÓSTICO
# ======================
elif pagina == "Diagnóstico":

    st.subheader("🔍 Diagnóstico de Conexão e Tabelas")
    st.caption("Use esta página para identificar problemas de conexão ou estrutura das tabelas.")

    from config import TABELA, TABELA_AUDITORIA, TABELA_BACKUP

    st.markdown("#### 1. Conexão com Databricks")
    try:
        from db.connection import get_connection
        with get_connection() as conn:
            st.success("✅ Conexão estabelecida com sucesso.")
    except Exception as e:
        st.error(f"❌ Falha na conexão: {e}")
        st.stop()

    st.markdown("#### 2. Leitura das tabelas")
    from db.queries import query_df

    for nome, tabela in [("Ativos", TABELA), ("Auditoria", TABELA_AUDITORIA), ("Backup", TABELA_BACKUP)]:
        try:
            df = query_df(f"SELECT * FROM {tabela} LIMIT 1")
            st.success(f"✅ {nome} (`{tabela}`): leitura OK — {len(df)} linha(s) retornada(s).")
        except Exception as e:
            st.error(f"❌ {nome} (`{tabela}`): {e}")

    st.markdown("#### 3. Colunas da tabela de auditoria")
    try:
        df_audit = query_df(f"SELECT * FROM {TABELA_AUDITORIA} LIMIT 0")
        st.info(f"Colunas encontradas: `{list(df_audit.columns)}`")
        esperadas = ["data_hora", "usuario", "acao", "patrimonio", "detalhes"]
        faltando = [c for c in esperadas if c not in df_audit.columns]
        if faltando:
            st.warning(f"⚠️ Colunas ausentes na auditoria: {faltando}")
        else:
            st.success("✅ Todas as colunas esperadas estão presentes.")
    except Exception as e:
        st.error(f"❌ Erro ao inspecionar auditoria: {e}")

    st.markdown("#### 4. Colunas da tabela de backup")
    try:
        df_bkp = query_df(f"SELECT * FROM {TABELA_BACKUP} LIMIT 0")
        st.info(f"Colunas encontradas: `{list(df_bkp.columns)}`")
        esperadas_bkp = ["patrimonio", "modelo", "departamento", "responsavel", "serial_number", "backup_em", "modificacao_numero"]
        faltando_bkp = [c for c in esperadas_bkp if c not in df_bkp.columns]
        if faltando_bkp:
            st.warning(f"⚠️ Colunas ausentes no backup: {faltando_bkp}")
        else:
            st.success("✅ Todas as colunas esperadas estão presentes.")
    except Exception as e:
        st.error(f"❌ Erro ao inspecionar backup: {e}")

    st.markdown("#### 5. Teste de escrita na auditoria")
    if st.button("Executar INSERT de teste na auditoria"):
        try:
            from db.queries import execute
            execute(
                f"""
                INSERT INTO {TABELA_AUDITORIA}
                (data_hora, usuario, acao, patrimonio, detalhes)
                VALUES (current_timestamp(), :usuario, :acao, :patrimonio, :detalhes)
                """,
                {
                    "usuario": "diagnostico",
                    "acao": "TESTE",
                    "patrimonio": "N/A",
                    "detalhes": "Teste de escrita via página de diagnóstico",
                },
            )
            st.success("✅ INSERT na auditoria executado com sucesso!")
        except Exception as e:
            st.error(f"❌ Falha no INSERT da auditoria: {e}")
