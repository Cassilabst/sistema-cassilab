from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


@st.dialog("👥 Painel Executivo — Funcionários e Headcount", width="large")
def abrir_dashboard_funcionarios(df_func, empresa_nome):
  st.markdown(f"### 🏢 Visão Geral de Funcionários: **{empresa_nome}**")
  st.write(
      "Resumo analítico detalhado por setor e cargo (ideal para consultas"
      " rápidas)."
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
      f"### 🏢 Dashboard Executivo (Tela Inteira) — Funcionários:"
      f" **{empresa_nome}**"
  )
  st.write(
      "Visão analítica completa e detalhada, ideal para apresentações"
      " estratégicas com o cliente."
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
      empresa_selecionada = st.selectbox(
          "🏢 Selecione a Empresa", ["Todas"] + empresas_cad, key="sel_func_admin"
      )
  else:
    empresa_selecionada = emp_usuario

  if isinstance(empresa_selecionada, bool):
    empresa_selecionada = "Todas"

  st.markdown(
      f"<h3 style='color: #2980b9; margin-top: -10px;'>🏢 Empresa:"
      f" <b>{empresa_selecionada}</b></h3>",
      unsafe_allow_html=True,
  )
  st.markdown("---")

  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  df = pd.read_sql("SELECT * FROM base_funcionarios", conn)
  conn.close()

  # Ordenação alfabética por nome do funcionário (ignorando maiúsculas/minúsculas)
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

    # Âncora invisível para manter a posição da tela após ações/rerun
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

      id_func_sel = st.session_state["sel_id_func"]
      col_acao1, col_acao2 = st.columns(2)

      if pode_editar:
        if col_acao1.button(
            "✏️ Editar Funcionário Selecionado",
            use_container_width=True,
            key="btn_edit_func",
        ):
          if id_func_sel is not None:
            dialog_editar_funcionario(int(id_func_sel))
          else:
            st.warning("⚠️ Selecione um funcionário marcando o quadradinho.")

      if pode_excluir:
        if col_acao2.button(
            "🗑️ Excluir Funcionário Selecionado",
            use_container_width=True,
            key="btn_del_func",
        ):
          if id_func_sel is not None:
            st.session_state["modal_excluir_ativo"] = True
            st.session_state["modal_excluir_tabela"] = "base_funcionarios"
            st.session_state["modal_excluir_id"] = int(id_func_sel)
            st.session_state["modal_excluir_editor_key"] = (
                "editor_selecao_funcionarios"
            )
            st.session_state["sel_id_func"] = None
            st.rerun()
          else:
            st.warning("⚠️ Selecione um funcionário marcando o quadradinho.")

      st.write("")

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
          },
      )

      curr_func = (
          edit_df[edit_df["Selecionar"] == True]["_id_banco"].tolist()
      )
      new_func = [
          uid for uid in curr_func if uid != st.session_state["sel_id_func"]
      ]

      if new_func:
        st.session_state["sel_id_func"] = new_func[-1]
        st.rerun()
      elif not curr_func and st.session_state["sel_id_func"] is not None:
        st.session_state["sel_id_func"] = None
        st.rerun()

      if st.session_state.get("modal_edit_func_id"):
        dialog_editar_funcionario(st.session_state["modal_edit_func_id"])
        st.session_state["modal_edit_func_id"] = None

  with aba_novo:
    st.markdown("### ➕ Cadastrar Novo Funcionário")
    if not pode_lancar:
      st.warning("🔒 Seu perfil não possui permissão para realizar lançamentos.")
    else:
      emp_alvo_novo = (
          empresa_selecionada
          if empresa_selecionada != "Todas"
          else (empresas_cad[0] if empresas_cad else "")
      )
      with st.form("form_novo_funcionario"):
        mat_in = st.text_input("Matrícula")
        nome_in = st.text_input("Nome Completo")

        cargos_emp = get_cargos_por_empresa(emp_alvo_novo)
        if cargos_emp:
          cargo_in = st.selectbox("Cargo", cargos_emp)
        else:
          cargo_in = st.text_input("Cargo")

        setores_emp = get_setores_por_empresa(emp_alvo_novo)
        if setores_emp:
          setor_in = st.selectbox("Setor", setores_emp)
        else:
          setor_in = st.text_input("Setor")

        cpf_in = st.text_input("CPF")
        dt_adm = st.text_input(
            "Data de Admissão", value=datetime.today().strftime("%d/%m/%Y")
        )
        dt_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA)", value="")

        btn_salvar_f = st.form_submit_button("Salvar Novo Funcionário")
        if btn_salvar_f:
          if nome_in.strip():
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            conn.execute(
                """
                            INSERT INTO base_funcionarios (empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status, data_nascimento)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'Ativo', ?)
                        """,
                (
                    emp_alvo_novo,
                    str(mat_in).strip(),
                    formatar_titulo(nome_in),
                    formatar_titulo(cargo_in),
                    formatar_titulo(setor_in),
                    formatar_cpf(cpf_in),
                    validar_e_formatar_data_input(dt_adm),
                    validar_e_formatar_data_input(dt_nasc) if dt_nasc else "",
                ),
            )
            conn.commit()
            conn.close()
            st.session_state["msg_sucesso"] = (
                "✅ Funcionário cadastrado com sucesso!"
            )
            registrar_log(
                st.session_state.get("nome_usuario", "Desconhecido"),
                emp_alvo_novo,
                f"Cadastrou funcionário: {formatar_titulo(nome_in)}",
            )
            st.rerun()
          else:
            st.error("Preencha o funcionário.")