import streamlit as st

try:
    from config import COLUNAS, COLUNAS_OBRIGATORIAS
except Exception as e:
    st.error(f"Erro ao carregar config: {e}")
    st.stop()

st.set_page_config(page_title="Controle de Ativos", layout="wide")
st.title("📋 Controle de Ativos")

from utils.auth import obter_usuario
from utils.backup_auth import tem_acesso_backup
from utils.logger import get_logger

logger = get_logger(__name__)

_usuario_atual = obter_usuario()
_is_admin = tem_acesso_backup(_usuario_atual)

_menu = ["Ativos", "Manutenção", "Novo Ativo", "Cadastro em Lote", "Edição em Lote", "Relatório", "Histórico"]
if _is_admin:
    _menu = ["Upload"] + _menu + ["Diagnóstico"]

pagina = st.sidebar.selectbox("Menu", _menu)


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

        faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
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
                logger.error(
                    "Erro ao salvar planilha no Databricks",
                    extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "UPLOAD_PLANILHA"},
                    exc_info=True,
                )
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
        col2.metric("Unidades", df["unidade"].nunique())
        col3.metric("Responsáveis", df["responsavel"].nunique())

        st.divider()

        # Busca rápida
        busca = st.text_input(
            "🔍 Busca rápida",
            placeholder="Digite patrimônio, hostname, responsável ou modelo...",
        )
        if busca:
            termo = busca.strip().lower()
            mascara = (
                df["patrimonio"].astype(str).str.lower().str.contains(termo, na=False)
                | df["hostname"].astype(str).str.lower().str.contains(termo, na=False)
                | df["responsavel"].astype(str).str.lower().str.contains(termo, na=False)
                | df["modelo"].astype(str).str.lower().str.contains(termo, na=False)
            )
            df = df[mascara]
            st.caption(f"{len(df)} resultado(s) para \"{busca}\".")
            st.dataframe(df, use_container_width=True)
            st.stop()

        st.divider()

        # Filtros avançados — OR dentro da coluna, AND entre colunas
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
        logger.error(
            "Erro ao carregar ativos",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CARREGAR_ATIVOS"},
            exc_info=True,
        )
        st.error(f"Erro ao carregar ativos: {e}")


# ======================
# MANUTENÇÃO
# ======================
elif pagina == "Manutenção":

    st.subheader("Manutenção de Ativo")

    try:
        import pandas as pd
        from services.ativos_service import carregar_ativos, atualizar_ativo, excluir_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from services.catalogo_service import tipos_disponiveis, modelos_por_tipo, tipo_do_modelo
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache
        from config import ROTULOS, COLUNAS_DATA, COLUNAS

        def _txt(valor):
            """Converte valores nulos/NaN em string vazia para exibir em text_input."""
            if valor is None or (isinstance(valor, float) and pd.isna(valor)):
                return ""
            s = str(valor)
            return "" if s.lower() == "nan" else s

        def _data(valor):
            """Converte valor do banco em date (ou None) para exibir em date_input."""
            if valor is None or (isinstance(valor, float) and pd.isna(valor)):
                return None
            try:
                d = pd.to_datetime(valor)
                return None if pd.isna(d) else d.date()
            except Exception:
                return None

        df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        patrimonio = st.selectbox(
            "Selecione o patrimônio",
            sorted(df["patrimonio"].astype(str).tolist()),
        )

        ativo = df[df["patrimonio"].astype(str) == patrimonio].iloc[0]

        # --- Seleção de quais campos editar ---
        campos_editaveis = [c for c in COLUNAS if c != "patrimonio"]
        rotulo_para_campo = {ROTULOS[c]: c for c in campos_editaveis}

        rotulos_selecionados = st.multiselect(
            "Quais campos deseja alterar?",
            [ROTULOS[c] for c in campos_editaveis],
            placeholder="Selecione um ou mais campos",
        )
        campos_selecionados = {rotulo_para_campo[r] for r in rotulos_selecionados}

        # Tipo e Modelo são dependentes (catálogo) — se um for selecionado, o outro aparece junto
        if "tipo" in campos_selecionados or "modelo" in campos_selecionados:
            campos_selecionados.add("tipo")
            campos_selecionados.add("modelo")

        # Ponto de partida: mantém os valores atuais de todos os campos
        dados_novos = {c: ativo.get(c) for c in campos_editaveis}

        if not campos_selecionados:
            st.info("Selecione ao menos um campo acima para habilitar a edição.")
        else:
            st.divider()

            for campo in campos_editaveis:  # respeita a ordem definida em config.COLUNAS
                if campo not in campos_selecionados:
                    continue

                rotulo = ROTULOS[campo]

                if campo == "tipo":
                    _tipos = tipos_disponiveis()
                    _tipo_atual = _txt(ativo.get("tipo")) or tipo_do_modelo(str(ativo["modelo"]))
                    _index_tipo = _tipos.index(_tipo_atual) if _tipo_atual in _tipos else 0
                    if not _tipo_atual:
                        st.caption(f"⚠️ Modelo atual (`{ativo['modelo']}`) não está no catálogo — selecione o tipo manualmente.")
                    dados_novos["tipo"] = st.selectbox(rotulo, _tipos, index=_index_tipo)

                elif campo == "modelo":
                    tipo_para_filtro = dados_novos.get("tipo")
                    opcoes_modelo = modelos_por_tipo(tipo_para_filtro)
                    if str(ativo["modelo"]) in opcoes_modelo:
                        _index_modelo = opcoes_modelo.index(str(ativo["modelo"]))
                    else:
                        opcoes_modelo = [str(ativo["modelo"])] + opcoes_modelo
                        _index_modelo = 0
                    dados_novos["modelo"] = st.selectbox(rotulo, opcoes_modelo, index=_index_modelo) if opcoes_modelo else None

                elif campo in COLUNAS_DATA:
                    dados_novos[campo] = st.date_input(rotulo, value=_data(ativo.get(campo)))

                else:
                    dados_novos[campo] = st.text_input(rotulo, value=_txt(ativo.get(campo)))

            campos_nao_selecionados = [c for c in campos_editaveis if c not in campos_selecionados]
            if campos_nao_selecionados:
                with st.expander(f"Ver os outros {len(campos_nao_selecionados)} campo(s) — não serão alterados"):
                    st.table({ROTULOS[c]: _txt(ativo.get(c)) for c in campos_nao_selecionados})

        if campos_selecionados and st.button("Salvar Alterações"):
            diffs = []
            for campo, novo_valor in dados_novos.items():
                if campo not in campos_selecionados:
                    continue
                antigo_valor = ativo.get(campo)
                if _txt(antigo_valor) != _txt(novo_valor):
                    diffs.append(f"{ROTULOS.get(campo, campo)}: {_txt(antigo_valor)} --> {_txt(novo_valor)}")
            detalhes = " | ".join(diffs) if diffs else "Nenhum campo alterado"

            atualizar_ativo(patrimonio, dados_novos)
            registrar_evento(obter_usuario(), "EDICAO", patrimonio, detalhes)
            backup_gerado = gerar_backup_se_necessario("EDICAO")
            limpar_cache()
            logger.info(
                "Ativo atualizado com sucesso",
                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "EDICAO", "patrimonio": patrimonio},
            )
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
            logger.info(
                "Ativo excluído com sucesso",
                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "EXCLUSAO", "patrimonio": patrimonio},
            )
            msg = "Ativo removido com sucesso!"
            if backup_gerado:
                msg += "Backup gerado automaticamente."
            st.success(msg)
            st.rerun()

    except Exception as e:
        logger.error(
            "Erro na página de Manutenção",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "MANUTENCAO"},
            exc_info=True,
        )
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
        from services.catalogo_service import tipos_disponiveis, modelos_por_tipo
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache
        from config import ROTULOS, COLUNAS_OBRIGATORIAS

        nova_data_entrega = st.date_input(ROTULOS["data_entrega"], value=None)
        novo_patrimonio = st.text_input(ROTULOS["patrimonio"])
        novo_hostname = st.text_input(ROTULOS["hostname"])
        novo_responsavel = st.text_input(ROTULOS["responsavel"])
        nova_unidade = st.text_input(ROTULOS["unidade"])
        novo_cargo = st.text_input(ROTULOS["cargo"])
        novo_gestor = st.text_input(ROTULOS["gestor"])

        tipo_equipamento = st.selectbox(ROTULOS["tipo"], tipos_disponiveis())
        opcoes_modelo = modelos_por_tipo(tipo_equipamento) if tipo_equipamento else []
        if tipo_equipamento and not opcoes_modelo:
            st.warning("Nenhum modelo cadastrado no catálogo para este tipo.")
        novo_modelo = st.selectbox(ROTULOS["modelo"], opcoes_modelo) if opcoes_modelo else None

        novo_status = st.text_input(ROTULOS["status"])
        novo_cc = st.text_input(ROTULOS["cc"])
        novo_num_pedido = st.text_input(ROTULOS["num_pedido"])
        nova_nota_fiscal = st.text_input(ROTULOS["nota_fiscal"])
        nova_dt_compra = st.date_input(ROTULOS["dt_compra"], value=None)
        nova_dt_garantia = st.date_input(ROTULOS["dt_garantia"], value=None)

        dados = {
            "data_entrega": nova_data_entrega,
            "patrimonio": novo_patrimonio,
            "hostname": novo_hostname,
            "responsavel": novo_responsavel,
            "unidade": nova_unidade,
            "cargo": novo_cargo,
            "gestor": novo_gestor,
            "tipo": tipo_equipamento,
            "modelo": novo_modelo,
            "status": novo_status,
            "cc": novo_cc,
            "num_pedido": novo_num_pedido,
            "nota_fiscal": nova_nota_fiscal,
            "dt_compra": nova_dt_compra,
            "dt_garantia": nova_dt_garantia,
        }

        if st.button("Cadastrar Ativo"):
            faltando = [ROTULOS.get(c, c) for c in COLUNAS_OBRIGATORIAS if not dados.get(c)]
            if faltando:
                st.warning(f"Preencha todos os campos obrigatórios: {', '.join(faltando)}")
            elif patrimonio_existe(novo_patrimonio):
                st.error("Já existe um ativo com este patrimônio.")
            else:
                inserir_ativo(dados)
                registrar_evento(
                    obter_usuario(),
                    "CADASTRO",
                    novo_patrimonio,
                    f"Modelo={novo_modelo}, Unidade={nova_unidade}",
                )
                gerar_backup_se_necessario("CADASTRO")
                limpar_cache()
                logger.info(
                    "Ativo cadastrado com sucesso",
                    extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CADASTRO", "patrimonio": novo_patrimonio},
                )
                st.session_state["cadastro_ok"] = True
                st.rerun()

    except Exception as e:
        logger.error(
            "Erro na página de Novo Ativo",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CADASTRO"},
            exc_info=True,
        )
        st.error(f"Erro: {e}")


# ======================
# CADASTRO EM LOTE
# ======================
elif pagina == "Cadastro em Lote":

    st.subheader("📥 Cadastro em Lote")
    st.caption(
        "Adicione várias linhas na tabela abaixo (clique no `+` no final) e cadastre todas de uma vez. "
        "Isso ADICIONA novos ativos — diferente do Upload, não substitui a base atual."
    )

    try:
        import pandas as pd
        from services.ativos_service import patrimonio_existe, inserir_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from services.catalogo_service import tipos_disponiveis, modelos_por_tipo
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache
        from config import COLUNAS, COLUNAS_OBRIGATORIAS, ROTULOS

        _tipos = tipos_disponiveis()
        _modelos_todos = sorted({m for t in _tipos for m in modelos_por_tipo(t)})

        st.caption(
            "⚠️ O Modelo aqui não é filtrado automaticamente pelo Tipo selecionado na linha — "
            "confira se a combinação Tipo + Modelo faz sentido antes de cadastrar."
        )

        col_titulo, col_reset = st.columns([5, 1])
        with col_reset:
            if st.button("🗑️ Limpar tabela"):
                if "cadastro_lote_editor" in st.session_state:
                    del st.session_state["cadastro_lote_editor"]
                st.rerun()

        df_editor = st.data_editor(
            pd.DataFrame(columns=COLUNAS),
            num_rows="dynamic",
            use_container_width=True,
            key="cadastro_lote_editor",
            column_config={
                "data_entrega": st.column_config.DateColumn(ROTULOS["data_entrega"]),
                "patrimonio": st.column_config.TextColumn(ROTULOS["patrimonio"], required=True),
                "hostname": st.column_config.TextColumn(ROTULOS["hostname"]),
                "responsavel": st.column_config.TextColumn(ROTULOS["responsavel"]),
                "unidade": st.column_config.TextColumn(ROTULOS["unidade"]),
                "cargo": st.column_config.TextColumn(ROTULOS["cargo"]),
                "gestor": st.column_config.TextColumn(ROTULOS["gestor"]),
                "tipo": st.column_config.SelectboxColumn(ROTULOS["tipo"], options=_tipos),
                "modelo": st.column_config.SelectboxColumn(ROTULOS["modelo"], options=_modelos_todos),
                "status": st.column_config.TextColumn(ROTULOS["status"]),
                "cc": st.column_config.TextColumn(ROTULOS["cc"]),
                "num_pedido": st.column_config.TextColumn(ROTULOS["num_pedido"]),
                "nota_fiscal": st.column_config.TextColumn(ROTULOS["nota_fiscal"]),
                "dt_compra": st.column_config.DateColumn(ROTULOS["dt_compra"]),
                "dt_garantia": st.column_config.DateColumn(ROTULOS["dt_garantia"]),
            },
        )

        linhas_preenchidas = df_editor.dropna(how="all")

        if linhas_preenchidas.empty:
            st.info("Adicione linhas na tabela acima (clique no `+` no final) para começar.")
        else:
            st.caption(f"{len(linhas_preenchidas)} linha(s) preenchida(s).")

            if st.button(f"Cadastrar {len(linhas_preenchidas)} ativo(s)", type="primary"):
                erros = []
                cadastrados = 0
                patrimonios_no_lote = set()

                for idx, row in linhas_preenchidas.iterrows():
                    dados = row.to_dict()
                    patrimonio = str(dados.get("patrimonio") or "").strip()

                    faltando = [ROTULOS.get(c, c) for c in COLUNAS_OBRIGATORIAS if not dados.get(c)]
                    if faltando:
                        erros.append(f"Linha {idx + 1}: campos obrigatórios ausentes ({', '.join(faltando)})")
                        continue

                    if patrimonio in patrimonios_no_lote:
                        erros.append(f"Linha {idx + 1}: patrimônio '{patrimonio}' duplicado dentro do próprio lote")
                        continue

                    if patrimonio_existe(patrimonio):
                        erros.append(f"Linha {idx + 1}: patrimônio '{patrimonio}' já existe na base")
                        continue

                    try:
                        inserir_ativo(dados)
                        registrar_evento(
                            obter_usuario(),
                            "CADASTRO_LOTE",
                            patrimonio,
                            f"Modelo={dados.get('modelo')}, Unidade={dados.get('unidade')}",
                        )
                        logger.info(
                            "Ativo cadastrado com sucesso (cadastro em lote)",
                            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CADASTRO_LOTE", "patrimonio": patrimonio},
                        )
                        patrimonios_no_lote.add(patrimonio)
                        cadastrados += 1
                    except Exception as e:
                        logger.error(
                            "Erro ao cadastrar ativo no lote",
                            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CADASTRO_LOTE", "patrimonio": patrimonio},
                            exc_info=True,
                        )
                        erros.append(f"Linha {idx + 1} ({patrimonio}): {e}")

                if cadastrados:
                    gerar_backup_se_necessario("CADASTRO")
                    limpar_cache()

                if erros:
                    st.warning(f"Concluído com {len(erros)} erro(s):")
                    for erro in erros:
                        st.text(f"• {erro}")
                if cadastrados:
                    st.success(f"✅ {cadastrados} ativo(s) cadastrado(s) com sucesso!")
                    if "cadastro_lote_editor" in st.session_state:
                        del st.session_state["cadastro_lote_editor"]
                    st.rerun()

    except Exception as e:
        logger.error(
            "Erro na página de Cadastro em Lote",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "CADASTRO_LOTE"},
            exc_info=True,
        )
        st.error(f"❌ Erro: {e}")


# ======================
# EDIÇÃO EM LOTE
# ======================
elif pagina == "Edição em Lote":

    st.subheader("✏️ Edição em Lote")
    st.caption("Selecione os patrimônios, escolha quais campos deseja poder alterar, e preencha apenas o que for necessário em cada card.")

    try:
        import pandas as pd
        from services.ativos_service import carregar_ativos, atualizar_ativo
        from services.audit_service import registrar_evento
        from services.backup_service import gerar_backup_se_necessario
        from services.catalogo_service import tipos_disponiveis, modelos_por_tipo
        from utils.auth import obter_usuario
        from utils.cache import limpar_cache
        from config import ROTULOS, COLUNAS_DATA, COLUNAS

        def _txt(valor):
            if valor is None or (isinstance(valor, float) and pd.isna(valor)):
                return ""
            s = str(valor)
            return "" if s.lower() == "nan" else s

        SENTINEL = "— não alterar —"
        campos_editaveis = [c for c in COLUNAS if c != "patrimonio"]
        rotulo_para_campo = {ROTULOS[c]: c for c in campos_editaveis}

        def _tem_valor(campo, valor):
            if campo in ("tipo", "modelo"):
                return bool(valor) and valor != SENTINEL
            if campo in COLUNAS_DATA:
                return valor is not None
            return bool(valor and str(valor).strip())

        df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        # Filtro opcional para facilitar seleção
        with st.expander("Filtrar lista por unidade ou responsável"):
            col1, col2 = st.columns(2)
            with col1:
                unidades_filtro = ["Todas"] + sorted(df["unidade"].dropna().astype(str).unique().tolist())
                filtro_unidade = st.selectbox("Unidade", unidades_filtro, key="lote_unidade")
            with col2:
                resps_filtro = ["Todos"] + sorted(df["responsavel"].dropna().astype(str).unique().tolist())
                filtro_resp = st.selectbox("Responsável", resps_filtro, key="lote_resp")

        df_filtrado = df.copy()
        if filtro_unidade != "Todas":
            df_filtrado = df_filtrado[df_filtrado["unidade"].astype(str) == filtro_unidade]
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

            rotulos_campos_lote = st.multiselect(
                "Quais campos deseja poder alterar nesta edição em lote?",
                [ROTULOS[c] for c in campos_editaveis],
                placeholder="Selecione um ou mais campos",
            )
            campos_lote = {rotulo_para_campo[r] for r in rotulos_campos_lote}

            # Tipo e Modelo são dependentes (catálogo) — se um for escolhido, o outro aparece junto
            if "tipo" in campos_lote or "modelo" in campos_lote:
                campos_lote.add("tipo")
                campos_lote.add("modelo")

            if not campos_lote:
                st.info("Selecione ao menos um campo acima para habilitar a edição em lote.")
            else:
                st.divider()
                st.markdown("**Edição individual** — preencha, em cada card, apenas os campos que deseja alterar")
                st.caption("Campos deixados em branco (ou marcados como \"não alterar\") preservam o valor atual do patrimônio.")

                # Um card por patrimônio selecionado
                novos_valores = {}
                for pat in patrimonios_selecionados:
                    ativo = df[df["patrimonio"].astype(str) == pat].iloc[0]

                    with st.container(border=True):
                        st.markdown(f"**{pat}** — modelo atual: `{ativo['modelo']}` · responsável atual: `{ativo['responsavel']}`")

                        valores_pat = {}
                        for campo in campos_editaveis:  # respeita a ordem de config.COLUNAS
                            if campo not in campos_lote:
                                continue
                            rotulo = ROTULOS[campo]

                            if campo == "tipo":
                                opcoes = [SENTINEL] + tipos_disponiveis()
                                valores_pat["tipo"] = st.selectbox(rotulo, opcoes, key=f"tipo_{pat}")
                            elif campo == "modelo":
                                tipo_escolhido = valores_pat.get("tipo")
                                if _tem_valor("tipo", tipo_escolhido):
                                    opcoes_modelo = [SENTINEL] + modelos_por_tipo(tipo_escolhido)
                                else:
                                    opcoes_modelo = [SENTINEL, str(ativo["modelo"])]
                                valores_pat["modelo"] = st.selectbox(rotulo, opcoes_modelo, key=f"modelo_{pat}")
                            elif campo in COLUNAS_DATA:
                                valores_pat[campo] = st.date_input(
                                    rotulo, value=None, key=f"{campo}_{pat}"
                                )
                            else:
                                valores_pat[campo] = st.text_input(
                                    rotulo,
                                    placeholder="Deixe em branco para não alterar",
                                    key=f"{campo}_{pat}",
                                )

                        novos_valores[pat] = valores_pat

                st.divider()

                # Verifica se ao menos um campo foi preenchido em algum card
                tem_alteracao = any(
                    any(_tem_valor(c, v) for c, v in vals.items())
                    for vals in novos_valores.values()
                )

                if not tem_alteracao:
                    st.info("Preencha ao menos um campo em algum dos cards para habilitar o salvamento.")
                else:
                    alteracoes_resumo = [
                        pat for pat, vals in novos_valores.items()
                        if any(_tem_valor(c, v) for c, v in vals.items())
                    ]
                    st.success(f"{len(alteracoes_resumo)} patrimônio(s) com alterações pendentes: {', '.join(alteracoes_resumo)}")

                    if st.button(f"Salvar alterações ({len(alteracoes_resumo)} patrimônios)", type="primary"):
                        erros = []
                        salvos = 0

                        for pat, vals in novos_valores.items():
                            # Patrimônios sem nenhum campo preenchido são ignorados
                            if not any(_tem_valor(c, v) for c, v in vals.items()):
                                continue

                            try:
                                ativo = df[df["patrimonio"].astype(str) == pat].iloc[0]
                                dados_atualizados = ativo.to_dict()
                                diffs = []

                                for campo, valor in vals.items():
                                    if not _tem_valor(campo, valor):
                                        continue
                                    valor_final = valor.strip() if isinstance(valor, str) else valor
                                    dados_atualizados[campo] = valor_final
                                    diffs.append(f"{ROTULOS[campo]}: {_txt(ativo.get(campo))} --> {_txt(valor_final)}")

                                atualizar_ativo(pat, dados_atualizados)

                                registrar_evento(
                                    obter_usuario(),
                                    "EDICAO_LOTE",
                                    pat,
                                    " | ".join(diffs),
                                )
                                logger.info(
                                    "Ativo atualizado com sucesso (edição em lote)",
                                    extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "EDICAO_LOTE", "patrimonio": pat},
                                )
                                salvos += 1

                            except Exception as e:
                                logger.error(
                                    "Erro ao atualizar patrimônio na edição em lote",
                                    extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "EDICAO_LOTE", "patrimonio": pat},
                                    exc_info=True,
                                )
                                erros.append(f"{pat}: {e}")

                        if salvos:
                            gerar_backup_se_necessario("EDICAO")
                            limpar_cache()

                        if erros:
                            st.warning(f"Concluído com erros em {len(erros)} patrimônio(s): {erros}")
                        if salvos:
                            st.success(f"✅ {salvos} patrimônio(s) atualizado(s) com sucesso!")
                        st.rerun()

    except Exception as e:
        logger.error(
            "Erro na página de Edição em Lote",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "EDICAO_LOTE"},
            exc_info=True,
        )
        st.error(f"❌ Erro: {e}")


# ======================
# RELATÓRIO
# ======================
elif pagina == "Relatório":

    st.subheader("📊 Relatório de Ativos")

    try:
        import plotly.express as px
        from services.ativos_service import carregar_ativos
        from config import COLUNAS_OBRIGATORIAS

        with st.spinner("Carregando dados..."):
            df = carregar_ativos()

        if df.empty:
            st.warning("Nenhum ativo cadastrado.")
            st.stop()

        # --- Métricas ---
        st.markdown("#### Resumo Geral")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Ativos", len(df))
        col2.metric("Unidades", df["unidade"].nunique())
        col3.metric("Responsáveis", df["responsavel"].nunique())
        col4.metric("Modelos distintos", df["modelo"].nunique())

        # Checagem de completude considera apenas os campos obrigatórios
        campos_vazios = (
            df[COLUNAS_OBRIGATORIAS].isnull().sum().sum()
            + (df[COLUNAS_OBRIGATORIAS] == "").sum().sum()
        )
        if campos_vazios > 0:
            st.warning(f"⚠️ {campos_vazios} campo(s) obrigatório(s) vazio(s) encontrado(s) na base.")
            df_incompletos = df[
                df[COLUNAS_OBRIGATORIAS].isnull().any(axis=1)
                | (df[COLUNAS_OBRIGATORIAS] == "").any(axis=1)
            ].copy()
            df_incompletos["campos_faltando"] = df_incompletos[COLUNAS_OBRIGATORIAS].apply(
                lambda row: ", ".join(
                    col for col in COLUNAS_OBRIGATORIAS
                    if row[col] is None or str(row[col]).strip() == "" or str(row[col]) == "nan"
                ),
                axis=1,
            )
            with st.expander(f"Ver {len(df_incompletos)} ativo(s) com dados obrigatórios incompletos"):
                st.dataframe(df_incompletos, use_container_width=True)
                st.caption("Acesse a página Manutenção ou Edição em Lote para corrigir esses registros.")

        st.divider()

        # --- Gráficos ---
        col_esq, col_dir = st.columns(2)

        with col_esq:
            st.markdown("#### Ativos por Unidade")
            unidade_count = (
                df["unidade"].astype(str)
                .value_counts()
                .reset_index()
                .rename(columns={"index": "unidade", "count": "total"})
            )
            fig_bar = px.bar(
                unidade_count,
                x="unidade",
                y="total",
                labels={"unidade": "Unidade", "total": "Quantidade"},
                color="unidade",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_bar.update_layout(showlegend=False, xaxis_tickangle=-30)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_dir:
            st.markdown("#### Distribuição por Unidade")
            fig_pizza = px.pie(
                unidade_count,
                names="unidade",
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
        logger.error(
            "Erro ao gerar relatório",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "RELATORIO"},
            exc_info=True,
        )
        st.error(f"❌ Erro ao gerar relatório: {e}")


# ======================
# HISTÓRICO
# ======================
elif pagina == "Histórico":

    st.subheader("Histórico")

    from utils.auth import obter_usuario
    from utils.backup_auth import tem_acesso_backup

    _usuario_historico = obter_usuario()
    _pode_ver_backup = tem_acesso_backup(_usuario_historico)

    _abas = ["Auditoria", "Backups"] if _pode_ver_backup else ["Auditoria"]
    _tabs = st.tabs(_abas)
    aba_auditoria = _tabs[0]
    aba_backups   = _tabs[1] if _pode_ver_backup else None

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

                # Filtro de data
                import pandas as pd
                df_audit["data_hora"] = pd.to_datetime(df_audit["data_hora"], utc=True)
                data_min = df_audit["data_hora"].min().date()
                data_max = df_audit["data_hora"].max().date()

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    data_inicio = st.date_input("De", value=data_min, min_value=data_min, max_value=data_max)
                with col_d2:
                    data_fim = st.date_input("Até", value=data_max, min_value=data_min, max_value=data_max)

                df_filtrado = df_audit.copy()
                if filtro_acao != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["acao"] == filtro_acao]
                if filtro_usuario != "Todos":
                    df_filtrado = df_filtrado[df_filtrado["usuario"] == filtro_usuario]

                import pandas as pd
                df_filtrado = df_filtrado[
                    (df_filtrado["data_hora"].dt.date >= data_inicio)
                    & (df_filtrado["data_hora"].dt.date <= data_fim)
                ]

                st.dataframe(df_filtrado, use_container_width=True)
                st.caption(f"{len(df_filtrado)} eventos encontrados.")

        except Exception as e:
            logger.error(
                "Erro ao carregar auditoria",
                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "HISTORICO_AUDITORIA"},
                exc_info=True,
            )
            st.error(f"Erro ao carregar auditoria: {e}")

    # ---------- ABA BACKUPS ----------
    if aba_backups:
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
                            import pandas as pd
                            from services.audit_service import registrar_evento
                            from utils.auth import obter_usuario

                            if df_preview.empty:
                                st.error("Nenhum registro encontrado neste snapshot.")
                            else:
                                execute(f"TRUNCATE TABLE {TABELA}")

                                df_restaurar = df_preview[COLUNAS].where(pd.notnull(df_preview[COLUNAS]), None)
                                registros = df_restaurar.to_dict("records")

                                colunas_sql = ", ".join(COLUNAS)
                                placeholders = ", ".join(f":{c}" for c in COLUNAS)

                                with get_connection() as conn:
                                    with conn.cursor() as cursor:
                                        cursor.executemany(
                                            f"INSERT INTO {TABELA} ({colunas_sql}) VALUES ({placeholders})",
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
                            logger.error(
                                "Erro ao restaurar backup",
                                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "RESTAURACAO_BACKUP"},
                                exc_info=True,
                            )
                            st.error(f"Erro ao restaurar: {e}")

            except Exception as e:
                logger.error(
                    "Erro ao carregar backups",
                    extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "HISTORICO_BACKUPS"},
                    exc_info=True,
                )
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
        logger.error(
            "Falha de conexão no diagnóstico",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "DIAGNOSTICO_CONEXAO"},
            exc_info=True,
        )
        st.error(f"Falha na conexão: {e}")
        st.stop()

    st.markdown("#### 2. Leitura das tabelas")
    from db.queries import query_df

    for nome, tabela in [("Ativos", TABELA), ("Auditoria", TABELA_AUDITORIA), ("Backup", TABELA_BACKUP)]:
        try:
            df = query_df(f"SELECT * FROM {tabela} LIMIT 1")
            st.success(f"{nome} (`{tabela}`): leitura OK — {len(df)} linha(s) retornada(s).")
        except Exception as e:
            logger.error(
                "Falha ao ler tabela no diagnóstico",
                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "DIAGNOSTICO_LEITURA"},
                exc_info=True,
            )
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
        logger.error(
            "Erro ao inspecionar colunas da auditoria",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "DIAGNOSTICO_COLUNAS_AUDITORIA"},
            exc_info=True,
        )
        st.error(f"Erro ao inspecionar auditoria: {e}")

    st.markdown("#### 4. Colunas da tabela de backup")
    try:
        df_bkp = query_df(f"SELECT * FROM {TABELA_BACKUP} LIMIT 0")
        st.info(f"Colunas encontradas: `{list(df_bkp.columns)}`")
        esperadas_bkp = [
            "patrimonio", "hostname", "data_entrega", "cc", "unidade", "responsavel",
            "cargo", "tipo", "modelo", "status", "num_pedido", "nota_fiscal",
            "dt_compra", "dt_garantia", "gestor", "backup_em", "modificacao_numero",
        ]
        faltando_bkp = [c for c in esperadas_bkp if c not in df_bkp.columns]
        if faltando_bkp:
            st.warning(f"⚠️ Colunas ausentes no backup: {faltando_bkp}")
        else:
            st.success("Todas as colunas esperadas estão presentes.")
    except Exception as e:
        logger.error(
            "Erro ao inspecionar colunas do backup",
            extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "DIAGNOSTICO_COLUNAS_BACKUP"},
            exc_info=True,
        )
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
            logger.error(
                "Falha no INSERT de teste da auditoria",
                extra={"usuario": _usuario_atual, "pagina": pagina, "acao": "DIAGNOSTICO_TESTE_INSERT"},
                exc_info=True,
            )
            st.error(f"Falha no INSERT da auditoria: {e}")