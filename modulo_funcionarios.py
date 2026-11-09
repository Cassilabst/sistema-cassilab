from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


@st.dialog("👥 Painel Executivo — Funcionários e Headcount", width="large")
def abrir_dashboard_funcionarios(df_func, empresa_nome):
    st.markdown(f"### 🏢 Visão Geral de Funcionários: **{empresa_nome}**")
    st.write(
        "Resumo analítico detalhado por setor e cargo (ideal para consultas rápidas)."
    )
    st.markdown("---")

    if df_func.empty:
        st.info("Nenhum dado encontrado para gerar o painel desta empresa.")
        return

    total = len(df_func)
    ativos = len(
        df_func[df_func["status"].str.contains("ativo", case=False, na=False)]
    )
    afastados = len(
        df_func[df_func["status"].str.contains("afastado", case=False, na=False)]
    )
    desligados = len(
        df_func[df_func["status"].str.contains("desligado", case=False, na=False)]
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Total de Funcionários", total)
    col2.metric("🟢 Ativos", ativos)
    col3.metric("🟠 Afastados", afastados)
    col4.metric("🔴 Desligados", desligados)

    st.markdown("---")
    st.markdown("#### 📊 Distribuição por Setor")
    if "setor" in df_func.columns:
        resumo_setor = (
            df_func.groupby("setor")
            .size()
            .reset_index(name="Total de Funcionários")
        )
        resumo_setor = resumo_setor.rename(columns={"setor": "Setor"})
        est_setor = (
            resumo_setor.style.set_properties(**{"text-align": "center"})
            .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
        )
        st.table(est_setor)

    st.markdown("---")
    st.markdown("#### 📊 Distribuição por Cargo / Função")
    if "cargo" in df_func.columns:
        resumo_cargo = (
            df_func.groupby("cargo")
            .size()
            .reset_index(name="Total de Funcionários")
        )
        resumo_cargo = resumo_cargo.rename(columns={"cargo": "Cargo / Função"})
        est_cargo = (
            resumo_cargo.style.set_properties(**{"text-align": "center"})
            .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
        )
        st.table(est_cargo)


def renderizar_dashboard_funcionarios_fullscreen(df_func, empresa_nome):
    if st.button("⬅️ Voltar para Lista e Gestão", key="btn_voltar_gestao_func"):
        st.session_state["view_mode_func"] = "gestao"
        st.rerun()

    st.markdown("---")
    st.markdown(
        f"### 🏢 Dashboard Executivo (Tela Inteira) — Funcionários: **{empresa_nome}**"
    )
    st.write(
        "Visão analítica completa e detalhada, ideal para apresentações estratégicas com o cliente."
    )
    st.markdown("---")

    if df_func.empty:
        st.info("Nenhum dado encontrado para gerar o painel desta empresa.")
        return

    total = len(df_func)
    ativos = len(
        df_func[df_func["status"].str.contains("ativo", case=False, na=False)]
    )
    afastados = len(
        df_func[df_func["status"].str.contains("afastado", case=False, na=False)]
    )
    desligados = len(
        df_func[df_func["status"].str.contains("desligado", case=False, na=False)]
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Total de Funcionários", total)
    col2.metric("🟢 Ativos", ativos)
    col3.metric("🟠 Afastados", afastados)
    col4.metric("🔴 Desligados", desligados)

    st.markdown("---")

    col_esq, col_dir = st.columns(2)

    with col_esq:
        st.markdown("#### 📊 Distribuição por Setor")
        if "setor" in df_func.columns:
            resumo_setor = (
                df_func.groupby("setor")
                .size()
                .reset_index(name="Total de Funcionários")
            )
            resumo_setor = resumo_setor.rename(columns={"setor": "Setor"})
            est_setor = (
                resumo_setor.style.set_properties(**{"text-align": "center"})
                .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
            )
            st.table(est_setor)

    with col_dir:
        st.markdown("#### 📊 Distribuição por Cargo / Função")
        if "cargo" in df_func.columns:
            resumo_cargo = (
                df_func.groupby("cargo")
                .size()
                .reset_index(name="Total de Funcionários")
            )
            resumo_cargo = resumo_cargo.rename(columns={"cargo": "Cargo / Função"})
            est_cargo = (
                resumo_cargo.style.set_properties(**{"text-align": "center"})
                .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
            )
            st.table(est_cargo)

    st.markdown("---")
    st.markdown("#### 🔍 Lista Resumida de Acompanhamento")
    colunas_mostrar = [
        c
        for c in ["matricula", "funcionario", "cargo", "setor", "status"]
        if c in df_func.columns
    ]
    st.dataframe(
        df_func[colunas_mostrar] if colunas_mostrar else df_func,
        use_container_width=True,
        hide_index=True,
    )


def renderizar_aba_funcionarios(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas,
    get_cargos_por_empresa,
    get_setores_por_empresa,
    formatar_titulo,
    formatar_cpf,
    validar_e_formatar_data_input,
    limpar_status_banco,
    atualizar_filtro_empresa,
    registrar_log,
    formatar_data_br,
    formatar_status_visual,
    formatar_colunas_tabela,
    adicionar_numeracao,
    reset_func_selection,
    dialog_editar_funcionario,
):
    st.title("👥 Gestão de Funcionários")

    if "view_mode_func" not in st.session_state:
        st.session_state["view_mode_func"] = "gestao"

    empresas_cad = get_empresas()
    if is_admin:
        empresa_global = st.session_state.get("empresa_global", "Todas")
        if empresa_global != "Todas":
            empresa_selecionada = empresa_global
        else:
            opcoes_emp = ["Todas"] + empresas_cad
            idx_sel = (
                opcoes_emp.index(empresa_global)
                if empresa_global in opcoes_emp
                else 0
            )
            empresa_selecionada = st.selectbox(
                "🏢 Selecione a Empresa", opcoes_emp, index=idx_sel, key="sel_func_admin"
            )
            if empresa_selecionada != empresa_global:
                st.session_state["empresa_global"] = empresa_selecionada
    else:
        empresa_selecionada = emp_usuario

    if isinstance(empresa_selecionada, bool):
        empresa_selecionada = "Todas"

    st.markdown(
        f"<h3 style='color: #2980b9; margin-top: -10px;'>🏢 Empresa: <b>{empresa_selecionada}</b></h3>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df = pd.read_sql("SELECT * FROM base_funcionarios", conn)
    conn.close()

    if not df.empty and "funcionario" in df.columns:
        df = df.sort_values(
            by="funcionario", key=lambda x: x.astype(str).str.lower()
        )

    if not df.empty and "empresa" in df.columns:
        if is_admin and empresa_selecionada != "Todas":
            df = df[
                df["empresa"].astype(str).str.strip().str.lower()
                == str(empresa_selecionada).strip().lower()
            ]
        elif not is_admin:
            df = df[
                df["empresa"].astype(str).str.strip().str.lower()
                == str(empresa_selecionada).strip().lower()
            ]
        df = df.drop(columns=["empresa"])

    if st.session_state["view_mode_func"] == "dashboard":
        renderizar_dashboard_funcionarios_fullscreen(
            df, empresa_selecionada if empresa_selecionada else "Geral"
        )
        return

    aba_lista, aba_novo = st.tabs(["📋 Lista e Gestão", "➕ Novo Funcionário"])

    with aba_lista:
        col_b1, col_b2 = st.columns([0.4, 0.6])
        with col_b1:
            if st.button(
                "📊 Abrir Dashboard Executivo (Tela Inteira)",
                use_container_width=True,
                type="primary",
                key="btn_dash_func_fs",
            ):
                st.session_state["view_mode_func"] = "dashboard"
                st.rerun()

        st.markdown("---")
        st.markdown("<div id='ancora_funcionarios'></div>", unsafe_allow_html=True)
        st.markdown(
            "<script>window.location.hash = 'ancora_funcionarios';</script>",
            unsafe_allow_html=True,
        )

        st.markdown("### 📋 Registos de Funcionários e Gestão")
        if df.empty:
            st.info("Nenhum registo de funcionários encontrado.")
        else:
            df_edit = df.copy()
            df_edit["_id_banco"] = (
                df_edit["id"] if "id" in df_edit.columns else df.index
            )
            if "id" in df_edit.columns:
                df_edit = df_edit.drop(columns=["id"])

            if "sel_id_func" not in st.session_state:
                st.session_state["sel_id_func"] = None

            df_edit["Selecionar"] = (
                df_edit["_id_banco"] == st.session_state["sel_id_func"]
            )
            cols_func_ord = [
                "Selecionar",
                "_id_banco",
                "matricula",
                "funcionario",
                "cargo",
                "setor",
                "cpf",
                "data_admissao",
                "data_nascimento",
                "pin_colaborador",
                "termo_adesao",
                "status",
            ]
            df_func_sel = df_edit[[c for c in cols_func_ord if c in df_edit.columns]]

            df_fmt = formatar_colunas_tabela(df_func_sel)
            df_fmt = adicionar_numeracao(df_fmt)

            edit_df = st.data_editor(
                df_fmt,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_funcionarios",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn(
                        "Selecionar", required=True, pinned=True
                    ),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn(
                        "Nº", disabled=True, pinned=True
                    ),
                    "funcionario": st.column_config.TextColumn(
                        "Funcionário", disabled=True, pinned=True
                    ),
                    # --- CAMPOS PARA A ASSINATURA ELETRÔNICA ---
                    "pin_colaborador": st.column_config.TextColumn(
                        "PIN (4 Dígitos)", 
                        help="Digite a senha numérica de 4 dígitos do colaborador",
                        max_chars=4,
                        width="small"
                    ),
                    "termo_adesao": st.column_config.CheckboxColumn(
                        "Termo Assinado?", 
                        help="Marque se o colaborador já assinou o Termo de Adesão ao EPI Eletrônico",
                        default=False
                    ),
                },
            )

            # Gestão de seleção única
            curr_f = edit_df[edit_df["Selecionar"] == True]["_id_banco"].tolist()
            new_f = [f_id for f_id in curr_f if f_id != st.session_state["sel_id_func"]]
            if new_f:
                st.session_state["sel_id_func"] = new_f[-1]
                st.rerun()
            elif not curr_f and st.session_state["sel_id_func"] is not None:
                st.session_state["sel_id_func"] = None
                st.rerun()

            sel_funcs = edit_df[edit_df["Selecionar"] == True]

            st.markdown("")
            col_btn_ed, col_btn_ex = st.columns(2)

            # BOTÃO EDITAR (Abre o Pop-up)
            if col_btn_ed.button("✏️ Editar Funcionário Selecionado", use_container_width=True):
                if pode_editar:
                    if len(sel_funcs) == 1:
                        id_para_editar = int(sel_funcs.iloc[0]["_id_banco"])
                        st.session_state["sel_id_func"] = None
                        if "editor_selecao_funcionarios" in st.session_state:
                            del st.session_state["editor_selecao_funcionarios"]
                        dialog_editar_funcionario(id_para_editar)
                    else:
                        st.warning("⚠️ Selecione um único funcionário marcando o quadradinho.")
                else:
                    st.warning("🔒 Seu perfil não possui permissão para editar.")

            # BOTÃO EXCLUIR EM CASCATA
            if col_btn_ex.button("🗑️ Excluir Funcionário Selecionado", use_container_width=True, key="btn_excluir_func_direto"):
                if not pode_excluir:
                    st.warning("🔒 Seu perfil não possui permissão para excluir.")
                else:
                    id_a_apagar = None
                    
                    if 'editor_selecao_funcionarios' in st.session_state:
                        df_editor_atual = st.session_state['editor_selecao_funcionarios']
                        if isinstance(df_editor_atual, pd.DataFrame) and "Selecionar" in df_editor_atual.columns:
                            selecionados = df_editor_atual[df_editor_atual["Selecionar"] == True]
                            if not selecionados.empty:
                                id_a_apagar = int(selecionados.iloc[0]["_id_banco"])

                    if not id_a_apagar and not sel_funcs.empty:
                        id_a_apagar = int(sel_funcs.iloc[0]["_id_banco"])

                    if id_a_apagar:
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        
                        cursor.execute("SELECT funcionario FROM base_funcionarios WHERE id = ?", (id_a_apagar,))
                        row_func = cursor.fetchone()
                        nome_colaborador = row
