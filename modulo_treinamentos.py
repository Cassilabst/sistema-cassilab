import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def renderizar_aba_treinamentos(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas_func,
    calcular_proximo_treinamento_func,
    validar_e_formatar_data_input_func,
    limpar_status_banco_func,
    sincronizar_status_treinamentos_func,
    atualizar_filtro_empresa_func,
    registrar_log_func,
    formatar_data_br_func,
    formatar_status_visual_func,
    formatar_colunas_func,
    adicionar_numeracao_func,
    reset_tr_selection_func,
    dialog_editar_treinamento_func,
    renderizar_matriz_treinamentos_func
):
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("📚 Controle de Treinamentos")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_trein"): st.rerun()

    empresas = get_empresas_func()
    
    sub_tab_tr_1, sub_tab_tr_2 = st.tabs(["📋 Lista de Treinamentos Realizados", "📊 Matriz de Treinamentos (Geral por Empresa)"])
    
    with sub_tab_tr_1:
        if pode_lancar:
            with st.expander("➕ Inserção de Treinamento", expanded=False):
                empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_trein") if is_admin else emp_usuario
                
                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
                df_cad_trein = pd.read_sql("SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
                conn.close()
                
                if not df_funcs_all.empty:
                    df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()]
                else:
                    df_funcs = pd.DataFrame()
                    
                lista_trein_geral = df_cad_trein["treinamento"].tolist() if not df_cad_trein.empty else []
                lista_cargas_gerais = df_cad_trein["carga_horaria"].dropna().unique().tolist()
                if not lista_cargas_gerais:
                    lista_cargas_gerais = ["8 horas", "16 horas", "20 horas", "40 horas"]
                    
                if not df_funcs.empty and lista_trein_geral:
                    with st.form("form_trein"):
                        c1, c2 = st.columns(2)
                        func_sel = c1.selectbox("Nome do Funcionário", df_funcs["funcionario"].tolist())
                        colab = df_funcs[df_funcs["funcionario"] == func_sel].iloc[0]
                        trein_sel = c2.selectbox("Treinamento", lista_trein_geral)
                        carga_v = c1.selectbox("Carga Horária", lista_cargas_gerais)
                        tipo_treinamento_modalidade = c2.selectbox("Tipo de Treinamento", ["Presencial", "Semi-presencial", "EaD"])
                        dt_real = c1.text_input("Data da Realização", value=datetime.today().strftime("%d/%m/%Y"))
                        val_v = c2.text_input("Validade (ex: 12 meses, 24 meses)", value="12 meses")
                        
                        proximo_calculado_tr = calcular_proximo_treinamento_func(dt_real, val_v)
                        proximo_tr = c1.text_input("Data do Próximo Treinamento", value=proximo_calculado_tr)
                        status_tr = c2.selectbox("Status", ["🟢 em dia", "🔴 vencido"])
                        
                        if st.form_submit_button("Salvar Treinamento"):
                            proximo_final_tr = calcular_proximo_treinamento_func(dt_real, val_v) if not proximo_tr else validar_e_formatar_data_input_func(proximo_tr)
                            
                            conn = sqlite3.connect(DB_NAME, timeout=10.0)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, proximo_treinamento, status) 
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (
                                empresa_sel, 
                                str(colab['matricula']), 
                                func_sel, 
                                str(colab['cargo']), 
                                str(colab['setor']), 
                                trein_sel, 
                                carga_v, 
                                tipo_treinamento_modalidade, 
                                validar_e_formatar_data_input_func(dt_real), 
                                val_v, 
                                proximo_final_tr, 
                                limpar_status_banco_func(status_tr)
                            ))
                            conn.commit()
                            conn.close()
                            
                            sincronizar_status_treinamentos_func()
                            if "editor_selecao_treinamentos" in st.session_state: 
                                del st.session_state["editor_selecao_treinamentos"]
                            st.session_state["sel_id_tr"] = None
                            
                            atualizar_filtro_empresa_func(empresa_sel)
                            
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log_func(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Lançou treinamento ({trein_sel}) para {func_sel}")
                            st.rerun()

        st.subheader("Treinamentos Registrados")
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_tr = pd.read_sql("SELECT * FROM treinamentos ORDER BY funcionario ASC", conn)
        conn.close()

        if is_admin:
            col_f1, col_f2, col_f3 = st.columns(3)
            filtro_tr = col_f1.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_tr_emp", on_change=reset_tr_selection_func)
            df_tr_filtrado = df_tr.copy()
            
            if filtro_tr != "Todas as Empresas" and not df_tr_filtrado.empty:
                df_tr_filtrado = df_tr_filtrado[df_tr_filtrado["empresa"].astype(str).str.strip().str.lower() == str(filtro_tr).strip().lower()]
                
            lista_funcs_filtro = ["Todos os Funcionários"] + sorted(df_tr_filtrado["funcionario"].dropna().unique().tolist()) if not df_tr_filtrado.empty else ["Todos os Funcionários"]
            lista_trein_filtro = ["Todos os Treinamentos"] + sorted(df_tr_filtrado["treinamento"].dropna().unique().tolist()) if not df_tr_filtrado.empty else ["Todos os Treinamentos"]
            
            filtro_func_escolhido = col_f2.selectbox("Filtrar por Funcionário", lista_funcs_filtro, key="filtro_func_trein")
            filtro_trein_escolhido = col_f3.selectbox("Filtrar por Treinamento", lista_trein_filtro, key="filtro_tipo_trein")
            df_tr = df_tr_filtrado
        else:
            if not df_tr.empty:
                df_tr = df_tr[df_tr["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
            lista_funcs_filtro = ["Todos os Funcionários"] + sorted(df_tr["funcionario"].dropna().unique().tolist()) if not df_tr.empty else ["Todos os Funcionários"]
            lista_trein_filtro = ["Todos os Treinamentos"] + sorted(df_tr["treinamento"].dropna().unique().tolist()) if not df_tr.empty else ["Todos os Treinamentos"]
            
            col_f1, col_f2 = st.columns(2)
            filtro_func_escolhido = col_f1.selectbox("Filtrar por Funcionário", lista_funcs_filtro, key="filtro_func_trein")
            filtro_trein_escolhido = col_f2.selectbox("Filtrar por Treinamento", lista_trein_filtro, key="filtro_tipo_trein")

        if not df_tr.empty:
            if filtro_func_escolhido != "Todos os Funcionários":
                df_tr = df_tr[df_tr["funcionario"] == filtro_func_escolhido]
            if filtro_trein_escolhido != "Todos os Treinamentos":
                df_tr = df_tr[df_tr["treinamento"] == filtro_trein_escolhido]

        if not df_tr.empty:
            df_tr["data_realizacao"] = df_tr["data_realizacao"].apply(formatar_data_br_func)
            df_tr["proximo_treinamento"] = df_tr["proximo_treinamento"].apply(formatar_data_br_func)
            df_tr["status"] = df_tr["status"].apply(lambda x: formatar_status_visual_func(x, "trein"))
            df_tr["_id_banco"] = df_tr["id"]
            
            if is_admin or pode_editar:
                if "sel_id_tr" not in st.session_state: 
                    st.session_state["sel_id_tr"] = None
                    
                df_tr["Selecionar"] = df_tr["_id_banco"] == st.session_state["sel_id_tr"]
                cols_tr_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "proximo_treinamento", "status"]
                df_tr_sel = df_tr[[c for c in cols_tr_ord if c in df_tr.columns]]
                df_tr_exib = formatar_colunas_func(df_tr_sel)
                df_tr_exib = adicionar_numeracao_func(df_tr_exib)
                
                editado_trein = st.data_editor(
                    df_tr_exib,
                    hide_index=True,
                    num_rows="fixed",
                    key="editor_selecao_treinamentos",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )
                
                curr_tr = editado_trein[editado_trein["Selecionar"] == True]["_id_banco"].tolist()
                new_tr = [uid for uid in curr_tr if uid != st.session_state["sel_id_tr"]]
                
                if new_tr:
                    st.session_state["sel_id_tr"] = new_tr[-1]
                    st.rerun()
                elif not curr_tr and st.session_state["sel_id_tr"] is not None:
                    st.session_state["sel_id_tr"] = None
                    st.rerun()
                    
                linhas_sel_tr = editado_trein[editado_trein["Selecionar"] == True]
                col_tb1, col_tb2 = st.columns(2)
                
                if pode_editar and col_tb1.button("✏️ Editar Treinamento Selecionado", key="btn_editar_trein", use_container_width=True):
                    if len(linhas_sel_tr) == 1:
                        st.session_state["modal_edit_trein_id"] = int(linhas_sel_tr.iloc[0]["_id_banco"])
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")
                        
                if pode_excluir and col_tb2.button("🗑️ Excluir Treinamento Selecionado", key="btn_excluir_trein", use_container_width=True):
                    if len(linhas_sel_tr) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "treinamentos"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_tr.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "editor_selecao_treinamentos"
                        st.session_state["sel_id_tr"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")
                        
                if st.session_state.get("modal_edit_trein_id"):
                    dialog_editar_treinamento_func(st.session_state["modal_edit_trein_id"])
                    st.session_state["modal_edit_trein_id"] = None
            else:
                df_tr_exib = df_tr[["empresa", "funcionario", "cargo", "setor", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "proximo_treinamento", "status"]]
                df_tr_exib = adicionar_numeracao_func(df_tr_exib)
                st.dataframe(formatar_colunas_func(df_tr_exib), use_container_width=True, hide_index=True)
                
            st.markdown("---")
            total_treinamentos = len(df_tr)
            qtd_em_dia = df_tr["status"].apply(lambda x: 1 if "em dia" in limpar_status_banco_func(x).lower() else 0).sum()
            qtd_vencido = df_tr["status"].apply(lambda x: 1 if "vencido" in limpar_status_banco_func(x).lower() else 0).sum()
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("📚 Total de Treinamentos", total_treinamentos)
            col_m2.metric("🟢 Em Dia", qtd_em_dia)
            col_m3.metric("🔴 Vencidos", qtd_vencido)
        else:
            st.info("ℹ️ Nenhum treinamento encontrado para os filtros selecionados.")

    with sub_tab_tr_2:
        renderizar_matriz_treinamentos_func(DB_NAME, empresas, registrar_log_func)