from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


def renderizar_aba_treinamentos(*args, **kwargs):
  DB_NAME = kwargs.get("DB_NAME") or (
      args[0] if len(args) > 0 else "cassilab_gestao.db"
  )
  is_admin = (
      kwargs.get("is_admin")
      if "is_admin" in kwargs
      else (args[1] if len(args) > 1 else False)
  )
  emp_usuario = kwargs.get("emp_usuario") or (
      args[2] if len(args) > 2 else ""
  )
  pode_lancar = (
      kwargs.get("pode_lancar")
      if "pode_lancar" in kwargs
      else (args[3] if len(args) > 3 else True)
  )
  pode_editar = (
      kwargs.get("pode_editar")
      if "pode_editar" in kwargs
      else (args[4] if len(args) > 4 else True)
  )
  pode_excluir = (
      kwargs.get("pode_excluir")
      if "pode_excluir" in kwargs
      else (args[5] if len(args) > 5 else True)
  )

  get_empresas_func = kwargs.get("get_empresas_func") or (
      args[6] if len(args) > 6 else lambda: []
  )
  calcular_proximo_treinamento_func = kwargs.get(
      "calcular_proximo_treinamento_func"
  ) or (args[7] if len(args) > 7 else lambda d, v: d)
  validar_e_formatar_data_input_func = (
      kwargs.get("validar_e_formatar_data_input_func")
      or (args[8] if len(args) > 8 else lambda x: x)
  )
  limpar_status_banco_func = kwargs.get("limpar_status_banco_func") or (
      args[9] if len(args) > 9 else lambda x: x
  )
  sincronizar_status_treinamentos_func = kwargs.get(
      "sincronizar_status_treinamentos_func"
  ) or (args[10] if len(args) > 10 else lambda: None)
  atualizar_filtro_empresa_func = kwargs.get(
      "atualizar_filtro_empresa_func"
  ) or (args[11] if len(args) > 11 else lambda x: None)
  raw_registrar_log_func = kwargs.get("registrar_log_func") or (
      args[12] if len(args) > 12 else None
  )
  formatar_data_br_func = kwargs.get("formatar_data_br_func") or (
      args[13] if len(args) > 13 else lambda x: x
  )

  raw_formatar_status_visual_func = kwargs.get(
      "formatar_status_visual_func"
  ) or (args[14] if len(args) > 14 else None)
  formatar_colunas_func = kwargs.get("formatar_colunas_func") or (
      args[15] if len(args) > 15 else lambda df: df
  )
  adicionar_numeracao_func = kwargs.get("adicionar_numeracao_func") or (
      args[16] if len(args) > 16 else lambda df: df
  )
  reset_tr_selection_func = kwargs.get("reset_tr_selection_func") or (
      args[17] if len(args) > 17 else lambda: None
  )
  dialog_editar_treinamento_func = kwargs.get(
      "dialog_editar_treinamento_func"
  ) or (args[18] if len(args) > 18 else lambda x: None)
  renderizar_matriz_treinamentos_func = kwargs.get(
      "renderizar_matriz_treinamentos_func"
  ) or (args[19] if len(args) > 19 else None)

  def registrar_log_func_seguro(*l_args, **l_kwargs):
    if not callable(raw_registrar_log_func):
      return
    try:
      return raw_registrar_log_func(*l_args, **l_kwargs)
    except Exception:
      try:
        if len(l_args) >= 2:
          return raw_registrar_log_func(l_args[0], l_args[1])
      except Exception:
        pass

  def formatar_status_visual_seguro(val, tipo="trein"):
    if pd.isna(val) or not str(val).strip():
      return "🟢 em dia"
    v = str(val).strip()
    if "🟢" in v or "🔴" in v or "🟠" in v or "🟡" in v:
      return v
    if callable(raw_formatar_status_visual_func):
      try:
        return raw_formatar_status_visual_func(val, tipo)
      except Exception:
        try:
          return raw_formatar_status_visual_func(val)
        except Exception:
          pass
    v_low = v.lower()
    if "vencido" in v_low:
      return f"🔴 {v}"
    return f"🟢 {v}"

  st.title("📚 Gestão de Treinamentos")

  empresas_cad = get_empresas_func() if callable(get_empresas_func) else []
  if is_admin:
    empresa_global = st.session_state.get("empresa_global", "Todas")
    if empresa_global != "Todas":
      empresa_selecionada = empresa_global
    else:
      empresa_selecionada = st.selectbox(
          "🏢 Selecione a Empresa", ["Todas"] + empresas_cad, key="sel_tr_admin"
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

  aba_lista, aba_novo, aba_matriz = st.tabs(
      ["📋 Lista e Gestão", "➕ Novo Lançamento", "📊 Matriz de Treinamentos"]
  )

  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  try:
    df = pd.read_sql("SELECT * FROM treinamentos", conn)
  except:
    df = pd.DataFrame()
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
    # âncora invisível para manter a posição da tela após ações/rerun
    st.markdown("<div id='ancora_treinamentos'></div>", unsafe_allow_html=True)
    st.markdown(
        "<script>window.location.hash = 'ancora_treinamentos';</script>",
        unsafe_allow_html=True,
    )

    st.markdown("### 📋 Registos de Treinamentos e Gestão")
    if df.empty:
      st.info("Nenhum registo de treinamento encontrado.")
    else:
      df_edit = df.copy()
      if "id" in df_edit.columns:
        df_edit = df_edit.drop(columns=["id"])

      if "sel_linha_tr" not in st.session_state:
        st.session_state["sel_linha_tr"] = None

      id_selecionado_real = None
      if (
          st.session_state["sel_linha_tr"] is not None
          and st.session_state["sel_linha_tr"] < len(df)
      ):
        id_selecionado_real = int(df.iloc[st.session_state["sel_linha_tr"]]["id"])

      col_acao1, col_acao2 = st.columns(2)

      if pode_editar:
        if col_acao1.button(
            "✏️ Editar Selecionado", use_container_width=True, key="btn_edit_tr"
        ):
          if id_selecionado_real is not None:
            dialog_editar_treinamento_func(id_selecionado_real)
          else:
            st.warning("⚠️ Selecione um registo na tabela marcando a caixa.")

      if pode_excluir:
        if col_acao2.button(
            "🗑️ Excluir Selecionado", use_container_width=True, key="btn_del_tr"
        ):
          if id_selecionado_real is not None:
            conn_exc = sqlite3.connect(DB_NAME, timeout=10.0)
            cursor_exc = conn_exc.cursor()
            cursor_exc.execute(
                "SELECT treinamento, funcionario FROM treinamentos WHERE id = ?",
                (id_selecionado_real,),
            )
            reg_exc = cursor_exc.fetchone()
            cursor_exc.execute(
                "DELETE FROM treinamentos WHERE id = ?", (id_selecionado_real,)
            )
            conn_exc.commit()
            conn_exc.close()

            st.session_state["sel_linha_tr"] = None
            if "editor_selecao_treinamentos" in st.session_state:
              del st.session_state["editor_selecao_treinamentos"]
            st.session_state["msg_sucesso"] = "🗑️ Registo excluído com sucesso!"
            registrar_log_func_seguro(
                st.session_state.get("nome_usuario", "Desconhecido"),
                empresa_selecionada,
                f"Excluiu treinamento ({reg_exc[0] if reg_exc else ''}) de"
                f" {reg_exc[1] if reg_exc else ''}",
            )
            st.rerun()
          else:
            st.warning("⚠️ Selecione um registo na tabela marcando a caixa.")

      st.write("")

      df_edit.insert(0, "Selecionar", False)
      if (
          st.session_state["sel_linha_tr"] is not None
          and st.session_state["sel_linha_tr"] < len(df_edit)
      ):
        df_edit.loc[st.session_state["sel_linha_tr"], "Selecionar"] = True

      if "data_realizacao" in df_edit.columns:
        df_edit["data_realizacao"] = df_edit["data_realizacao"].apply(
            formatar_data_br_func
        )
      if "proximo_treinamento" in df_edit.columns:
        df_edit["proximo_treinamento"] = df_edit["proximo_treinamento"].apply(
            formatar_data_br_func
        )
      if "status" in df_edit.columns:
        df_edit["status"] = df_edit["status"].apply(
            lambda x: formatar_status_visual_seguro(x, "trein")
        )

      df_fmt = formatar_colunas_func(df_edit)
      df_fmt = adicionar_numeracao_func(df_fmt)

      edit_df = st.data_editor(
          df_fmt,
          hide_index=True,
          num_rows="fixed",
          key="editor_selecao_treinamentos",
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

      if nova_linha_sel != st.session_state["sel_linha_tr"]:
        st.session_state["sel_linha_tr"] = nova_linha_sel
        st.rerun()

  with aba_novo:
    st.markdown("### ➕ Adicionar Novo Treinamento")
    if not pode_lancar:
      st.warning("🔒 Seu perfil não possui permissão para realizar lançamentos.")
    else:
      emp_alvo_novo = (
          empresa_selecionada
          if empresa_selecionada != "Todas"
          else (empresas_cad[0] if empresas_cad else "")
      )
      with st.form("form_novo_treinamento"):
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
          df_funcs = pd.read_sql(
              "SELECT funcionario, matricula, cargo, setor FROM base_funcionarios"
              " WHERE empresa = ?",
              conn,
              params=(emp_alvo_novo,),
          )
          df_cad_tr = pd.read_sql(
              "SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY"
              " treinamento ASC",
              conn,
          )
        except:
          df_funcs = pd.DataFrame()
          df_cad_tr = pd.DataFrame()
        conn.close()

        lista_f = (
            df_funcs["funcionario"].tolist() if not df_funcs.empty else []
        )
        lista_tr = (
            df_cad_tr["treinamento"].tolist() if not df_cad_tr.empty else []
        )
        mapa_ch = (
            dict(zip(df_cad_tr["treinamento"], df_cad_tr["carga_horaria"]))
            if not df_cad_tr.empty
            else {}
        )

        func_escolhido = st.selectbox("Funcionário", lista_f)

        if lista_tr:
          trein_sel = st.selectbox("Treinamento", lista_tr)
          carga_sug = mapa_ch.get(trein_sel, "8 horas")
        else:
          trein_sel = st.text_input("Treinamento", value="Integração")
          carga_sug = "8 horas"

        carga_in = st.text_input("Carga Horária", value=str(carga_sug))
        modalidade_in = st.selectbox(
            "Tipo de Treinamento", ["Presencial", "Semi-presencial", "EaD"]
        )
        data_real = st.text_input(
            "Data da Realização", value=datetime.today().strftime("%d/%m/%Y")
        )
        validade_in = st.text_input("Validade (ex: 12 meses)", value="12 meses")

        btn_salvar_tr = st.form_submit_button("Salvar Novo Treinamento")
        if btn_salvar_tr:
          if func_escolhido and trein_sel:
            mat_f, cargo_f, setor_f = "", "", ""
            if not df_funcs.empty:
              m_row = df_funcs[df_funcs["funcionario"] == func_escolhido]
              if not m_row.empty:
                mat_f = m_row.iloc[0]["matricula"]
                cargo_f = m_row.iloc[0]["cargo"]
                setor_f = m_row.iloc[0]["setor"]

            prox_tr = calcular_proximo_treinamento_func(data_real, validade_in)
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            conn.execute(
                """
                            INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, proximo_treinamento, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'em dia')
                        """,
                (
                    emp_alvo_novo,
                    str(mat_f),
                    func_escolhido,
                    str(cargo_f),
                    str(setor_f),
                    trein_sel,
                    carga_in.strip(),
                    modalidade_in.strip(),
                    validar_e_formatar_data_input_func(data_real),
                    validade_in.strip(),
                    prox_tr,
                ),
            )
            conn.commit()
            conn.close()
            if callable(sincronizar_status_treinamentos_func):
              sincronizar_status_treinamentos_func()
            st.session_state["msg_sucesso"] = (
                "✅ Treinamento cadastrado com sucesso!"
            )
            registrar_log_func_seguro(
                st.session_state.get("nome_usuario", "Desconhecido"),
                emp_alvo_novo,
                f"Cadastrou treinamento ({trein_sel}) para {func_escolhido}",
            )
            st.rerun()
          else:
            st.error("Preencha todos os campos obrigatórios.")

  with aba_matriz:
    if callable(renderizar_matriz_treinamentos_func):
      renderizar_matriz_treinamentos_func(
          DB_NAME, empresas_cad, registrar_log_func_seguro
      )
    else:
      st.info("Matriz de treinamentos não disponível.")