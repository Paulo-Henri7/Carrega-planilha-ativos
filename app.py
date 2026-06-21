import streamlit as st

st.title("Meu App Databricks")
st.write("APP RODANDO 🚀")

# from services.ativos_service import (
#     carregar_ativos,
#     patrimonio_existe,
#     substituir_todos,
# )

# from services.audit_service import registrar_evento
# from utils.auth import obter_usuario
# from utils.cache import limpar_cache
# from config import COLUNAS


# st.set_page_config(page_title="Controle de Ativos", layout="wide")

# st.title("📋 Controle de Ativos")

# pagina = st.sidebar.selectbox("Menu", ["Upload", "Ativos"])


# # ======================
# # UPLOAD
# # ======================
# if pagina == "Upload":

#     arquivo = st.file_uploader("Upload Excel", type=["xlsx"])

#     if arquivo:
#         import pandas as pd

#         df = pd.read_excel(arquivo)

#         st.dataframe(df)

#         if st.button("Salvar no Databricks"):

#             if not all(c in df.columns for c in COLUNAS):
#                 st.error("Colunas inválidas")
#                 st.stop()

#             substituir_todos(df)

#             registrar_evento(
#                 obter_usuario(),
#                 "UPLOAD_PLANILHA",
#                 "N/A",
#                 {"arquivo": arquivo.name, "linhas": len(df)},
#             )

#             limpar_cache()
#             st.success("Upload realizado!")


# # ======================
# # ATIVOS
# # ======================
# elif pagina == "Ativos":

#     df = carregar_ativos()

#     st.dataframe(df)