from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


def renderizar_aba_servicos(*args, **kwargs):
  DB_NAME = kwargs.get("DB_NAME") or (
      args[0] if len(args) > 0 else "cassilab_gestao.db"
  )
  is_admin = (
      kwargs.get("is_admin")
      if "is_admin" in kwargs
      else (args[1] if len(args) > 1 else False)
  )

  get_empresas_func = kwargs.get("get_empresas_func") or (
      args[2] if len(args) > 2 else lambda: []
  )
  validar_e_formatar_data_input_func = (
      kwargs.get("validar_e_formatar_data_input_func")
      or (args[3] if len(args) > 3 else lambda x: x)
  )
  formatar_titulo_func = kwargs.get("formatar_titulo_func") or (
      args[4] if len(args) > 4 else lambda x: x
  )
  formatar_valor_brasileiro_func = kwargs.get(
      "formatar_valor_brasileiro_func"
  ) or (args[5] if len(args) > 5 else lambda x: str(x))
  limpar_status_banco_func = kwargs.get("limpar_status_banco_func") or (
      args[6] if len(args) > 6 else lambda x: x
  )
  atualizar_filtro_empresa_func = kwargs.get(
      "atualizar_filtro_empresa_func"
  ) or (args[7] if len(args) > 7 else lambda x: None)
  raw_registrar_log_func = kwargs.get("registrar_log_func") or (
      args[8] if len(args) > 8 else None
  )

  raw_formatar_status_visual_func = kwargs.get(
      "formatar_status_visual_func"
  ) or (args[9] if len(args) > 9 else None)
  adicionar_numeracao_func = kwargs.get("adicionar_numeracao_func") or (
      args[10] if len(args) > 10 else lambda df: df
  )
  reset_serv_selection_func = (
      kwargs.get("reset_serv_selection_func")
      or kwargs.get("reset_servico_selection_func")
      or (args[11] if len(args) > 11 else lambda: None)
  )
  dialog_editar_servico_func = kwargs.get("dialog_editar_servico_func") or (
      args[12] if len(args) > 12 else lambda x: None
  )

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

  def formatar_status_visual_seguro(val, tipo="serv"):
    if pd.isna(val) or not str(val).strip():
      return "🟢 Concluído"
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
    if "andamento" in v_low:
      return f"🟠 {v}"
    if "agendado" in v_low:
      return f"🟡 {v}"
    if "cancelado" in v_low:
      return f"🔴 {v}"
    return f"🟢 {v}"

  def safe_reset_serv(*s_args, **s_kwargs):
    if callable(reset_serv_selection_func):
      try:
        reset_serv_selection_func()
      except Exception:
        pass

  col_h1, col_h2 = st.columns([0.8, 0.2])
  with col_h1:
    st.title("🛠️ Serviços Realizados (Controle Interno)")
  with col_h2:
    st.write("")
    if st.button("🔄 Atualizar Aba", key="btn_atualizar_serv"):
      st.rerun()

  if not is_admin:
    st.warning("🔒 Área restrita ao Administrador.")
    return

  empresas = get_empresas_func() if callable(get_empresas_func) else []

  with st.expander("➕ Adicionar Novo Serviço Realizado", expanded=False):
    empresa_sel = st.selectbox(
        "Selecione a Empresa Cliente",
        empresas if empresas else ["Nenhuma"],
        key="serv_emp_form",
    )

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
      df_cad_serv = pd.read_sql(
          "SELECT servico FROM cad_servicos ORDER BY servico ASC", conn
      )
    except:
      df_cad_serv = pd.DataFrame()
    conn.close()

    lista_servicos = (
        df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []
    )

    with st.form("form_servico_realizado"):
      c1, c2 = st.columns(2)
      data_real = c1.text_input(
          "Data da Realização", value=datetime.today().strftime("%d/%m/%Y")
      )

      if lista_servicos:
        servico_sel = c2.selectbox("Serviço Executado", lista_servicos)
      else:
        servico_sel = c2.text_input("Serviço Executado")

      valor_serv = c1.number_input(
          "Valor do Serviço (R$)", min_value=0.0, value=0.0, step=50.0, format="%.2f"
      )
      resp_serv = c2.text_input("Responsável Técnico", value="Cassilab SST")

      status_serv = c1.selectbox(
          "Status",
          ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"],
      )
      nfes_serv = c2.text_input("NFES / Nº da Nota (Opcional)")
      obs_serv = st.text_area("Observações", height=70)

      if st.form_submit_button("Salvar Serviço Realizado"):
        if empresa_sel != "Nenhuma" and str(servico_sel).strip():
          conn = sqlite3.connect(DB_NAME, timeout=10.0)
          serv_fmt = (
              formatar_titulo_func(servico_sel)
              if callable(formatar_titulo_func)
              else servico_sel
          )
          resp_fmt = (
              formatar_titulo_func(resp_serv)
              if callable(formatar_titulo_func)
              else resp_serv
          )
          data_fmt = (
              validar_e_formatar_data_input_func(data_real)
              if callable(validar_e_formatar_data_input_func)
              else data_real
          )

          conn.execute(
              """
                        INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
              (
                  empresa_sel,
                  serv_fmt,
                  data_fmt,
                  resp_fmt,
                  obs_serv,
                  float(valor_serv),
                  limpar_status_banco_func(status_serv)
                  if callable(limpar_status_banco_func)
                  else status_serv,
                  str(nfes_serv).strip(),
              ),
          )
          conn.commit()
          conn.close()

          if "editor_selecao_servicos" in st.session_state:
            del st.session_state["editor_selecao_servicos"]
          st.session_state["sel_id_serv"] = None

          if callable(atualizar_filtro_empresa_func):
            atualizar_filtro_empresa_func(empresa_sel)

          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log_func_seguro(
              st.session_state.get("nome_usuario", "Administrador"),
              empresa_sel,
              f"Registrou serviço ({serv_fmt})",
          )
          st.rerun()
        else:
          st.error("Selecione a empresa e o serviço.")

  st.markdown("---")
  
  # âncora invisível para manter a posição da tela após ações/rerun
  st.markdown("<div id='ancora_servicos'></div>", unsafe_allow_html=True)
  st.markdown(
      "<script>window.location.hash = 'ancora_servicos';</script>",
      unsafe_allow_html=True,
  )

  st.subheader("Serviços Registrados")
  filtro_serv = st.selectbox(
      "Filtrar por Empresa",
      ["Todas as Empresas"] + empresas,
      key="filtro_srv_emp_trad",
      on_change=safe_reset_serv,
  )

  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  try:
    df_srv = pd.read_sql(
        "SELECT * FROM servicos_realizados ORDER BY data_realizacao DESC", conn
    )
  except:
    df_srv = pd.DataFrame()
  conn.close()

  if filtro_serv != "Todas as Empresas" and not df_srv.empty:
    df_srv = df_srv[
        df_srv["empresa"].astype(str).str.strip().str.lower()
        == str(filtro_serv).strip().lower()
    ]

  if not df_srv.empty:
    df_srv["_id_banco"] = df_srv["id"]

    if "sel_id_serv" not in st.session_state:
      st.session_state["sel_id_serv"] = None

    id_serv_sel = st.session_state["sel_id_serv"]
    col_srv_b1, col_srv_b2 = st.columns(2)

    if col_srv_b1.button(
        "✏️ Editar Serviço Selecionado",
        key="btn_editar_serv",
        use_container_width=True,
    ):
      if id_serv_sel is not None:
        st.session_state["modal_edit_serv_id"] = int(id_serv_sel)
        st.rerun()
      else:
        st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

    if col_srv_b2.button(
        "🗑️ Excluir Serviço Selecionado",
        key="btn_excluir_serv",
        use_container_width=True,
    ):
      if id_serv_sel is not None:
        st.session_state["modal_excluir_ativo"] = True
        st.session_state["modal_excluir_tabela"] = "servicos_realizados"
        st.session_state["modal_excluir_id"] = int(id_serv_sel)
        st.session_state["modal_excluir_editor_key"] = "editor_selecao_servicos"
        st.session_state["sel_id_serv"] = None
        st.rerun()
      else:
        st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

    st.write("")

    df_srv["Selecionar"] = df_srv["_id_banco"] == st.session_state["sel_id_serv"]
    cols_srv_ord = [
        "Selecionar",
        "_id_banco",
        "empresa",
        "servico",
        "data_realizacao",
        "responsavel",
        "valor",
        "status",
        "nfes",
        "observacoes",
    ]
    df_srv_sel = df_srv[[c for c in cols_srv_ord if c in df_srv.columns]]

    if "valor" in df_srv_sel.columns and callable(
        formatar_valor_brasileiro_func
    ):
      df_srv_sel["valor"] = df_srv_sel["valor"].apply(
          formatar_valor_brasileiro_func
      )
    if "status" in df_srv_sel.columns:
      df_srv_sel["status"] = df_srv_sel["status"].apply(
          lambda x: formatar_status_visual_seguro(x, "serv")
      )

    df_srv_exib = (
        adicionar_numeracao_func(df_srv_sel)
        if callable(adicionar_numeracao_func)
        else df_srv_sel
    )

    editado_serv = st.data_editor(
        df_srv_exib,
        hide_index=True,
        num_rows="fixed",
        key="editor_selecao_servicos",
        use_container_width=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar", required=True, pinned=True
            ),
            "_id_banco": None,
            "Nº": st.column_config.NumberColumn(
                "Nº", disabled=True, pinned=True
            ),
            "servico": st.column_config.TextColumn(
                "Serviço Executado", disabled=True, pinned=True
            ),
        },
    )

    curr_srv = (
        editado_serv[editado_serv["Selecionar"] == True]["_id_banco"].tolist()
    )
    new_srv = [
        uid for uid in curr_srv if uid != st.session_state["sel_id_serv"]
    ]

    if new_srv:
      st.session_state["sel_id_serv"] = new_srv[-1]
      st.rerun()
    elif not curr_srv and st.session_state["sel_id_serv"] is not None:
      st.session_state["sel_id_serv"] = None
      st.rerun()

    if st.session_state.get("modal_edit_serv_id"):
      if callable(dialog_editar_servico_func):
        try:
          dialog_editar_servico_func(st.session_state["modal_edit_serv_id"])
        except Exception:
          pass
      st.session_state["modal_edit_serv_id"] = None
  else:
    st.info("ℹ️ Nenhum serviço cadastrado.")