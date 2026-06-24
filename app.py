import streamlit as st

try:
    from config import COLUNAS
except Exception as e:
    st.error(f"Erro ao carregar config: {e}")
    st.stop()

st.set_page_config(page_title="Controle de Ativos", layout="wide")
st.title("📋 Controle de Ativos")

pagina = st.sidebar.selectbox("Menu", ["Upload", "Ativos", "Manutenção", "Novo Ativo", "Edição em Lote", "Relatório", "Histórico", "Diagnóstico"])


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

                msg = f"Upload realizado! {len(df)} registros salvos."
                if backup_gerado:
                    msg += "Backup gerado automaticamente."
                st.success(msg)

            except Exception as e:
                st.error(f"Erro ao salvar no Databricks: {e}")


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

        # Filtros OR — cada coluna aceita múltiplos valores (OR dentro da coluna)
        # Entre colunas diferentes o filtro é AND
        st.markdown("**Filtros** — dentro de cada coluna os valores selecionados usam OR entre si")
        colunas_filtro = st.multiselect("Selecione as colunas para filtrar", df.columns.tolist())
        df_filtrado = df.copy()

        for coluna in colunas_filtro:
            opcoes = sorted(df[coluna].dropna().astype(str).unique().tolist())
            with st.sidebar:
                valores = st.multiselect(
                    f"Filtro: {coluna}",
                    opcoes,
                    key=f"filtro_{coluna}",
                )
            if valores:
                df_filtrado = df_filtrado[df_filtrado[coluna].astype(str).isin(valores)]

        colunas_visiveis = st.multiselect(
            "Colunas para exibir",
            df_filtrado.columns.tolist(),
            default=df_filtrado.columns.tolist(),
        )

        st.dataframe(df_filtrado[colunas_visiveis], use_container_width=True)
        st.caption(f"{len(df_filtrado)} ativos encontrados.")

    except Exception as e:
        st.error(f"Erro ao carregar ativos: {e}")


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
            msg = "Alterações salvas com sucesso!"
            if backup_gerado:
                msg += "Backup gerado automaticamente."
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
            msg = "Ativo removido com sucesso!"
            if backup_gerado:
                msg += "Backup gerado automaticamente."
            st.success(msg)
            st.rerun()

    except Exception as e:
        st.error(f"Erro: {e}")


# ======================
# NOVO ATIVO
# ======================
elif pagina == "Novo Ativo":

    st.subheader("Cadastro de Novo Ativo")

    if st.session_state.get("cadastro_ok"):
        st.success("Ativo cadastrado com sucesso!")
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
                st.error("Já existe um ativo com este patrimônio.")
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
        st.error(f"Erro: {e}")


# ======================
# EDIÇÃO EM LOTE
# ======================
elif pagina == "Edição em Lote":

    st.subheader("✏️ Edição em Lote")
    st.caption("Selecione os patrimônios e altere responsável e/ou departamento de uma vez.")

    try:
        from services.ativos_service import carregar_ativos, atualizar_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache

        df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        # Filtro opcional para facilitar seleção
        with st.expander("Filtrar lista por departamento ou responsável"):
            col1, col2 = st.columns(2)
            with col1:
                deps = ["Todos"] + sorted(df["departamento"].dropna().astype(str).unique().tolist())
                filtro_dep = st.selectbox("Departamento", deps, key="lote_dep")
            with col2:
                resps = ["Todos"] + sorted(df["responsavel"].dropna().astype(str).unique().tolist())
                filtro_resp = st.selectbox("Responsável", resps, key="lote_resp")

        df_filtrado = df.copy()
        if filtro_dep != "Todos":
            df_filtrado = df_filtrado[df_filtrado["departamento"].astype(str) == filtro_dep]
        if filtro_resp != "Todos":
            df_filtrado = df_filtrado[df_filtrado["responsavel"].astype(str) == filtro_resp]

        patrimonios_disponiveis = sorted(df_filtrado["patrimonio"].astype(str).tolist())
        patrimonios_selecionados = st.multiselect(
            "Selecione os patrimônios para editar",
            patrimonios_disponiveis,
        )

        if patrimonios_selecionados:
            st.dataframe(
                df[df["patrimonio"].astype(str).isin(patrimonios_selecionados)],
                use_container_width=True,
            )

            st.divider()
            st.markdown("**Novos valores** — deixe em branco para não alterar o campo")

            col1, col2 = st.columns(2)
            with col1:
                novo_responsavel = st.text_input("Novo Responsável")
            with col2:
                novo_departamento = st.text_input("Novo Departamento")

            if not novo_responsavel and not novo_departamento:
                st.info("Preencha ao menos um dos campos acima.")
            elif st.button("Aplicar em Lote", type="primary"):
                erros = []
                for pat in patrimonios_selecionados:
                    try:
                        ativo = df[df["patrimonio"].astype(str) == pat].iloc[0]
                        resp_final = novo_responsavel if novo_responsavel else str(ativo["responsavel"])
                        dep_final = novo_departamento if novo_departamento else str(ativo["departamento"])
                        mod_final = str(ativo["modelo"])

                        atualizar_ativo(pat, mod_final, dep_final, resp_final)

                        detalhes = []
                        if novo_responsavel:
                            detalhes.append(f"Responsavel: {ativo['responsavel']} --> {resp_final}")
                        if novo_departamento:
                            detalhes.append(f"Departamento: {ativo['departamento']} --> {dep_final}")

                        registrar_evento(
                            obter_usuario(),
                            "EDICAO_LOTE",
                            pat,
                            " | ".join(detalhes),
                        )
                    except Exception as e:
                        erros.append(f"{pat}: {e}")

                gerar_backup_se_necessario("EDICAO")
                limpar_cache()

                if erros:
                    st.warning(f"Concluído com erros: {erros}")
                else:
                    st.success(f"✅ {len(patrimonios_selecionados)} ativos atualizados com sucesso!")
                st.rerun()

    except Exception as e:
        st.error(f"❌ Erro: {e}")


# ======================
# RELATÓRIO
# ======================
elif pagina == "Relatório":

    st.subheader("📊 Relatório de Ativos")

    try:
        import plotly.express as px
        from services.ativos_service import carregar_ativos

        with st.spinner("Carregando dados..."):
            df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        # --- Métricas ---
        st.markdown("#### Resumo Geral")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Ativos", len(df))
        col2.metric("Departamentos", df["departamento"].nunique())
        col3.metric("Responsáveis", df["responsavel"].nunique())
        col4.metric("Modelos distintos", df["modelo"].nunique())

        campos_vazios = df[COLUNAS].isnull().sum().sum() + (df[COLUNAS] == "").sum().sum()
        if campos_vazios > 0:
            st.warning(f"⚠️ {campos_vazios} campo(s) vazio(s) encontrado(s) na base.")

        st.divider()

        # --- Gráficos ---
        col_esq, col_dir = st.columns(2)

        with col_esq:
            st.markdown("#### Ativos por Departamento")
            dep_count = (
                df["departamento"].astype(str)
                .value_counts()
                .reset_index()
                .rename(columns={"index": "departamento", "count": "total"})
            )
            fig_bar = px.bar(
                dep_count,
                x="departamento",
                y="total",
                labels={"departamento": "Departamento", "total": "Quantidade"},
                color="departamento",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_bar.update_layout(showlegend=False, xaxis_tickangle=-30)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_dir:
            st.markdown("#### Distribuição por Departamento")
            fig_pizza = px.pie(
                dep_count,
                names="departamento",
                values="total",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pizza, use_container_width=True)

        st.divider()

        # --- Top responsáveis ---
        st.markdown("#### Top 10 Responsáveis com mais ativos")
        resp_count = (
            df["responsavel"].astype(str)
            .value_counts()
            .head(10)
            .reset_index()
            .rename(columns={"index": "responsavel", "count": "total"})
        )
        fig_resp = px.bar(
            resp_count,
            x="total",
            y="responsavel",
            orientation="h",
            labels={"responsavel": "Responsável", "total": "Quantidade"},
            color="total",
            color_continuous_scale="Blues",
        )
        fig_resp.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
        st.plotly_chart(fig_resp, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Erro ao gerar relatório: {e}")


# ======================
# HISTÓRICO
# ======================
elif pagina == "Histórico":

    st.subheader("Histórico")

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
            st.error(f"Erro ao carregar auditoria: {e}")

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

                # Seleção pelo número da modificação
                opcoes_mod = sorted(df_bkp["modificacao_numero"].tolist(), reverse=True)
                mod_selecionada = st.selectbox(
                    "Selecione o número da modificação",
                    opcoes_mod,
                    format_func=lambda n: (
                        f"Modificação #{n}  —  "
                        + str(df_bkp.loc[df_bkp["modificacao_numero"] == n, "backup_em"].iloc[0])
                    ),
                )

                # Preview do snapshot selecionado
                backup_em_selecionado = df_bkp.loc[
                    df_bkp["modificacao_numero"] == mod_selecionada, "backup_em"
                ].iloc[0]

                with st.spinner("Carregando preview..."):
                    df_preview = query_df(
                        f"""
                        SELECT {', '.join(COLUNAS)}
                        FROM {TABELA_BACKUP}
                        WHERE modificacao_numero = :mod
                        """,
                        {"mod": int(mod_selecionada)},
                    )

                st.markdown(f"**Preview — Modificação #{mod_selecionada}** ({len(df_preview)} registros)")
                st.dataframe(df_preview, use_container_width=True)

                confirmar_restore = st.checkbox("Confirmo que desejo restaurar este snapshot")

                if confirmar_restore and st.button("Restaurar", type="primary"):
                    try:
                        from services.audit_service import registrar_evento
                        from utils.auth import obter_usuario

                        if df_preview.empty:
                            st.error("Nenhum registro encontrado neste snapshot.")
                        else:
                            execute(f"TRUNCATE TABLE {TABELA}")
                            registros = df_preview[COLUNAS].astype(str).to_dict("records")

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
                                f"Modificação #{mod_selecionada} de {backup_em_selecionado} restaurada ({len(df_preview)} registros)",
                            )
                            limpar_cache()
                            st.success(
                                f"Modificação #{mod_selecionada} restaurada com sucesso! "
                                f"{len(df_preview)} registros reinseridos."
                            )

                    except Exception as e:
                        st.error(f"Erro ao restaurar: {e}")

        except Exception as e:
            st.error(f"Erro ao carregar backups: {e}")


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
            st.success("Conexão estabelecida com sucesso.")
    except Exception as e:
        st.error(f"Falha na conexão: {e}")
        st.stop()

    st.markdown("#### 2. Leitura das tabelas")
    from db.queries import query_df

    for nome, tabela in [("Ativos", TABELA), ("Auditoria", TABELA_AUDITORIA), ("Backup", TABELA_BACKUP)]:
        try:
            df = query_df(f"SELECT * FROM {tabela} LIMIT 1")
            st.success(f"{nome} (`{tabela}`): leitura OK — {len(df)} linha(s) retornada(s).")
        except Exception as e:
            st.error(f"{nome} (`{tabela}`): {e}")

    st.markdown("#### 3. Colunas da tabela de auditoria")
    try:
        df_audit = query_df(f"SELECT * FROM {TABELA_AUDITORIA} LIMIT 0")
        st.info(f"Colunas encontradas: `{list(df_audit.columns)}`")
        esperadas = ["data_hora", "usuario", "acao", "patrimonio", "detalhes"]
        faltando = [c for c in esperadas if c not in df_audit.columns]
        if faltando:
            st.warning(f"⚠️ Colunas ausentes na auditoria: {faltando}")
        else:
            st.success("Todas as colunas esperadas estão presentes.")
    except Exception as e:
        st.error(f"Erro ao inspecionar auditoria: {e}")

    st.markdown("#### 4. Colunas da tabela de backup")
    try:
        df_bkp = query_df(f"SELECT * FROM {TABELA_BACKUP} LIMIT 0")
        st.info(f"Colunas encontradas: `{list(df_bkp.columns)}`")
        esperadas_bkp = ["patrimonio", "modelo", "departamento", "responsavel", "serial_number", "backup_em", "modificacao_numero"]
        faltando_bkp = [c for c in esperadas_bkp if c not in df_bkp.columns]
        if faltando_bkp:
            st.warning(f"⚠️ Colunas ausentes no backup: {faltando_bkp}")
        else:
            st.success("Todas as colunas esperadas estão presentes.")
    except Exception as e:
        st.error(f"Erro ao inspecionar backup: {e}")

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
            st.success("INSERT na auditoria executado com sucesso!")
        except Exception as e:
            st.error(f"Falha no INSERT da auditoria: {e}")
