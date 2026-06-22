import streamlit as st

try:
    from config import COLUNAS
except Exception as e:
    st.error(f"Erro ao carregar config: {e}")
    st.stop()

st.set_page_config(page_title="Controle de Ativos", layout="wide")
st.title("📋 Controle de Ativos")

pagina = st.sidebar.selectbox("Menu", ["Upload", "Ativos"])


# ======================
# UPLOAD
# ======================
if pagina == "Upload":

    arquivo = st.file_uploader("Upload Excel", type=["xlsx"])

    if arquivo:
        import pandas as pd

        df = pd.read_excel(arquivo)
        st.dataframe(df)

        if st.button("Salvar no Databricks"):

            if not all(c in df.columns for c in COLUNAS):
                st.error("Colunas inválidas. Verifique se o arquivo contém: " + ", ".join(COLUNAS))
                st.stop()

            try:
                from services.ativos_service import substituir_todos
                from services.audit_service import registrar_evento
                from utils.auth import obter_usuario
                from utils.cache import limpar_cache

                with st.spinner("Salvando..."):
                    substituir_todos(df)
                    registrar_evento(
                        obter_usuario(),
                        "UPLOAD_PLANILHA",
                        "N/A",
                        {"arquivo": arquivo.name, "linhas": len(df)},
                    )
                    limpar_cache()

                st.success(f"✅ Upload realizado! {len(df)} registros salvos.")

            except Exception as e:
                st.error(f"❌ Erro ao salvar no Databricks: {e}")


# ======================
# ATIVOS
# ======================
elif pagina == "Ativos":

    try:
        from services.ativos_service import carregar_ativos

        with st.spinner("Carregando ativos..."):
            df = carregar_ativos()

        st.dataframe(df, use_container_width=True)
        st.caption(f"{len(df)} ativos encontrados.")

    except Exception as e:
        st.error(f"❌ Erro ao carregar ativos: {e}")
