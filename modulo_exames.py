import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def renderizar_aba_exames(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas_func,
    calcular_proximo_exame_func,
    validar_e_formatar_data_input_func,
    limpar_status_banco_func,
    sincronizar_status_exames_func,
    atualizar_filtro_empresa_func,
    registrar_log_func,
    formatar_data_br_func,
    formatar_status_visual_func,
    formatar_colunas_func,
    adicionar_numeracao_func,
    reset_ex_selection_func,
    dialog_editar_exame_func
):
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🩺 Controle de Exames Ocupacionais")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_exames"): st.rerun()

    empresas = get_empresas_func()
    
    if pode_lancar:
        with st.expander("➕ Adicionar Novo Exame", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="ex_emp") if is_admin else emp_usuario
            
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
            conn.close()
            
            if not df_funcs_all.empty:
                df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()]
            else:
                df_funcs = pd.DataFrame()
                
            if not df_funcs.empty:
                with st.form("form_exame"):
                    nome_sel = st.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    c1, c2 = st.columns(2)
                    ultimo = c1.text_input("Data Último Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    opcoes_periodicidade = ["1 mês", "3 meses", "6 meses", "12 meses", "18 meses", "24 meses"]
                    periodicidade_sel = c2.selectbox("Periodicidade", opcoes_periodicidade, index=3)
                    tipo_ex = c1.selectbox("Tipo", ["Admissional", "Periódico", "Retorno ao Trabalho", "Mudança de Riscos", "Demissional"])
                    
                    proximo_calculado = calcular_proximo_exame_func(ultimo, periodicidade_sel)
                    proximo = c2.text_input("Data Próximo Exame", value=proximo_calculado)
                    status_ex = c2.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"])
                    
                    if st.form_submit_button("Salvar Exame"):
                        proximo_final = calcular_proximo_exame_func(ultimo, periodicidade_sel) if not proximo else validar_e_formatar_data_input_func(proximo)
                        
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        conn.execute("""
                            INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, periodicidade, tipo_exame, proximo_exame, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel, 
                            colab['matricula'], 
                            nome_sel, 
                            colab['cargo'], 
                            colab['setor'], 
                            validar_e_formatar_data_input_func(ultimo), 
                            periodicidade_sel, 
                            tipo_ex, 
                            proximo_final, 
                            limpar_status_banco_func(status_ex)
                        ))
                        conn.commit()
                        conn.close()
                        
                        sincronizar_status_exames_func()
                        if "editor_selecao_exames" in st.session_state: 
                            del st.session_state["editor_selecao_exames"]
                        st.session_state["sel_id_ex"] = None
                        
                        atualizar_filtro_empresa_func(empresa_sel)
                        
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log_func(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Lançou exame ({tipo_ex}) para {nome_sel}")
                        st.rerun()

    st.subheader("Exames Registrados")
    filtro_ex = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ex_emp", on_change=reset_ex_selection_func) if is_admin else emp_usuario
    
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_ex = pd.read_sql("SELECT * FROM exames ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_ex != "Todas as Empresas" and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(filtro_ex).strip().lower()]
    elif not is_admin and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_ex.empty:
        df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br_func)
        df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br_func)
        df_ex["status"] = df_ex["status"].apply(lambda x: formatar_status_visual_func(x, "ex"))
        df_ex["_id_banco"] = df_ex["id"]
        
        if is_admin or pode_editar:
            if "sel_id_ex" not in st.session_state: 
                st.session_state["sel_id_ex"] = None
                
            df_ex["Selecionar"] = df_ex["_id_banco"] == st.session_state["sel_id_ex"]
            cols_ex_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "periodicidade", "proximo_exame", "status"]
            df_ex_sel = df_ex[[c for c in cols_ex_ord if c in df_ex.columns]]
            df_ex_exib = formatar_colunas_func(df_ex_sel)
            df_ex_exib = adicionar_numeracao_func(df_ex_exib)
            
            editado_ex = st.data_editor(
                df_ex_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_exames",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )
            
            curr_ex = editado_ex[editado_ex["Selecionar"] == True]["_id_banco"].tolist()
            new_ex = [uid for uid in curr_ex if uid != st.session_state["sel_id_ex"]]
            
            if new_ex:
                st.session_state["sel_id_ex"] = new_ex[-1]
                st.rerun()
            elif not curr_ex and st.session_state["sel_id_ex"] is not None:
                st.session_state["sel_id_ex"] = None
                st.rerun()
                
            linhas_sel_ex = editado_ex[editado_ex["Selecionar"] == True]
            col_ex_b1, col_ex_b2 = st.columns(2)
            
            if pode_editar and col_ex_b1.button("✏️ Editar Exame Selecionado", key="btn_editar_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    st.session_state["modal_edit_exame_id"] = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um exame marcando o quadradinho.")
                    
            if pode_excluir and col_ex_b2.button("🗑️ Excluir Exame Selecionado", key="btn_excluir_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "exames"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_exames"
                    st.session_state["sel_id_ex"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um exame marcando o quadradinho.")
                    
            if st.session_state.get("modal_edit_exame_id"):
                dialog_editar_exame_func(st.session_state["modal_edit_exame_id"])
                st.session_state["modal_edit_exame_id"] = None
        else:
            df_ex_exib = df_ex[["empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "periodicidade", "proximo_exame", "status"]]
            df_ex_exib = adicionar_numeracao_func(df_ex_exib)
            st.dataframe(formatar_colunas_func(df_ex_exib), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum exame encontrado.")