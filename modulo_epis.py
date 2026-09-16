import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def verificar_status_ca(data_val_str, situacao_oficial="VÁLIDO"):
    """Verifica o status do CA retornando o texto formatado e a cor."""
    sit = str(situacao_oficial).upper()
    if "REVALIDA" in sit:
        return "🟠 Em Revalidação"
    
    if not data_val_str or str(data_val_str).strip() in ("", "nan", "None", "N/A"):
        return "❌ Inexistente"
        
    try:
        dt_val = datetime.strptime(str(data_val_str).strip()[:10], "%d/%m/%Y")
        hoje = datetime.today()
        
        if sit == "VENCIDO" or dt_val < hoje:
            return "🔴 Vencido"
        else:
            return "🟢 Válido"
    except:
        return "❌ Inexistente"

def renderizar_aba_epis(
    DB_NAME,
    is_admin,
    emp_usuario,
    pode_lancar,
    pode_editar,
    pode_excluir,
    get_empresas_func,
    validar_e_formatar_data_input_func,
    limpar_status_banco_func,
    atualizar_filtro_empresa_func,
    registrar_log_func,
    formatar_data_br_func,
    formatar_status_visual_func,
    formatar_colunas_func,
    adicionar_numeracao_func,
    reset_epi_selection_func,
    dialog_editar_epi_func
):
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🦺 Controle de Equipamentos de Proteção Individual (EPI)")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_epis"): st.rerun()

    empresas = get_empresas_func()
    
    if pode_lancar:
        with st.expander("➕ Registrar Entrega de EPI", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_epi") if is_admin else emp_usuario
            
            conn_e = sqlite3.connect(DB_NAME, timeout=10.0)
            # Puxando também validade e situação da tabela cad_epis (Cadastros Gerais)
            try:
                df_e_all = pd.read_sql("SELECT epi, ca, validade, situacao, empresa FROM cad_epis ORDER BY epi ASC", conn_e)
            except:
                df_e_all = pd.read_sql("SELECT epi, ca, empresa FROM cad_epis ORDER BY epi ASC", conn_e)
                df_e_all["validade"] = ""
                df_e_all["situacao"] = "VÁLIDO"

            df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn_e)
            conn_e.close()
            
            df_e_emp = df_e_all[df_e_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()] if not df_e_all.empty else pd.DataFrame()
            df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()] if not df_funcs_all.empty else pd.DataFrame()
            
            lista_epis_emp = df_e_emp["epi"].tolist() if not df_e_emp.empty else []
            mapa_ca_epis = dict(zip(df_e_emp["epi"], df_e_emp["ca"])) if not df_e_emp.empty else {}
            
            # Criar dicionários para checar validade do CA selecionado
            mapa_val_epis = dict(zip(df_e_emp["epi"], df_e_emp["validade"])) if not df_e_emp.empty and "validade" in df_e_emp.columns else {}
            mapa_sit_epis = dict(zip(df_e_emp["epi"], df_e_emp["situacao"])) if not df_e_emp.empty and "situacao" in df_e_emp.columns else {}

            if not df_funcs.empty and lista_epis_emp:
                with st.form("form_epi"):
                    c1, c2 = st.columns(2)
                    nome_sel = c1.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    epi_sel = c1.selectbox("EPI", lista_epis_emp)
                    
                    ca_padrao = mapa_ca_epis.get(epi_sel, "")
                    ca_epi = c2.text_input("Número do CA", value=ca_padrao)
                    
                    # Validação automática do CA do cadastro geral
                    val_cad = mapa_val_epis.get(epi_sel, "")
                    sit_cad = mapa_sit_epis.get(epi_sel, "VÁLIDO")
                    status_ca_geral = verificar_status_ca(val_cad, sit_cad)
                    
                    st.info(f"🛡️ Status do CA no Cadastro Geral: **{status_ca_geral}** (Validade: {val_cad or 'Não informada'})")

                    data_entrega = c1.text_input("Data Entrega", value=datetime.today().strftime("%d/%m/%Y"))
                    qtd = c2.number_input("Quantidade", min_value=1, value=1)
                    status_epi = c1.selectbox("Status do EPI", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"])
                    
                    if st.form_submit_button("Salvar EPI"):
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        
                        # Garantir que a tabela epis possua a coluna status_ca se formos salvar
                        cursor_aux = conn.cursor()
                        cursor_aux.execute("PRAGMA table_info(epis)")
                        colunas_epis = [col[1] for col in cursor_aux.fetchall()]
                        if "status_ca" not in colunas_epis:
                            cursor_aux.execute("ALTER TABLE epis ADD COLUMN status_ca TEXT")
                        conn.commit()

                        conn.execute("""
                            INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status, status_ca) 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel, 
                            colab['matricula'], 
                            nome_sel, 
                            colab['cargo'], 
                            colab['setor'], 
                            epi_sel, 
                            ca_epi, 
                            validar_e_formatar_data_input_func(data_entrega), 
                            int(qtd), 
                            limpar_status_banco_func(status_epi),
                            status_ca_geral
                        ))
                        conn.commit()
                        conn.close()
                        
                        if "editor_selecao_epis" in st.session_state: 
                            del st.session_state["editor_selecao_epis"]
                        st.session_state["sel_id_epi"] = None
                        
                        atualizar_filtro_empresa_func(empresa_sel)
                        
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log_func(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Registrou entrega de EPI ({epi_sel}) para {nome_sel}")
                        st.rerun()

    st.subheader("EPIs Registrados")
    filtro_ep = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ep_emp", on_change=reset_epi_selection_func) if is_admin else emp_usuario
    
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_ep = pd.read_sql("SELECT * FROM epis ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_ep != "Todas as Empresas" and not df_ep.empty:
        df_ep = df_ep[df_ep["empresa"].astype(str).str.strip().str.lower() == str(filtro_ep).strip().lower()]
    elif not is_admin and not df_ep.empty:
        df_ep = df_ep[df_ep["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_ep.empty:
        df_ep["data_entrega"] = df_ep["data_entrega"].apply(formatar_data_br_func)
        df_ep["status"] = df_ep["status"].apply(lambda x: formatar_status_visual_func(x, "epi"))
        
        # Se a coluna status_ca não existir no banco antigo, preenche dinamicamente
        if "status_ca" not in df_ep.columns:
            df_ep["status_ca"] = "🟢 Válido"
        
        df_ep["_id_banco"] = df_ep["id"]
        
        if is_admin or pode_editar:
            if "sel_id_epi" not in st.session_state: 
                st.session_state["sel_id_epi"] = None
                
            df_ep["Selecionar"] = df_ep["_id_banco"] == st.session_state["sel_id_epi"]
            cols_ep_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "epi", "ca", "status_ca", "data_entrega", "quantidade", "status"]
            df_ep_sel = df_ep[[c for c in cols_ep_ord if c in df_ep.columns]]
            df_ep_exib = formatar_colunas_func(df_ep_sel)
            df_ep_exib = adicionar_numeracao_func(df_ep_exib)
            
            editado_ep = st.data_editor(
                df_ep_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_epis",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )
            
            curr_ep = editado_ep[editado_ep["Selecionar"] == True]["_id_banco"].tolist()
            new_ep = [uid for uid in curr_ep if uid != st.session_state["sel_id_epi"]]
            
            if new_ep:
                st.session_state["sel_id_epi"] = new_ep[-1]
                st.rerun()
            elif not curr_ep and st.session_state["sel_id_epi"] is not None:
                st.session_state["sel_id_epi"] = None
                st.rerun()
                
            linhas_sel_ep = editado_ep[editado_ep["Selecionar"] == True]
            col_ep_b1, col_ep_b2 = st.columns(2)
            
            if pode_editar and col_ep_b1.button("✏️ Editar EPI Selecionado", key="btn_editar_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    st.session_state["modal_edit_epi_id"] = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um EPI marcando o quadradinho.")
                    
            if pode_excluir and col_ep_b2.button("🗑️ Excluir EPI Selecionado", key="btn_excluir_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "epis"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_epis"
                    st.session_state["sel_id_epi"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um EPI marcando o quadradinho.")
                    
            if st.session_state.get("modal_edit_epi_id"):
                dialog_editar_epi_func(st.session_state["modal_edit_epi_id"])
                st.session_state["modal_edit_epi_id"] = None
        else:
            cols_visualizacao = [c for c in ["empresa", "funcionario", "cargo", "setor", "epi", "ca", "status_ca", "data_entrega", "quantidade", "status"] if c in df_ep.columns]
            df_ep_exib = df_ep[cols_visualizacao]
            df_ep_exib = adicionar_numeracao_func(df_ep_exib)
            st.dataframe(formatar_colunas_func(df_ep_exib), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum EPI encontrado.")