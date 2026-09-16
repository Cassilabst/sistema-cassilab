import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def renderizar_aba_empresas(
    DB_NAME, 
    is_admin, 
    emp_usuario, 
    formatar_titulo_func, 
    formatar_data_br_func, 
    formatar_cnpj_func, 
    consultar_cnpj_func, 
    consultar_cep_func, 
    consultar_grau_risco_func, 
    formatar_colunas_func, 
    adicionar_numeracao_func, 
    atualizar_filtro_empresa_func, 
    registrar_log_func
):
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🏢 Cadastro de Empresas Clientes")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_empresas"): st.rerun()

    if is_admin:
        with st.expander("➕ Adicionar Nova Empresa", expanded=False):
            if "form_emp_nome" not in st.session_state: st.session_state["form_emp_nome"] = ""
            if "form_emp_cnpj" not in st.session_state: st.session_state["form_emp_cnpj"] = ""
            if "form_cep" not in st.session_state: st.session_state["form_cep"] = ""
            if "form_end" not in st.session_state: st.session_state["form_end"] = ""
            if "form_bair" not in st.session_state: st.session_state["form_bair"] = ""
            if "form_cid" not in st.session_state: st.session_state["form_cid"] = ""
            if "form_tel" not in st.session_state: st.session_state["form_tel"] = ""
            if "form_email" not in st.session_state: st.session_state["form_email"] = ""
            if "form_resp" not in st.session_state: st.session_state["form_resp"] = ""
            if "form_grau_risco" not in st.session_state: st.session_state["form_grau_risco"] = "1"
            if "form_cnae_consulta" not in st.session_state: st.session_state["form_cnae_consulta"] = ""
            if "form_lista_cnaes" not in st.session_state: st.session_state["form_lista_cnaes"] = []

            with st.form("form_empresa"):
                col_r1_1, col_r1_2, col_r1_3 = st.columns([2, 1.2, 1.2])
                nome_empresa = col_r1_1.text_input("Nome da Empresa *", value=st.session_state["form_emp_nome"])
                sub_c_cnpj_1, sub_c_cnpj_2 = col_r1_2.columns([1.3, 1])
                cnpj = sub_c_cnpj_1.text_input("CNPJ", value=st.session_state["form_emp_cnpj"])
                sub_c_cnpj_2.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                btn_buscar_cnpj = sub_c_cnpj_2.form_submit_button("🔍 Consultar CNPJ", use_container_width=True)
                sub_c_cep_1, sub_c_cep_2 = col_r1_3.columns([1.3, 1])
                cep_input = sub_c_cep_1.text_input("CEP", value=st.session_state["form_cep"])
                sub_c_cep_2.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                btn_buscar_cep = sub_c_cep_2.form_submit_button("🔍 Consultar CEP", use_container_width=True)
                
                col_r2_1, col_r2_2, col_r2_3 = st.columns(3)
                endereco_input = col_r2_1.text_input("Endereço", value=st.session_state["form_end"])
                bairro_input = col_r2_2.text_input("Bairro", value=st.session_state["form_bair"])
                cidade_input = col_r2_3.text_input("Cidade / UF", value=st.session_state["form_cid"])
                
                col_r3_1, col_r3_2, col_r3_3 = st.columns(3)
                telefone = col_r3_1.text_input("Telefone", value=st.session_state["form_tel"])
                email = col_r3_2.text_input("E-mail", value=st.session_state["form_email"])
                responsavel = col_r3_3.text_input("Responsável", value=st.session_state["form_resp"])
                
                if st.session_state["form_lista_cnaes"]:
                    cnae_escolhido_select = st.selectbox(
                        "📋 CNAEs do CNPJ (O 1º é o Principal)",
                        options=st.session_state["form_lista_cnaes"],
                        key="select_cnae_carregado"
                    )
                    if cnae_escolhido_select:
                        codigo_extraido = cnae_escolhido_select.split(" - ")[0].strip()
                        st.session_state["form_cnae_consulta"] = codigo_extraido
                        st.session_state["form_grau_risco"] = consultar_grau_risco_func(codigo_extraido)
                else:
                    st.session_state["form_cnae_consulta"] = st.text_input("CNAE", value=st.session_state["form_cnae_consulta"])
                
                col_r5_1, col_r5_2 = st.columns(2)
                opcoes_risco = ["1", "2", "3", "4"]
                try: idx_risco = opcoes_risco.index(str(st.session_state["form_grau_risco"]))
                except: idx_risco = 0
                grau_risco = col_r5_1.selectbox("Grau de Risco", opcoes_risco, index=idx_risco)
                qtd_funcionarios = col_r5_2.number_input("Qtd de Funcionários", min_value=0, value=0, step=1)
                btn_salvar_empresa = col_r5_1.form_submit_button("💾 Salvar Empresa", use_container_width=False)

                if btn_buscar_cnpj:
                    if cnpj.strip():
                        res_cnpj = consultar_cnpj_func(cnpj)
                        if res_cnpj:
                            st.session_state["form_emp_nome"] = res_cnpj.get("razao_social", "")
                            st.session_state["form_emp_cnpj"] = formatar_cnpj_func(cnpj)
                            st.session_state["form_cep"] = res_cnpj.get("cep", "")
                            st.session_state["form_end"] = res_cnpj.get("logradouro", "")
                            st.session_state["form_bair"] = res_cnpj.get("bairro", "")
                            st.session_state["form_cid"] = res_cnpj.get("cidade", "")
                            st.session_state["form_tel"] = res_cnpj.get("telefone", "")
                            st.session_state["form_email"] = res_cnpj.get("email", "")
                            st.session_state["form_grau_risco"] = res_cnpj.get("grau_risco", "1")
                            st.session_state["form_cnae_consulta"] = res_cnpj.get("cnae_principal", "")
                            st.session_state["form_lista_cnaes"] = res_cnpj.get("lista_cnaes", [])
                            st.success("Dados do CNPJ, CNAEs e Grau de Risco consultados com sucesso!")
                            st.rerun()
                        else:
                            st.error("CNPJ não encontrado ou inválido.")

                if btn_buscar_cep:
                    if cep_input.strip():
                        res_cep = consultar_cep_func(cep_input)
                        if res_cep:
                            st.session_state["form_cep"] = cep_input
                            st.session_state["form_end"] = res_cep.get("logradouro", "")
                            st.session_state["form_bair"] = res_cep.get("bairro", "")
                            st.session_state["form_cid"] = res_cep.get("cidade", "")
                            st.success("CEP encontrado!")
                            st.rerun()
                        else:
                            st.error("CEP não encontrado.")

                if btn_salvar_empresa:
                    if nome_empresa.strip():
                        nome_fmt = formatar_titulo_func(nome_empresa)
                        cnpj_formatado = formatar_cnpj_func(cnpj)
                        data_registro_atual = datetime.now().strftime("%d/%m/%Y")
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                INSERT INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, cnae, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                data_registro_atual, 
                                nome_fmt, 
                                cnpj_formatado, 
                                str(cep_input or "").strip(), 
                                formatar_titulo_func(cidade_input), 
                                formatar_titulo_func(bairro_input), 
                                formatar_titulo_func(endereco_input), 
                                str(telefone or "").strip(), 
                                str(email or "").strip(), 
                                formatar_titulo_func(responsavel), 
                                str(st.session_state["form_cnae_consulta"]).strip(),
                                str(grau_risco).strip(), 
                                int(qtd_funcionarios)
                            ))
                            conn.commit()
                            st.session_state["form_emp_nome"] = ""
                            st.session_state["form_emp_cnpj"] = ""
                            st.session_state["form_cep"] = ""
                            st.session_state["form_end"] = ""
                            st.session_state["form_bair"] = ""
                            st.session_state["form_cid"] = ""
                            st.session_state["form_tel"] = ""
                            st.session_state["form_email"] = ""
                            st.session_state["form_resp"] = ""
                            st.session_state["form_grau_risco"] = "1"
                            st.session_state["form_cnae_consulta"] = ""
                            st.session_state["form_lista_cnaes"] = []
                            if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                            
                            atualizar_filtro_empresa_func(nome_fmt)
                            
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log_func(st.session_state.get("nome_usuario", "Administrador"), nome_fmt, "Cadastro de nova empresa")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esta empresa já está cadastrada (nome ou CNPJ já existente no sistema).")
                        finally:
                            conn.close()
                    else:
                        st.error("O campo 'Nome da Empresa' é obrigatório.")

    st.subheader("Empresas Cadastradas")
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, cnae, grau_risco, qtd_funcionarios FROM empresas ORDER BY nome_empresa ASC", conn)
    conn.close()

    if not is_admin and not df_emp.empty:
        df_emp = df_emp[df_emp["nome_empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_emp.empty:
        if "data_registro" in df_emp.columns: df_emp["data_registro"] = df_emp["data_registro"].apply(formatar_data_br_func)
        if "cnpj" in df_emp.columns: df_emp["cnpj"] = df_emp["cnpj"].apply(formatar_cnpj_func)
        df_emp["_id_banco"] = df_emp["id"]
        cols_emp_ord = ["_id_banco"] + [c for c in df_emp.columns if c not in ["_id_banco", "id"]]
        df_emp = df_emp[cols_emp_ord]
        if is_admin:
            df_emp_exibicao = formatar_colunas_func(df_emp)
            df_emp_exibicao = adicionar_numeracao_func(df_emp_exibicao)
            editado_emp = st.data_editor(
                df_emp_exibicao, 
                num_rows="dynamic", 
                key="editor_emp", 
                use_container_width=True,
                column_config={
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )
            chk_salvar_emp = st.checkbox("⚠️ Confirmo salvar as alterações feitas na tabela de empresas", key="chk_salvar_emp")
            if st.button("💾 Salvar Alterações", key="btn_salvar_alt_emp"):
                if chk_salvar_emp:
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    erro_duplicidade = False
                    for _, row in editado_emp.iterrows():
                        emp_id = row.get("_id_banco", row.get("id"))
                        nome_emp_val = row.get("Nome Empresa", row.get("nome_empresa", ""))
                        if pd.notna(nome_emp_val) and str(nome_emp_val).strip():
                            try: qtd_func_val = int(row.get("Qtd Funcionários", row.get("qtd_funcionarios", 0)))
                            except: qtd_func_val = 0
                            try:
                                if pd.notna(emp_id) and str(emp_id).strip() not in ("", "nan", "None"):
                                    cursor.execute("""
                                        UPDATE empresas SET data_registro=?, nome_empresa=?, cnpj=?, cep=?, cidade=?, bairro=?, endereco=?, telefone=?, email=?, responsavel=?, cnae=?, grau_risco=?, qtd_funcionarios=?
                                        WHERE id=?
                                    """, (
                                        formatar_data_br_func(row.get("Data Registro", row.get("data_registro"))),
                                        formatar_titulo_func(nome_emp_val),
                                        formatar_cnpj_func(row.get("CNPJ", row.get("cnpj"))),
                                        str(row.get("CEP", row.get("cep", ""))).strip(),
                                        formatar_titulo_func(row.get("Cidade", row.get("cidade", ""))),
                                        formatar_titulo_func(row.get("Bairro", row.get("bairro", ""))),
                                        formatar_titulo_func(row.get("Endereço", row.get("endereco", ""))),
                                        str(row.get("Telefone", row.get("telefone", ""))).strip(),
                                        str(row.get("E-mail", row.get("email", ""))).strip(),
                                        formatar_titulo_func(row.get("Responsável", row.get("responsavel", ""))),
                                        str(row.get("CNAE", row.get("cnae", ""))).strip(),
                                        str(row.get("Grau Risco", row.get("grau_risco", "1"))).strip(),
                                        qtd_func_val,
                                        int(emp_id)
                                    ))
                                else:
                                    cursor.execute("""
                                        INSERT INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, cnae, grau_risco, qtd_funcionarios) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        formatar_data_br_func(row.get("Data Registro", row.get("data_registro"))),
                                        formatar_titulo_func(nome_emp_val),
                                        formatar_cnpj_func(row.get("CNPJ", row.get("cnpj"))),
                                        str(row.get("CEP", row.get("cep", ""))).strip(),
                                        formatar_titulo_func(row.get("Cidade", row.get("cidade", ""))),
                                        formatar_titulo_func(row.get("Bairro", row.get("bairro", ""))),
                                        formatar_titulo_func(row.get("Endereço", row.get("endereco", ""))),
                                        str(row.get("Telefone", row.get("telefone", ""))).strip(),
                                        str(row.get("E-mail", row.get("email", ""))).strip(),
                                        formatar_titulo_func(row.get("Responsável", row.get("responsavel", ""))),
                                        str(row.get("CNAE", row.get("cnae", ""))).strip(),
                                        str(row.get("Grau Risco", row.get("grau_risco", "1"))).strip(),
                                        qtd_func_val
                                    ))
                            except sqlite3.IntegrityError:
                                erro_duplicidade = True
                    conn.commit()
                    conn.close()
                    if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                    if erro_duplicidade:
                        st.warning("Algumas alterações não foram salvas pois gerariam duplicidade de Nome ou CNPJ.")
                    else:
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log_func(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de empresas")
                        st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação.")

            st.markdown("---")
            st.subheader("🗑️ Excluir Empresa Definitivamente")
            with st.form("form_excluir_empresa"):
                lista_nomes_empresas = sorted(df_emp["nome_empresa"].tolist() if "nome_empresa" in df_emp.columns else df_emp["Nome Empresa"].tolist())
                empresa_para_excluir = st.selectbox("Selecione a empresa que deseja excluir:", lista_nomes_empresas)
                chk_excluir_emp = st.checkbox("⚠️ Confirmo que desejo excluir esta empresa e todos os seus dados vinculados permanentemente")
                btn_executar_exclusao = st.form_submit_button("🗑️ Excluir Empresa e Dados Relacionados")
                if btn_executar_exclusao:
                    if chk_excluir_emp and empresa_para_excluir:
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM empresas WHERE nome_empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM base_funcionarios WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM exames WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM treinamentos WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM epis WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM servicos_realizados WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM usuarios_sistema WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_cargos WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_setores WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_epis WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM documentos WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM matriz_treinamentos_config WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM matriz_treinamentos_status WHERE empresa = ?", (empresa_para_excluir,))
                        conn.commit()
                        conn.close()
                        if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log_func(st.session_state.get("nome_usuario", "Administrador"), empresa_para_excluir, "Exclusão definitiva da empresa e dados")
                        st.rerun()
                    else:
                        st.error("Selecione a empresa e marque a caixa de confirmação para autorizar a exclusão.")
        else:
            df_exib_sem_banco = df_emp.drop(columns=["_id_banco"])
            df_exib_sem_banco = adicionar_numeracao_func(df_exib_sem_banco)
            st.dataframe(formatar_colunas_func(df_exib_sem_banco), use_container_width=True, hide_index=True)