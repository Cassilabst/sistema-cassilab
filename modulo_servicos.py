import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def renderizar_aba_servicos(
    DB_NAME,
    is_admin,
    get_empresas_func,
    validar_e_formatar_data_input_func,
    formatar_titulo_func,
    formatar_valor_brasileiro_func,
    limpar_status_banco_func,
    atualizar_filtro_empresa_func,
    registrar_log_func,
    formatar_status_visual_func,
    adicionar_numeracao_func,
    reset_serv_selection_func,
    dialog_editar_servico_func
):
    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador.")
    else:
        col_h1, col_h2 = st.columns([0.8, 0.2])
        with col_h1: st.title("🛠️ Controle de Serviços Realizados")
        with col_h2:
            st.write("")
            if st.button("🔄 Atualizar Aba", key="btn_atualizar_serv"): st.rerun()

        empresas = get_empresas_func()
        with st.expander("➕ Registrar Novo Serviço Realizado", expanded=False):
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            df_cad_serv = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            lista_serv_cad = df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []
            if empresas:
                with st.form("form_servico_tradicional"):
                    c1, c2 = st.columns(2)
                    empresa_sel_srv = c1.selectbox("Empresa Cliente", empresas)
                    data_realizacao_input = c1.text_input("Data da Realização (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                    if lista_serv_cad:
                        servico_sel = c1.selectbox("Serviço Executado", lista_serv_cad)
                    else:
                        servico_sel = c1.text_input("Serviço Executado")
                    valor_input = c1.number_input("Valor do Serviço (R$)", min_value=0.0, value=0.0, step=50.0, format="%.2f")
                    responsavel_srv = c2.text_input("Responsável Técnico", value="Luiz Marcelo Fontana")
                    status_srv = c2.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"])
                    nfes_input = c2.text_input("NFES / Nº da Nota")
                    observacoes_srv = c2.text_input("Observações")
                    
                    if st.form_submit_button("Salvar Serviço"):
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        serv_fmt = formatar_titulo_func(servico_sel)
                        conn.execute("""
                            INSERT INTO servicos_realizados 
                            (empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel_srv, 
                            serv_fmt, 
                            validar_e_formatar_data_input_func(data_realizacao_input), 
                            formatar_titulo_func(responsavel_srv), 
                            observacoes_srv, 
                            float(valor_input),
                            limpar_status_banco_func(status_srv),
                            str(nfes_input).strip()
                        ))
                        conn.commit()
                        conn.close()
                        
                        if "editor_selecao_servicos" in st.session_state: 
                            del st.session_state["editor_selecao_servicos"]
                        st.session_state["sel_id_serv"] = None
                        
                        atualizar_filtro_empresa_func(empresa_sel_srv)
                        
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log_func(st.session_state.get("nome_usuario", "Administrador"), empresa_sel_srv, f"Registrou serviço ({serv_fmt})")
                        st.rerun()

        st.subheader("Serviços Registrados")
        col_f1, col_f2 = st.columns(2)
        filtro_srv = col_f1.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_srv_emp_trad", on_change=reset_serv_selection_func)
        
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_serv = pd.read_sql("SELECT id, empresa, servico, data_realizacao, responsavel, observacoes, status, valor, nfes FROM servicos_realizados", conn)
        conn.close()

        if filtro_srv != "Todas as Empresas" and not df_serv.empty:
            df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == str(filtro_srv).strip().lower()]

        if not df_serv.empty:
            df_serv["_dt_temp"] = pd.to_datetime(df_serv["data_realizacao"], dayfirst=True, errors="coerce")
            meses_disponiveis = ["Todos os Meses"]
            if df_serv["_dt_temp"].notna().any():
                m_unicos = df_serv["_dt_temp"].dropna().dt.strftime("%m/%Y").unique()
                m_unicos = sorted(m_unicos, key=lambda x: datetime.strptime(x, "%m/%Y"), reverse=True)
                meses_disponiveis.extend(m_unicos)
                
            filtro_mes = col_f2.selectbox("Filtrar por Mês", meses_disponiveis, key="filtro_srv_mes", on_change=reset_serv_selection_func)
            if filtro_mes != "Todos os Meses":
                df_serv["_mes_ano"] = df_serv["_dt_temp"].dt.strftime("%m/%Y")
                df_serv = df_serv[df_serv["_mes_ano"] == filtro_mes]
                df_serv = df_serv.drop(columns=["_mes_ano"])
                
            df_serv = df_serv.sort_values(by="_dt_temp", ascending=False, na_position="last").drop(columns=["_dt_temp"])
            valor_total_soma = pd.to_numeric(df_serv["valor"], errors="coerce").fillna(0.0).sum()
            
            st.markdown(f"<p style='font-size: 13px; color: #555; margin-bottom: 8px;'>Total: <b>R$ {formatar_valor_brasileiro_func(valor_total_soma)}</b></p>", unsafe_allow_html=True)
            
            if "sel_id_serv" not in st.session_state: 
                st.session_state["sel_id_serv"] = None
                
            df_serv["_id_banco"] = df_serv["id"]
            df_serv["Selecionar"] = df_serv["_id_banco"] == st.session_state["sel_id_serv"]
            df_tabela_sel = df_serv[["Selecionar", "_id_banco", "empresa", "data_realizacao", "servico", "responsavel", "observacoes", "status", "valor", "nfes"]].copy()
            df_tabela_sel["status"] = df_tabela_sel["status"].apply(lambda x: formatar_status_visual_func(x, "serv"))
            df_tabela_sel["valor_fmt"] = pd.to_numeric(df_tabela_sel["valor"], errors="coerce").fillna(0.0).apply(formatar_valor_brasileiro_func)
            
            df_tabela_exib = df_tabela_sel[["Selecionar", "_id_banco", "empresa", "data_realizacao", "servico", "responsavel", "observacoes", "status", "valor_fmt", "nfes"]].rename(columns={
                "empresa": "Empresa",
                "data_realizacao": "Data da Realização",
                "servico": "Serviço Executado",
                "responsavel": "Responsável",
                "observacoes": "Observações",
                "status": "Status",
                "valor_fmt": "Valor do Serviço (R$)",
                "nfes": "NFES"
            })
            
            df_tabela_exib = adicionar_numeracao_func(df_tabela_exib)
            editado_tabela = st.data_editor(
                df_tabela_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_servicos",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )
            
            curr_sv = editado_tabela[editado_tabela["Selecionar"] == True]["_id_banco"].tolist()
            new_sv = [uid for uid in curr_sv if uid != st.session_state["sel_id_serv"]]
            
            if new_sv:
                st.session_state["sel_id_serv"] = new_sv[-1]
                st.rerun()
            elif not curr_sv and st.session_state["sel_id_serv"] is not None:
                st.session_state["sel_id_serv"] = None
                st.rerun()
                
            linhas_selecionadas = editado_tabela[editado_tabela["Selecionar"] == True]
            col_b1, col_b2 = st.columns(2)
            
            if col_b1.button("✏️ Editar Linha Selecionada", key="btn_ir_editar", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    st.session_state["modal_edit_serv_id"] = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho.")
                    
            if col_b2.button("🗑️ Excluir Linha Selecionada", key="btn_ir_excluir", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "servicos_realizados"
                    st.session_state["modal_excluir_id"] = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_servicos"
                    st.session_state["sel_id_serv"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho.")
                    
            if st.session_state.get("modal_edit_serv_id"):
                dialog_editar_servico_func(st.session_state["modal_edit_serv_id"])
                st.session_state["modal_edit_serv_id"] = None
        else:
            st.info("ℹ️ Nenhum serviço registrado para esta seleção.")