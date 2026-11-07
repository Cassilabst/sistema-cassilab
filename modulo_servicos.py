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

    # --- SEÇÃO DE CADASTRO PADRONIZADA (IGUAL À ABA DE SETORES) ---
    st.markdown("### Gerenciar Serviços por Empresa")
    st.markdown("---")

    empresa_sel = st.selectbox(
        "Selecione a Empresa",
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
            "Valor do Serviço (R$)",
            min_value=0.0,
            value=0.0,
            step=50.0,
            format="%.2f",
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
    st.markdown("<div id='ancora_servicos'></div>", unsafe_allow_html=True)
    st.markdown(
        "<script>window.location.hash = 'ancora_servicos';</script>",
        unsafe_allow_html=True,
    )

    st.subheader("Serviços Registrados")

    empresa_global_atual = st.session_state.get("empresa_global", "Todas")
    opcoes_filtro_emp = ["Todas as Empresas"] + empresas
    idx_filtro_inicial = 0
    if empresa_global_atual in opcoes_filtro_emp and empresa_global_atual != "Todas":
        idx_filtro_inicial = opcoes_filtro_emp.index(empresa_global_atual)

    filtro_serv = st.selectbox(
        "Filtrar por Empresa",
        opcoes_filtro_emp,
        index=idx_filtro_inicial,
        key="filtro_servicos_empresa_local",
        on_change=safe_reset_serv,
    )

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
        df_srv = pd.read_sql("SELECT * FROM servicos_realizados", conn)
    except:
        df_srv = pd.DataFrame()
    conn.close()

    if not df_srv.empty and "data_realizacao" in df_srv.columns:
        df_srv["_dt_parse"] = pd.to_datetime(
            df_srv["data_realizacao"], format="%d/%m/%Y", errors="coerce"
        )
        df_srv = (
            df_srv.sort_values(by=["_dt_parse", "id"], ascending=[False, False])
            .drop(columns=["_dt_parse"])
            .reset_index(drop=True)
        )

    if filtro_serv != "Todas as Empresas" and not df_srv.empty:
        df_srv = df_srv[
            df_srv["empresa"].astype(str).str.strip().str.lower()
            == str(filtro_serv).strip().lower()
        ]

    if not df_srv.empty:
        total_servicos = len(df_srv)
        try:
            valor_total = df_srv["valor"].astype(float).sum()
        except:
            valor_total = 0.0

        val_fmt_total = formatar_valor_brasileiro_func(valor_total) if callable(formatar_valor_brasileiro_func) else f"{valor_total:.2f}"

        col_m1, col_m2 = st.columns(2)
        col_m1.metric("📊 Total de Serviços Registrados", total_servicos)
        col_m2.metric("💰 Valor Total Acumulado", f"R$ {val_fmt_total}")
        st.markdown("---")

    if not df_srv.empty:
        df_srv["_id_banco"] = df_srv["id"]

        if "sel_id_serv" not in st.session_state:
            st.session_state["sel_id_serv"] = None

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

        linhas_marcadas = editado_serv[editado_serv["Selecionar"] == True][
            "_id_banco"
        ].tolist()

        if linhas_marcadas:
            novo_selecionado = int(linhas_marcadas[-1])
            if st.session_state["sel_id_serv"] != novo_selecionado:
                st.session_state["sel_id_serv"] = novo_selecionado
                st.rerun()
        else:
            if st.session_state["sel_id_serv"] is not None:
                st.session_state["sel_id_serv"] = None

        st.write("")
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("✏️ Editar Serviço Selecionado", use_container_width=True, key="btn_editar_serv_acao"):
                if st.session_state["sel_id_serv"] is not None:
                    id_alvo_ed = int(st.session_state["sel_id_serv"])
                    st.session_state["sel_id_serv"] = None
                    if "editor_selecao_servicos" in st.session_state:
                        del st.session_state["editor_selecao_servicos"]
                    if callable(dialog_editar_servico_func):
                        dialog_editar_servico_func(id_alvo_ed)
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho para editar.")

        with col_btn2:
            if st.button("🗑️ Excluir Serviço Selecionado", use_container_width=True, key="btn_excluir_serv_acao"):
                if st.session_state["sel_id_serv"] is not None:
                    id_alvo_exc = int(st.session_state["sel_id_serv"])
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    conn.execute("DELETE FROM servicos_realizados WHERE id = ?", (id_alvo_exc,))
                    conn.commit()
                    conn.close()
                    st.session_state["sel_id_serv"] = None
                    if "editor_selecao_servicos" in st.session_state:
                        del st.session_state["editor_selecao_servicos"]
                    st.session_state["msg_sucesso"] = "🗑️ Serviço excluído com sucesso!"
                    registrar_log_func_seguro(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        f"Excluiu serviço ID {id_alvo_exc}",
                    )
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho para excluir.")

        if st.session_state.get("modal_edit_serv_id"):
            if callable(dialog_editar_servico_func):
                try:
                    dialog_editar_servico_func(st.session_state["modal_edit_serv_id"])
                except Exception:
                    pass
            st.session_state["modal_edit_serv_id"] = None
    else:
        st.info("ℹ️ Nenhum serviço cadastrado.")
