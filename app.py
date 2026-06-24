import streamlit as st

try:
    from config import COLUNAS
except Exception as e:
    st.error(f"Erro ao carregar config: {e}")
    st.stop()

st.set_page_config(page_title="Controle de Ativos", layout="wide")
st.title("📋 Controle de Ativos")

pagina = st.sidebar.selectbox("Menu", ["Upload", "Ativos", "Manutenção", "Novo Ativo"])


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
