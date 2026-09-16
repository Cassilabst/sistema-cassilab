import streamlit as st
import sqlite3
import pandas as pd

def garantir_tabela_e_colunas(DB_NAME):
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(base_funcionarios)")
    cols = [col[1] for col in cursor.fetchall()]
    if "data_nascimento" not in cols:
        try:
            cursor.execute("ALTER TABLE base_funcionarios ADD COLUMN data_nascimento TEXT")
            conn.commit()
        except:
            pass
    conn.close()

def formatar_data_flexivel(texto):
    if not texto:
        return ""
    # Extrai apenas os números digitados (aceita se o usuário digitou com ou sem /)
    digitos = "".join(filter(str.isdigit, str(texto)))
    # Se tiver 8 dígitos, formata automaticamente com as barras DD/MM/AAAA
    if len(digitos) == 8:
        return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"
    return str(texto).strip()

def buscar_cargos_por_empresa_seguro(DB_NAME, empresa_nome):
    if not empresa_nome or empresa_nome == "-- Selecione a Empresa --":
        return []
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cargos = []
    try:
        cursor = conn.cursor()
        for tabela in ["cargos", "cad_cargos", "base_cargos", "cadastros_gerais"]:
            try:
                cursor.execute(f"SELECT * FROM {tabela}")
                rows = cursor.fetchall()
                col_names = [description[0].lower() for description in cursor.description]
                emp_idx = next((i for i, c in enumerate(col_names) if 'empresa' in c), None)
                cargo_idx = next((i for i, c in enumerate(col_names) if any(k in c for k in ['cargo', 'nome', 'descricao'])), None)
                if emp_idx is not None and cargo_idx is not None:
                    for row in rows:
                        if str(row[emp_idx]).strip().lower() == str(empresa_nome).strip().lower():
                            val = str(row[cargo_idx]).strip()
                            if val and val not in cargos:
                                cargos.append(val)
            except:
                continue
    except:
        pass
    finally:
        conn.close()
    return sorted(cargos)

def buscar_setores_por_empresa_seguro(DB_NAME, empresa_nome):
    if not empresa_nome or empresa_nome == "-- Selecione a Empresa --":
        return []
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    setores = []
    try:
        cursor = conn.cursor()
        for tabela in ["setores", "cad_setores", "base_setores", "cadastros_gerais"]:
            try:
                cursor.execute(f"SELECT * FROM {tabela}")
                rows = cursor.fetchall()
                col_names = [description[0].lower() for description in cursor.description]
                emp_idx = next((i for i, c in enumerate(col_names) if 'empresa' in c), None)
                setor_idx = next((i for i, c in enumerate(col_names) if any(k in c for k in ['setor', 'nome', 'descricao'])), None)
                if emp_idx is not None and setor_idx is not None:
                    for row in rows:
                        if str(row[emp_idx]).strip().lower() == str(empresa_nome).strip().lower():
                            val = str(row[setor_idx]).strip()
                            if val and val not in setores:
                                setores.append(val)
            except:
                continue
    except:
        pass
    finally:
        conn.close()
    return sorted(setores)

def renderizar_aba_funcionarios(
    DB_NAME, is_admin, emp_usuario, pode_lancar, pode_editar, pode_excluir,
    get_empresas, get_cargos_por_empresa, get_setores_por_empresa, formatar_titulo,
    formatar_cpf, validar_e_formatar_data_input, limpar_status_banco,
    atualizar_filtro_empresa, registrar_log, formatar_data_br, formatar_status_visual,
    formatar_colunas_tabela, adicionar_numeracao, reset_func_selection, dialog_editar_funcionario
):
    garantir_tabela_e_colunas(DB_NAME)
    
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("👥 Gestão de Funcionários")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atu_func"): st.rerun()

    empresas = get_empresas()

    if pode_lancar:
        with st.expander("➕ Cadastrar Novo Funcionário", expanded=False):
            with st.form("form_cad_func_novo", clear_on_submit=True):
                emp_cad_options = empresas if empresas else []
                emp_cad = st.selectbox("Selecione a Empresa*", ["-- Selecione a Empresa --"] + emp_cad_options, key="form_cad_empresa_sel")
                
                cargos_disp = buscar_cargos_por_empresa_seguro(DB_NAME, emp_cad)
                setores_disp = buscar_setores_por_empresa_seguro(DB_NAME, emp_cad)

                c1, c2, c3 = st.columns(3)
                with c1:
                    mat = st.text_input("Matrícula")
                    cargo = st.selectbox("Cargo", cargos_disp) if cargos_disp else st.text_input("Cargo (Nenhum cadastrado)")
                with c2:
                    nome = st.text_input("Nome Completo*")
                    setor = st.selectbox("Setor", setores_disp) if setores_disp else st.text_input("Setor (Nenhum cadastrado)")
                with c3:
                    cpf = st.text_input("CPF")
                    dt_adm = st.text_input("Data Admissão")
                
                c4, c5 = st.columns(2)
                with c4:
                    dt_nasc_input = st.text_input("Data de Nascimento")
                with c5:
                    status = st.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"])
                
                btn_salvar = st.form_submit_button("💾 Salvar Funcionário", use_container_width=True)
                if btn_salvar:
                    if emp_cad == "-- Selecione a Empresa --":
                        st.error("Por favor, selecione uma empresa válida para o cadastro!")
                    elif not nome.strip():
                        st.error("O Nome Completo é obrigatório!")
                    else:
                        # Aplica a formatação flexível em ambas as datas para garantir que sejam salvas com /
                        dt_adm_fmt = formatar_data_flexivel(dt_adm)
                        dt_nasc_fmt = formatar_data_flexivel(dt_nasc_input)

                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        conn.execute("""
                            INSERT INTO base_funcionarios (empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status, data_nascimento)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            emp_cad, str(mat).strip(), formatar_titulo(nome),
                            str(cargo).strip(), str(setor).strip(), formatar_cpf(cpf),
                            dt_adm_fmt, limpar_status_banco(status), dt_nasc_fmt
                        ))
                        conn.commit()
                        conn.close()
                        st.session_state["msg_sucesso"] = "✅ Funcionário cadastrado com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Admin"), emp_cad, f"Cadastrou funcionário: {formatar_titulo(nome)}")
                        st.rerun()

    st.markdown("---")
    st.subheader("Funcionários Registrados")

    if is_admin:
        opcoes_filtro = ["Todas as Empresas"] + (empresas if empresas else [])
        emp_sel = st.selectbox("Filtrar por Empresa", opcoes_filtro, key="filtro_func_emp_tabela")
    else:
        emp_sel = emp_usuario
        st.info(f"Empresa Vinculada: **{emp_sel}**")

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
        df = pd.read_sql("SELECT * FROM base_funcionarios", conn)
    except:
        df = pd.DataFrame()
    conn.close()

    if not df.empty:
        if not is_admin:
            df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        elif is_admin and emp_sel != "Todas as Empresas":
            df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_sel).strip().lower()]

        if not df.empty:
            if "funcionario" in df.columns:
                df = df.sort_values(by="funcionario", ascending=True)

            if "last_sel_func_id" not in st.session_state:
                st.session_state["last_sel_func_id"] = None

            df["_id_banco"] = df["id"]
            df["Selecionar"] = df["_id_banco"] == st.session_state["last_sel_func_id"]
            
            if "id" in df.columns:
                df = df.drop(columns=["id"])

            cols_ordem = ["Selecionar", "_id_banco", "empresa", "matricula", "funcionario", "cargo", "setor", "cpf", "data_nascimento", "data_admissao", "status"]
            cols_validas = [c for c in cols_ordem if c in df.columns]
            df_view = df[cols_validas].copy()
            df_view = formatar_colunas_tabela(df_view)
            df_view = adicionar_numeracao(df_view)

            edit_df = st.data_editor(
                df_view,
                hide_index=True,
                num_rows="fixed",
                key="editor_funcionarios_checkbox",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            linhas_marcadas = edit_df[edit_df["Selecionar"] == True]
            ids_marcados = linhas_marcadas["_id_banco"].tolist()

            if ids_marcados:
                novo_id = [uid for uid in ids_marcados if uid != st.session_state["last_sel_func_id"]]
                if novo_id:
                    st.session_state["last_sel_func_id"] = novo_id[-1]
                    st.rerun()
                elif len(ids_marcados) > 1:
                    st.session_state["last_sel_func_id"] = ids_marcados[-1]
                    st.rerun()
            else:
                if st.session_state["last_sel_func_id"] is not None:
                    st.session_state["last_sel_func_id"] = None
                    st.rerun()

            id_selecionado = st.session_state["last_sel_func_id"]

            st.write("")
            c_btn1, c_btn2 = st.columns(2)
            
            if id_selecionado is not None:
                if pode_editar and c_btn1.button("✏️ Editar Funcionário Selecionado", use_container_width=True):
                    st.session_state["modal_edit_func_id"] = id_selecionado
                    st.rerun()
                if pode_excluir and c_btn2.button("🗑️ Excluir Funcionário Selecionado", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    conn.execute("DELETE FROM base_funcionarios WHERE id = ?", (id_selecionado,))
                    conn.commit()
                    conn.close()
                    st.session_state["last_sel_func_id"] = None
                    st.session_state["msg_sucesso"] = "✅ Funcionário excluído com sucesso!"
                    st.rerun()
            else:
                c_btn1.button("✏️ Editar Funcionário Selecionado", use_container_width=True, disabled=True)
                c_btn2.button("🗑️ Excluir Funcionário Selecionado", use_container_width=True, disabled=True)

            if st.session_state.get("modal_edit_func_id"):
                dialog_editar_funcionario(st.session_state["modal_edit_func_id"])
        else:
            st.info("Nenhum funcionário encontrado para esta empresa.")
    else:
        st.info("Nenhum funcionário cadastrado no sistema.")