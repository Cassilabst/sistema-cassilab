from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st


def renderizar_aba_documentos(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas_func,
    calcular_proxima_renovacao_func,
    calcular_status_por_data_func,
    validar_e_formatar_data_input_func,
    sincronizar_status_documentos_func,
    atualizar_filtro_empresa_func,
    registrar_log_func,
    formatar_data_br_func,
    formatar_status_visual_func,
    formatar_titulo_func,
    formatar_colunas_func,
    adicionar_numeracao_func,
    reset_doc_selection_func,
    dialog_editar_documento_func,
):
  col_h1, col_h2 = st.columns([0.8, 0.2])
  with col_h1:
    st.title("📄 Controle de Documentos da Empresa")
  with col_h2:
    st.write("")
    if st.button("🔄 Atualizar Aba", key="btn_atualizar_doc"):
      st.rerun()

  empresas = get_empresas_func()
  if pode_lancar:
    with st.expander("➕ Adicionar Novo Documento", expanded=False):
      empresa_sel = (
          st.selectbox("Selecione a Empresa", empresas, key="emp_doc_form")
          if is_admin
          else emp_usuario
      )
      conn = sqlite3.connect(DB_NAME, timeout=10.0)
      df_cad_serv_doc = pd.read_sql(
          "SELECT servico FROM cad_servicos ORDER BY servico ASC", conn
      )
      conn.close()
      lista_servicos_doc = (
          df_cad_serv_doc["servico"].tolist()
          if not df_cad_serv_doc.empty
          else []
      )
      with st.form("form_documento"):
        c1, c2 = st.columns(2)
        if lista_servicos_doc:
          nome_doc = c1.selectbox("Nome do Documento / Serviço", lista_servicos_doc)
        else:
          nome_doc = c1.text_input("Nome do Documento (ex: PGR, PCMSO, LTCAT)")
        dt_emissao = c2.text_input(
            "Data de Emissão", value=datetime.today().strftime("%d/%m/%Y")
        )
        vigencia_doc = c1.text_input(
            "Vigência (ex: 1 ano, 2 anos, 6 meses)", value="1 ano"
        )
        proximo_calc = calcular_proxima_renovacao_func(dt_emissao, vigencia_doc)
        proxima_renovacao_input = c2.text_input(
            "Data da Próxima Renovação/Atualização", value=proximo_calc
        )

        status_calc_form = calcular_status_por_data_func(
            proxima_renovacao_input if proxima_renovacao_input else proximo_calc
        )
        st.info(f"Status calculado automaticamente: **{status_calc_form}**")

        if st.form_submit_button("Salvar Documento"):
          if nome_doc and str(nome_doc).strip():
            proxima_renovacao_final = (
                calcular_proxima_renovacao_func(dt_emissao, vigencia_doc)
                if not proxima_renovacao_input
                else validar_e_formatar_data_input_func(proxima_renovacao_input)
            )
            status_final_form = calcular_status_por_data_func(
                proxima_renovacao_final
            )

            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            doc_fmt = formatar_titulo_func(nome_doc)
            conn.execute(
                """INSERT INTO documentos (empresa, documento, data_emissao, vigencia, proxima_renovacao, status) VALUES (?,?,?,?,?,?)""",
                (
                    empresa_sel,
                    doc_fmt,
                    validar_e_formatar_data_input_func(dt_emissao),
                    vigencia_doc.strip(),
                    proxima_renovacao_final,
                    status_final_form,
                ),
            )
            conn.commit()
            conn.close()
            sincronizar_status_documentos_func()
            if "editor_selecao_documentos" in st.session_state:
              del st.session_state["editor_selecao_documentos"]
            st.session_state["sel_id_doc"] = None

            atualizar_filtro_empresa_func(empresa_sel)

            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
            registrar_log_func(
                st.session_state.get("nome_usuario", "Desconhecido"),
                empresa_sel,
                f"Cadastrou documento: {doc_fmt}",
            )
            st.rerun()
          else:
            st.error("Preencha o nome do documento.")

  st.subheader("Documentos Cadastrados")
  filtro_doc = (
      st.selectbox(
          "Filtrar por Empresa",
          ["Todas as Empresas"] + empresas,
          key="filtro_doc_emp",
          on_change=reset_doc_selection_func,
      )
      if is_admin
      else emp_usuario
  )
  conn = sqlite3.connect(DB_NAME, timeout=10.0)
  df_doc = pd.read_sql("SELECT * FROM documentos ORDER BY documento ASC", conn)
  conn.close()

  if is_admin and filtro_doc != "Todas as Empresas" and not df_doc.empty:
    df_doc = df_doc[
        df_doc["empresa"].astype(str).str.strip().str.lower()
        == str(filtro_doc).strip().lower()
    ]
  elif not is_admin and not df_doc.empty:
    df_doc = df_doc[
        df_doc["empresa"].astype(str).str.strip().str.lower()
        == str(emp_usuario).strip().lower()
    ]

  if not df_doc.empty:
    df_doc["data_emissao"] = df_doc["data_emissao"].apply(formatar_data_br_func)
    df_doc["proxima_renovacao"] = df_doc["proxima_renovacao"].apply(
        formatar_data_br_func
    )
    df_doc["status"] = df_doc["status"].apply(
        lambda x: formatar_status_visual_func(x, "doc")
    )
    df_doc["_id_banco"] = df_doc["id"]
    if is_admin or pode_editar:
      if "sel_id_doc" not in st.session_state:
        st.session_state["sel_id_doc"] = None
      df_doc["Selecionar"] = df_doc["_id_banco"] == st.session_state["sel_id_doc"]
      cols_doc_ord = [
          "Selecionar",
          "_id_banco",
          "empresa",
          "documento",
          "data_emissao",
          "vigencia",
          "proxima_renovacao",
          "status",
      ]
      df_doc_sel = df_doc[[c for c in cols_doc_ord if c in df_doc.columns]]
      df_doc_exib = formatar_colunas_func(df_doc_sel)
      df_doc_exib = adicionar_numeracao_func(df_doc_exib)

      col_doc_b1, col_doc_b2 = st.columns(2)
      if pode_excluir:
        if col_doc_b2.button(
            "🗑️ Excluir Documento Selecionado",
            key="btn_excluir_doc",
            use_container_width=True,
        ):
          if st.session_state["sel_id_doc"] is not None:
            st.session_state["modal_excluir_ativo"] = True
            st.session_state["modal_excluir_tabela"] = "documentos"
            st.session_state["modal_excluir_id"] = int(
                st.session_state["sel_id_doc"]
            )
            st.session_state["modal_excluir_editor_key"] = (
                "editor_selecao_documentos"
            )
            st.session_state["sel_id_doc"] = None
            st.rerun()
          else:
            st.warning("⚠️ Selecione um documento marcando o quadradinho.")

      st.write("")

      editado_doc = st.data_editor(
          df_doc_exib,
          hide_index=True,
          num_rows="fixed",
          key="editor_selecao_documentos",
          use_container_width=True,
          column_config={
              "Selecionar": st.column_config.CheckboxColumn(
                  "Selecionar", required=True
              ),
              "_id_banco": None,
              "Nº": st.column_config.NumberColumn("Nº", disabled=True),
          },
      )

      linhas_marcadas = edit_df = editado_doc[
          editado_doc["Selecionar"] == True
      ]["_id_banco"].tolist()
      if linhas_marcadas and pode_editar:
        id_para_editar = int(linhas_marcadas[-1])
        st.session_state["sel_id_doc"] = None
        if "editor_selecao_documentos" in st.session_state:
          del st.session_state["editor_selecao_documentos"]
        dialog_editar_documento_func(id_para_editar)

      if st.session_state.get("modal_edit_doc_id"):
        dialog_editar_documento_func(st.session_state["modal_edit_doc_id"])
        st.session_state["modal_edit_doc_id"] = None
    else:
      df_doc_exib = df_doc[[
          "empresa",
          "documento",
          "data_emissao",
          "vigencia",
          "proxima_renovacao",
          "status",
      ]]
      df_doc_exib = adicionar_numeracao_func(df_doc_exib)
      st.dataframe(
          formatar_colunas_func(df_doc_exib),
          use_container_width=True,
          hide_index=True,
      )
  else:
    st.info("ℹ️ Nenhum documento cadastrado.")