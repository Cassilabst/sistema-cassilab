from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


@st.dialog("🩺 Painel Executivo — Exames Ocupacionais", width="large")
def abrir_dashboard_exames(df_ex, empresa_nome):
  st.markdown(f"### 🏢 Visão Geral de Saúde Ocupacional: **{empresa_nome}**")
  st.write(
      "Resumo analítico detalhado por tipo de exame (ideal para apresentação"
      " em reuniões com clientes)."
  )
  st.markdown("---")

  if df_ex.empty:
    st.info("Nenhum dado encontrado para gerar o painel desta empresa.")
    return

  total = len(df_ex)
  validos = len(
      df_ex[
          df_ex["status"].str.contains(
              "Válido|Em Dia|Ativo", case=False, na=False
          )
      ]
  )
  a_vencer = len(
      df_ex[
          df_ex["status"].str.contains(
              "A Vencer|Vencer|Próximo", case=False, na=False
          )
      ]
  )
  vencidos = len(
      df_ex[
          df_ex["status"].str.contains(
              "Vencido|Atrasado", case=False, na=False
          )
      ]
  )

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("📦 Total de Exames", total)
  col2.metric("🟢 Em Dia (Válidos)", validos)
  col3.metric("🟠 A Vencer (30 dias)", a_vencer)
  col4.metric("🔴 Vencidos", vencidos)

  st.markdown("---")
  st.markdown("#### 📊 Detalhamento por Tipo de Exame")
  if "tipo_exame" in df_ex.columns:
    df_ex_aux = df_ex.copy()
    df_ex_aux["is_vencido"] = df_ex_aux["status"].str.contains(
        "Vencido|Atrasado", case=False, na=False
    )
    resumo_grupo = (
        df_ex_aux.groupby("tipo_exame")
        .agg(
            Qtd_Funcionarios=("funcionario", "count"),
            Vencidos=("is_vencido", "sum"),
        )
        .reset_index()
    )
    resumo_grupo["Em_Dia"] = (
        resumo_grupo["Qtd_Funcionarios"] - resumo_grupo["Vencidos"]
    )
    resumo_grupo = resumo_grupo.rename(
        columns={
            "tipo_exame": "Tipo de Exame",
            "Qtd_Funcionarios": "Total de Funcionários",
            "Em_Dia": "Em Dia 🟢",
            "Vencidos": "Vencidos 🔴",
        }
    )

    resumo_estilizado = (
        resumo_grupo.style.set_properties(**{"text-align": "center"})
        .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
    )
    st.table(resumo_estilizado)
  else:
    st.dataframe(df_ex, use_container_width=True, hide_index=True)

  st.markdown("---")
  st.markdown("#### 🔍 Lista Completa Detalhada")
  colunas_mostrar = [
      c
      for c in [
          "funcionario",
          "tipo_exame",
          "ultimo_exame",
          "periodicidade",
          "proximo_exame",
          "status",
      ]
      if c in df_ex.columns
  ]
  st.dataframe(
      df_ex[colunas_mostrar] if colunas_mostrar else df_ex,
      use_container_width=True,
      hide_index=True,
  )


def renderizar_aba_exames(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas,
    calcular_proximo_exame,
    validar_e_formatar_data_input,
    limpar_status_banco,
    sincronizar_status_exames,
    atualizar_filtro_empresa,
    registrar_log,
    formatar_data_br,
    formatar_status_visual,
    formatar_colunas_tabela,
    adicionar_numeracao,
    reset_ex_selection,
    dialog_editar_exame,
):
  st.title("🩺 Gestão de Exames Ocupacionais")

  empresas_cad = get_empresas()
  if is_admin:
    empresa_global = st.session_state.get("empresa_global", "Todas")
    if empresa_global != "Todas":
      empresa_selecionada = empresa_global
    else:
      empresa_selecionada = st.selectbox(
          "🏢 Selecione a Empresa", ["Todas"] + empresas_cad, key="sel_ex_admin"
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

  aba_lista, aba_novo = st.tabs(["📋 Lista e Gestão", "➕ Novo Lançamento"])

  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  df = pd.read_sql("SELECT * FROM exames", conn)
  conn.close()

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

  with aba_lista:
    col_b1, col_b2 = st.columns([0.35, 0.65])
    with col_b1:
      if st.button(
          "📊 Abrir Dashboard Executivo",
          use_container_width=True,
          type="primary",
          key="btn_dash_ex",
      ):
        abrir_dashboard_exames(
            df, empresa_selecionada if empresa_selecionada else "Geral"
        )

    st.markdown("---")
    st.markdown("### 📋 Registos de Exames e Gestão")
    if df.empty:
      st.info("Nenhum registo de exames encontrado.")
    else:
      df_edit = df.copy()
      if "id" in df_edit.columns:
        df_edit = df_edit.drop(columns=["id"])

      if "sel_linha_ex" not in st.session_state:
        st.session_state["sel_linha_ex"] = None

      # BOTÕES MOVIDOS PARA A PARTE DE CIMA
      id_selecionado_real = None
      if (
          st.session_state["sel_linha_ex"] is not None
          and st.session_state["sel_linha_ex"] < len(df)
      ):
        id_selecionado_real = int(df.iloc[st.session_state["sel_linha_ex"]]["id"])

      col_acao1, col_acao2 = st.columns(2)

      if pode_editar:
        if col_acao1.button(
            "✏️ Editar Selecionado", use_container_width=True, key="btn_edit_ex"
        ):
          if id_selecionado_real is not None:
            dialog_editar_exame(id_selecionado_real)
          else:
            st.warning("⚠️ Selecione um registo na tabela marcando a caixa.")

      if pode_excluir:
        if col_acao2.button(
            "🗑️ Excluir Selecionado", use_container_width=True, key="btn_del_ex"
        ):
          if id_selecionado_real is not None:
            conn_exc = sqlite3.connect(DB_NAME, timeout=10.0)
            cursor_exc = conn_exc.cursor()
            cursor_exc.execute(
                "SELECT tipo_exame, funcionario FROM exames WHERE id = ?",
                (id_selecionado_real,),
            )
            reg_exc = cursor_exc.fetchone()
            cursor_exc.execute(
                "DELETE FROM exames WHERE id = ?", (id_selecionado_real,)
            )
            conn_exc.commit()
            conn_exc.close()

            st.session_state["sel_linha_ex"] = None
            if "editor_selecao_exames" in st.session_state:
              del st.session_state["editor_selecao_exames"]
            st.session_state["msg_sucesso"] = "🗑️ Registo excluído com sucesso!"
            registrar_log(
                st.session_state.get("nome_usuario", "Desconhecido"),
                empresa_selecionada,
                f"Excluiu exame ({reg_exc[0] if reg_exc else ''}) de"
                f" {reg_exc[1] if reg_exc else ''}",
            )
            st.rerun()
          else:
            st.warning("⚠️ Selecione um registo na tabela marcando a caixa.")

      st.write("")

      df_edit.insert(0, "Selecionar", False)
      if (
          st.session_state["sel_linha_ex"] is not None
          and st.session_state["sel_linha_ex"] < len(df_edit)
      ):
        df_edit.loc[st.session_state["sel_linha_ex"], "Selecionar"] = True

      df_fmt = formatar_colunas_tabela(df_edit)
      df_fmt = adicionar_numeracao(df_fmt)

      edit_df = st.data_editor(
          df_fmt,
          hide_index=True,
          num_rows="fixed",
          key="editor_selecao_exames",
          use_container_width=True,
          column_config={
              "Selecionar": st.column_config.CheckboxColumn(
                  "Selecionar", required=True, pinned=True
              ),
              "Nº": st.column_config.NumberColumn(
                  "Nº", disabled=True, pinned=True
              ),
              "funcionario": st.column_config.TextColumn(
                  "Funcionário", disabled=True, pinned=True
              ),
          },
      )

      linhas_marcadas = edit_df[edit_df["Selecionar"] == True].index.tolist()
      nova_linha_sel = linhas_marcadas[-1] if linhas_marcadas else None

      if nova_linha_sel != st.session_state["sel_linha_ex"]:
        st.session_state["sel_linha_ex"] = nova_linha_sel
        st.rerun()

  with aba_novo:
    st.markdown("### ➕ Adicionar Novo Exame Ocupacional")
    if not pode_lancar:
      st.warning("🔒 Seu perfil não possui permissão para realizar lançamentos.")
    else:
      emp_alvo_novo = (
          empresa_selecionada
          if empresa_selecionada != "Todas"
          else (empresas_cad[0] if empresas_cad else "")
      )
      with st.form("form_novo_exame"):
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_funcs = pd.read_sql(
            "SELECT funcionario, matricula, cargo, setor FROM base_funcionarios"
            " WHERE empresa = ?",
            conn,
            params=(emp_alvo_novo,),
        )
        conn.close()

        lista_f = (
            df_funcs["funcionario"].tolist() if not df_funcs.empty else []
        )

        func_escolhido = st.selectbox("Funcionário", lista_f)
        tipo_exame_sel = st.selectbox(
            "Tipo de Exame",
            [
                "Admissional",
                "Periódico",
                "Retorno ao Trabalho",
                "Mudança de Riscos",
                "Demissional",
            ],
        )
        data_ultimo = st.text_input(
            "Data do Último Exame", value=datetime.today().strftime("%d/%m/%Y")
        )
        periodicidade_sel = st.selectbox(
            "Periodicidade",
            [
                "1 mês",
                "3 meses",
                "6 meses",
                "12 meses",
                "18 meses",
                "24 meses",
            ],
            index=3,
        )

        btn_salvar_novo_ex = st.form_submit_button("Salvar Novo Exame")
        if btn_salvar_novo_ex:
          if func_escolhido:
            mat_f, cargo_f, setor_f = "", "", ""
            if not df_funcs.empty:
              m_row = df_funcs[df_funcs["funcionario"] == func_escolhido]
              if not m_row.empty:
                mat_f = m_row.iloc[0]["matricula"]
                cargo_f = m_row.iloc[0]["cargo"]
                setor_f = m_row.iloc[0]["setor"]

            prox_ex = calcular_proximo_exame(data_ultimo, periodicidade_sel)
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            conn.execute(
                """
                            INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, periodicidade, proximo_exame, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Válido')
                        """,
                (
                    emp_alvo_novo,
                    str(mat_f),
                    func_escolhido,
                    str(cargo_f),
                    str(setor_f),
                    tipo_exame_sel,
                    validar_e_formatar_data_input(data_ultimo),
                    periodicidade_sel,
                    prox_ex,
                ),
            )
            conn.commit()
            conn.close()
            sincronizar_status_exames()
            st.session_state["msg_sucesso"] = "✅ Exame cadastrado com sucesso!"
            registrar_log(
                st.session_state.get("nome_usuario", "Desconhecido"),
                emp_alvo_novo,
                f"Cadastrou exame ({tipo_exame_sel}) para {func_escolhido}",
            )
            st.rerun()
          else:
            st.error("Selecione um funcionário.")