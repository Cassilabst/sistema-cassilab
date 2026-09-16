import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def garantir_tabela_absenteismo(DB_NAME):
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS absenteismo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            matricula TEXT,
            nome TEXT,
            cargo TEXT,
            setor TEXT,
            cpf TEXT,
            data_nascimento TEXT,
            data_admissao TEXT,
            data_afastamento TEXT,
            retorno TEXT,
            cid TEXT,
            conselho TEXT,
            dias_previstos INTEGER,
            dias INTEGER,
            horas_previstas REAL,
            horas_perdidas REAL,
            motivo TEXT,
            tipo_atestado TEXT,
            turno TEXT,
            genero TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(absenteismo)")
    cols = [col[1] for col in cursor.fetchall()]
    
    colunas_necessarias = [
        ("matricula", "TEXT"),
        ("cargo", "TEXT"),
        ("setor", "TEXT"),
        ("cpf", "TEXT"),
        ("data_nascimento", "TEXT"),
        ("data_admissao", "TEXT"),
        ("data_afastamento", "TEXT"),
        ("retorno", "TEXT"),
        ("cid", "TEXT"),
        ("conselho", "TEXT"),
        ("dias_previstos", "INTEGER"),
        ("dias", "INTEGER"),
        ("horas_previstas", "REAL"),
        ("horas_perdidas", "REAL"),
        ("motivo", "TEXT"),
        ("tipo_atestado", "TEXT"),
        ("turno", "TEXT"),
        ("genero", "TEXT")
    ]
    
    for col_nome, col_tipo in colunas_necessarias:
        if col_nome not in cols:
            try:
                cursor.execute(f"ALTER TABLE absenteismo ADD COLUMN {col_nome} {col_tipo}")
            except:
                pass
                
    conn.commit()
    conn.close()

def formatar_data_flexivel(texto):
    if not texto:
        return ""
    digitos = "".join(filter(str.isdigit, str(texto)))
    if len(digitos) == 8:
        return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"
    return str(texto).strip()

def calcular_idade_e_tempo(dt_nasc_str, dt_adm_str):
    hoje = datetime.now()
    idade = ""
    tempo_emp = ""
    try:
        if dt_nasc_str and "/" in dt_nasc_str:
            partes = dt_nasc_str.split("/")
            if len(partes) == 3:
                nasc = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
                anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
                idade = f"{anos} anos"
    except:
        pass
    
    try:
        if dt_adm_str and "/" in dt_adm_str:
            partes = dt_adm_str.split("/")
            if len(partes) == 3:
                adm = datetime(int(partes[2]), int(partes[1]), int(partes[0]))
                anos_emp = hoje.year - adm.year - ((hoje.month, hoje.day) < (adm.month, adm.day))
                if anos_emp < 0: anos_emp = 0
                tempo_emp = f"{anos_emp} anos"
    except:
        pass
    return idade, tempo_emp

def calcular_dias_e_horas_automatico(dt_afast_str, dt_ret_str):
    try:
        f_a = "".join(filter(str.isdigit, str(dt_afast_str)))
        f_r = "".join(filter(str.isdigit, str(dt_ret_str)))
        if len(f_a) == 8 and len(f_r) == 8:
            d1 = datetime(int(f_a[4:]), int(f_a[2:4]), int(f_a[:2]))
            d2 = datetime(int(f_r[4:]), int(f_r[2:4]), int(f_r[:2]))
            if d2 >= d1:
                dias = (d2 - d1).days + 1
                horas = float(dias * 8.0)
                return int(dias), horas
    except:
        pass
    return 0, 0.0

def renderizar_aba_absenteismo(
    DB_NAME, is_admin, emp_usuario, get_empresas, registrar_log,
    pode_lancar=True, pode_editar=True, pode_excluir=True,
    formatar_titulo=lambda x: str(x).title(),
    validar_e_formatar_data_input=lambda x: formatar_data_flexivel(x)
):
    garantir_tabela_absenteismo(DB_NAME)

    col_h1, col_h2 = st.columns([0.7, 0.3])
    with col_h1: st.title("📊 Gestão de Absenteísmo")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atu_abs", use_container_width=True): st.rerun()

    empresas = get_empresas() if callable(get_empresas) else []

    aba_selecionada = st.radio(
        "Navegação Absenteísmo", 
        ["📋 Registros e Lançamentos", "📈 Dashboard Analítico"], 
        horizontal=True, 
        label_visibility="collapsed"
    )

    st.markdown("---")

    if aba_selecionada == "📋 Registros e Lançamentos":
        if pode_lancar:
            with st.expander("➕ Registrar Novo Absenteísmo", expanded=False):
                
                if is_admin:
                    emp_abs_options = empresas if empresas else []
                    emp_abs = st.selectbox("Selecione a Empresa*", ["-- Selecione a Empresa --"] + emp_abs_options, key="form_abs_emp")
                else:
                    emp_abs = emp_usuario
                    st.info(f"Empresa Vinculada: **{emp_abs}**")

                funcionarios_da_empresa = []
                dados_func_dict = {}
                if emp_abs and emp_abs != "-- Selecione a Empresa --":
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    try:
                        df_f = pd.read_sql("SELECT * FROM base_funcionarios", conn)
                    except:
                        df_f = pd.DataFrame()
                    conn.close()

                    if not df_f.empty and "empresa" in df_f.columns:
                        emp_alvo = str(emp_abs).strip().lower()
                        df_f = df_f[df_f["empresa"].astype(str).str.strip().str.lower() == emp_alvo]

                    if not df_f.empty:
                        df_f = df_f.sort_values(by="funcionario", ascending=True)
                        for _, row in df_f.iterrows():
                            nome_f = str(row.get("funcionario", ""))
                            if nome_f and nome_f != "None":
                                funcionarios_da_empresa.append(nome_f)
                                dados_func_dict[nome_f] = {
                                    "matricula": str(row.get("matricula", "")),
                                    "cargo": str(row.get("cargo", "")),
                                    "setor": str(row.get("setor", "")),
                                    "cpf": str(row.get("cpf", "")),
                                    "data_nascimento": str(row.get("data_nascimento", "")),
                                    "data_admissao": str(row.get("data_admissao", ""))
                                }

                nome_selecionado = st.selectbox(
                    "Selecione o Colaborador*", 
                    ["-- Selecionar Colaborador --"] + funcionarios_da_empresa,
                    key="form_abs_colab"
                )

                info_atual = dados_func_dict.get(nome_selecionado, {}) if nome_selecionado != "-- Selecionar Colaborador --" else {}

                st.markdown("##### 📅 Período do Afastamento")
                dc1, dc2 = st.columns(2)
                with dc1:
                    dt_afast_raw = st.text_input("Data do Afastamento (DD/MM/AAAA ou números)", key="input_dt_afast_dinamico")
                with dc2:
                    retorno_raw = st.text_input("Data de Retorno (DD/MM/AAAA ou números)", key="input_retorno_dinamico")

                dt_afast = validar_e_formatar_data_input(dt_afast_raw) if callable(validar_e_formatar_data_input) else formatar_data_flexivel(dt_afast_raw)
                retorno = validar_e_formatar_data_input(retorno_raw) if callable(validar_e_formatar_data_input) else formatar_data_flexivel(retorno_raw)

                dias_calc, horas_calc = calcular_dias_e_horas_automatico(dt_afast, retorno)

                with st.form("form_cad_abs", clear_on_submit=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        mat_cad = st.text_input("Matrícula", value=info_atual.get("matricula", ""))
                        cargo_cad = st.text_input("Cargo", value=info_atual.get("cargo", ""))
                    with c2:
                        setor_cad = st.text_input("Setor", value=info_atual.get("setor", ""))
                        cpf_cad = st.text_input("CPF", value=info_atual.get("cpf", ""))
                    with c3:
                        dt_nasc_cad = st.text_input("Data de Nascimento", value=info_atual.get("data_nascimento", ""))
                        dt_adm_cad = st.text_input("Data Admissão", value=info_atual.get("data_admissao", ""))

                    st.markdown("---")
                    c6, c7, c8 = st.columns(3)
                    with c6:
                        dias_previstos = st.number_input("Dias Previstos", min_value=0, value=dias_calc)
                    with c7:
                        dias = st.number_input("Dias Perdidos", min_value=0, value=dias_calc if dias_calc > 0 else 1)
                    with c8:
                        horas_previstas = st.number_input("Horas Previstas", min_value=0.0, value=horas_calc, step=0.5)

                    c9, c10, c11, c12, c13 = st.columns(5)
                    with c9:
                        horas_perdidas = st.number_input("Horas Perdidas", min_value=0.0, value=horas_calc if horas_calc > 0.0 else 0.0, step=0.5)
                    with c10:
                        cid = st.text_input("CID")
                    with c11:
                        conselho = st.text_input("Conselho")
                    with c12:
                        tipo_atestado = st.selectbox("Tipo Atestado", ["Atestado Médico", "Acompanhante", "Comparecimento"])
                    with c13:
                        turno = st.selectbox("Turno", ["Diurno", "Noturno", "Administrativo", "Outro"])

                    c14, c15 = st.columns(2)
                    with c14:
                        genero = st.selectbox("Gênero", ["Masculino", "Feminino", "Outro"])
                    with c15:
                        local_atendimento = st.text_input("Local Atendimento")

                    btn_salvar_abs = st.form_submit_button("💾 Salvar Registro de Absenteísmo", use_container_width=True)
                    if btn_salvar_abs:
                        if emp_abs == "-- Selecione a Empresa --" or not emp_abs:
                            st.error("Selecione uma empresa válida!")
                        elif nome_selecionado == "-- Selecionar Colaborador --" or not nome_selecionado:
                            st.error("Selecione um colaborador válido!")
                        elif not dt_afast or not retorno:
                            st.error("Informe a Data do Afastamento e a Data de Retorno!")
                        else:
                            conn = sqlite3.connect(DB_NAME, timeout=10.0)
                            conn.execute("""
                                INSERT INTO absenteismo (
                                    empresa, matricula, nome, cargo, setor, cpf, data_nascimento, data_admissao, 
                                    data_afastamento, retorno, dias_previstos, dias, horas_previstas, horas_perdidas, 
                                    cid, conselho, motivo, tipo_atestado, turno, genero
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                emp_abs, str(mat_cad), formatar_titulo(nome_selecionado) if callable(formatar_titulo) else nome_selecionado,
                                str(cargo_cad), str(setor_cad), str(cpf_cad),
                                str(dt_nasc_cad), str(dt_adm_cad),
                                dt_afast, retorno, int(dias_previstos), int(dias), 
                                float(horas_previstas), float(horas_perdidas),
                                str(cid).upper(), str(conselho), formatar_titulo(local_atendimento) if callable(formatar_titulo) else local_atendimento,
                                tipo_atestado, turno, genero
                            ))
                            conn.commit()
                            conn.close()
                            st.session_state["msg_sucesso"] = "✅ Absenteísmo registrado com sucesso!"
                            if callable(registrar_log):
                                registrar_log(st.session_state.get("nome_usuario", "Admin"), emp_abs, f"Registrou absenteísmo para: {nome_selecionado}")
                            st.rerun()

        st.subheader("Registros Cadastrados")
        if is_admin:
            opcoes_filtro = ["Todas as Empresas"] + (empresas if empresas else [])
            emp_sel = st.selectbox("Filtrar por Empresa", opcoes_filtro, key="filtro_abs_emp_tabela")
        else:
            emp_sel = emp_usuario
            st.info(f"Empresa Vinculada: **{emp_sel}**")

        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
            df = pd.read_sql("SELECT * FROM absenteismo", conn)
        except:
            df = pd.DataFrame()
        conn.close()

        if not df.empty:
            if not is_admin:
                df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
            elif is_admin and emp_sel != "Todas as Empresas":
                df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_sel).strip().lower()]

            if not df.empty:
                if "nome" in df.columns:
                    df = df.sort_values(by="nome", ascending=True)

                if "last_sel_abs_id" not in st.session_state:
                    st.session_state["last_sel_abs_id"] = None

                id_selecionado = st.session_state["last_sel_abs_id"]

                # BOTÕES DE AÇÃO NA PARTE DE CIMA
                st.write("")
                c_btn1, c_btn2 = st.columns(2)
                
                if pode_editar and id_selecionado is not None:
                    if c_btn1.button("✏️ Editar Registro Selecionado", use_container_width=True):
                        st.session_state["edit_abs_id"] = id_selecionado
                        st.rerun()
                else:
                    c_btn1.button("✏️ Editar Registro Selecionado", use_container_width=True, disabled=True)

                if pode_excluir and id_selecionado is not None:
                    if c_btn2.button("🗑️ Excluir Registro Selecionado", use_container_width=True):
                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM absenteismo WHERE id = ?", (id_selecionado,))
                        conn.commit()
                        conn.close()
                        st.session_state["last_sel_abs_id"] = None
                        st.session_state["msg_sucesso"] = "✅ Registro de absenteísmo excluído com sucesso!"
                        st.rerun()
                else:
                    c_btn2.button("🗑️ Excluir Registro Selecionado", use_container_width=True, disabled=True)

                st.write("")

                df["_id_banco"] = df["id"]
                df["Selecionar"] = df["_id_banco"] == st.session_state["last_sel_abs_id"]
                
                if "id" in df.columns:
                    df = df.drop(columns=["id"])

                df.insert(1, "Nº", range(1, len(df) + 1))

                df = df.rename(columns={
                    "matricula": "Matrícula",
                    "nome": "Nome",
                    "setor": "Setor",
                    "data_afastamento": "Data Afastamento",
                    "dias": "Dias Perdidos",
                    "cid": "CID",
                    "conselho": "Conselho",
                    "tipo_atestado": "Tipo Atestado",
                    "motivo": "Local Atendimento",
                    "dias_previstos": "Dias Previstos",
                    "horas_previstas": "Horas Previstas",
                    "horas_perdidas": "Horas Perdidas"
                })

                # ==========================================
                # VISÕES POR ABAS (SUBDIVIDIDAS POR CATEGORIA)
                # ==========================================
                aba_geral, aba_medica, aba_prazos = st.tabs([
                    "📋 Visão Geral", 
                    "🏥 Visão Médica", 
                    "⏱️ Visão de Prazos/Horas"
                ])

                with aba_geral:
                    cols_geral = ["Selecionar", "Nº", "_id_banco", "Matrícula", "Nome", "Setor", "Data Afastamento", "Dias Perdidos"]
                    cols_v_geral = [c for c in cols_geral if c in df.columns]
                    df_geral = df[cols_v_geral].copy()
                    
                    edit_df_geral = st.data_editor(
                        df_geral,
                        hide_index=True,
                        num_rows="fixed",
                        key="editor_abs_geral",
                        use_container_width=True,
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                            "_id_banco": None,
                            "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                        }
                    )

                with aba_medica:
                    cols_medica = ["Selecionar", "Nº", "_id_banco", "Nome", "CID", "Conselho", "Tipo Atestado", "Local Atendimento"]
                    cols_v_medica = [c for c in cols_medica if c in df.columns]
                    df_medica = df[cols_v_medica].copy()
                    
                    edit_df_medica = st.data_editor(
                        df_medica,
                        hide_index=True,
                        num_rows="fixed",
                        key="editor_abs_medica",
                        use_container_width=True,
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                            "_id_banco": None,
                            "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                        }
                    )

                with aba_prazos:
                    cols_prazos = ["Selecionar", "Nº", "_id_banco", "Nome", "Dias Previstos", "Dias Perdidos", "Horas Previstas", "Horas Perdidas"]
                    cols_v_prazos = [c for c in cols_prazos if c in df.columns]
                    df_prazos = df[cols_v_prazos].copy()
                    
                    edit_df_prazos = st.data_editor(
                        df_prazos,
                        hide_index=True,
                        num_rows="fixed",
                        key="editor_abs_prazos",
                        use_container_width=True,
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                            "_id_banco": None,
                            "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                        }
                    )

                # Captura unificada de seleções em qualquer aba
                ids_marcados = []
                for ed_f in [edit_df_geral, edit_df_medica, edit_df_prazos]:
                    if "Selecionar" in ed_f.columns and "_id_banco" in ed_f.columns:
                        m = ed_f[ed_f["Selecionar"] == True]
                        if not m.empty:
                            ids_marcados.extend(m["_id_banco"].tolist())
                ids_marcados = list(dict.fromkeys(ids_marcados))

                if ids_marcados:
                    novo_id = [uid for uid in ids_marcados if uid != st.session_state["last_sel_abs_id"]]
                    if novo_id:
                        st.session_state["last_sel_abs_id"] = novo_id[-1]
                        st.rerun()
                    elif len(ids_marcados) > 1:
                        st.session_state["last_sel_abs_id"] = ids_marcados[-1]
                        st.rerun()
                else:
                    if st.session_state["last_sel_abs_id"] is not None:
                        st.session_state["last_sel_abs_id"] = None
                        st.rerun()

                # Formulário de Edição
                if st.session_state.get("edit_abs_id"):
                    edit_id = st.session_state["edit_abs_id"]
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT empresa, matricula, nome, cargo, setor, cpf, data_nascimento, data_admissao, 
                               data_afastamento, retorno, dias_previstos, dias, horas_previstas, horas_perdidas, 
                               cid, conselho, motivo, tipo_atestado, turno, genero 
                        FROM absenteismo WHERE id = ?
                    """, (edit_id,))
                    reg_edit = cursor.fetchone()
                    conn.close()

                    if reg_edit:
                        (e_emp, e_mat, e_nome, e_cargo, e_setor, e_cpf, e_nasc, e_adm, 
                         e_afast, e_ret, e_d_prev, e_dias, e_h_prev, e_h_perd, 
                         e_cid, e_conselho, e_motivo, e_tipo, e_turno, e_genero) = reg_edit
                        
                        st.markdown("---")
                        st.markdown(f"### ✏️ Editando Registro de: **{e_nome}** ({e_emp})")
                        with st.form(f"form_edicao_abs_{edit_id}"):
                            ec1, ec2, ec3 = st.columns(3)
                            with ec1:
                                ed_mat = st.text_input("Matrícula", value=str(e_mat or ""))
                                ed_cargo = st.text_input("Cargo", value=str(e_cargo or ""))
                            with ec2:
                                ed_setor = st.text_input("Setor", value=str(e_setor or ""))
                                ed_cpf = st.text_input("CPF", value=str(e_cpf or ""))
                            with ec3:
                                ed_nasc = st.text_input("Data de Nascimento", value=str(e_nasc or ""))
                                ed_adm = st.text_input("Data Admissão", value=str(e_adm or ""))

                            ec4, ec5, ec6, ec7, ec8 = st.columns(5)
                            with ec4:
                                ed_afast = st.text_input("Data do Afastamento", value=str(e_afast or ""))
                            with ec5:
                                ed_ret = st.text_input("Data de Retorno", value=str(e_ret or ""))
                            with ec6:
                                ed_d_prev = st.number_input("Dias Previstos", min_value=0, value=int(e_d_prev or 0))
                            with ec7:
                                ed_dias = st.number_input("Dias Perdidos", min_value=0, value=int(e_dias or 0))
                            with ec8:
                                ed_h_prev = st.number_input("Horas Previstas", min_value=0.0, value=float(e_h_prev or 0.0), step=0.5)

                            ec9, ec10, ec11, ec12, ec13 = st.columns(5)
                            with ec9:
                                ed_h_perd = st.number_input("Horas Perdidas", min_value=0.0, value=float(e_h_perd or 0.0), step=0.5)
                            with ec10:
                                ed_cid = st.text_input("CID", value=str(e_cid or ""))
                            with ec11:
                                ed_conselho = st.text_input("Conselho", value=str(e_conselho or ""))
                            with ec12:
                                tipos_op = ["Atestado Médico", "Acompanhante", "Comparecimento"]
                                idx_tipo = tipos_op.index(e_tipo) if e_tipo in tipos_op else 0
                                ed_tipo = st.selectbox("Tipo Atestado", tipos_op, index=idx_tipo)
                            with ec13:
                                turnos_op = ["Diurno", "Noturno", "Administrativo", "Outro"]
                                idx_turno = turnos_op.index(e_turno) if e_turno in turnos_op else 0
                                ed_turno = st.selectbox("Turno", turnos_op, index=idx_turno)

                            ec14, ec15 = st.columns(2)
                            with ec14:
                                generos_op = ["Masculino", "Feminino", "Outro"]
                                idx_gen = generos_op.index(e_genero) if e_genero in generos_op else 0
                                ed_genero = st.selectbox("Gênero", generos_op, index=idx_gen)
                            with ec15:
                                ed_motivo = st.text_input("Local Atendimento", value=str(e_motivo or ""))

                            col_salv_ed, col_canc_ed = st.columns(2)
                            btn_salvar_ed = col_salv_ed.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                            btn_canc_ed = col_canc_ed.form_submit_button("❌ Cancelar", use_container_width=True)

                            if btn_salvar_ed:
                                dt_afast_f = formatar_data_flexivel(ed_afast)
                                dt_ret_f = formatar_data_flexivel(ed_ret)
                                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                                conn.execute("""
                                    UPDATE absenteismo 
                                    SET matricula = ?, cargo = ?, setor = ?, cpf = ?, data_nascimento = ?, data_admissao = ?, 
                                        data_afastamento = ?, retorno = ?, dias_previstos = ?, dias = ?, 
                                        horas_previstas = ?, horas_perdidas = ?, cid = ?, conselho = ?, motivo = ?, 
                                        tipo_atestado = ?, turno = ?, genero = ?
                                    WHERE id = ?
                                """, (
                                    str(ed_mat), str(ed_cargo), str(ed_setor), str(ed_cpf), str(ed_nasc), str(ed_adm),
                                    dt_afast_f, dt_ret_f, int(ed_d_prev), int(ed_dias), float(ed_h_prev), float(ed_h_perd),
                                    str(ed_cid).upper(), str(ed_conselho), str(ed_motivo), ed_tipo, ed_turno, ed_genero, edit_id
                                ))
                                conn.commit()
                                conn.close()
                                st.session_state["edit_abs_id"] = None
                                st.session_state["last_sel_abs_id"] = None
                                st.session_state["msg_sucesso"] = "✅ Registro de absenteísmo atualizado com sucesso!"
                                st.rerun()
                            
                            if btn_canc_ed:
                                st.session_state["edit_abs_id"] = None
                                st.rerun()

            else:
                st.info("Nenhum registro encontrado para esta empresa.")
        else:
            st.info("Nenhum registro cadastrado no sistema.")

    elif aba_selecionada == "📈 Dashboard Analítico":
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
            df = pd.read_sql("SELECT * FROM absenteismo", conn)
        except:
            df = pd.DataFrame()
        conn.close()

        if not is_admin:
            if not df.empty and "empresa" in df.columns:
                df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

        if df.empty:
            st.warning("⚠️ Não há dados suficientes cadastrados para gerar o Dashboard Analítico.")
        else:
            if is_admin:
                opcoes_dash_emp = ["Todas as Empresas"] + (empresas if empresas else [])
                emp_dash_sel = st.selectbox("Filtrar Dashboard por Empresa", opcoes_dash_emp, key="dash_emp_sel")
                if emp_dash_sel != "Todas as Empresas":
                    df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_dash_sel).strip().lower()]

            st.markdown("### 📊 Indicadores Principais")
            
            total_afastamentos = len(df)
            total_dias_perdidos = int(df["dias"].sum()) if "dias" in df.columns else 0
            total_horas_perdidas = float(df["horas_perdidas"].sum()) if "horas_perdidas" in df.columns else float(total_dias_perdidos * 8)
            
            idades = []
            for _, r in df.iterrows():
                dt_nasc = str(r.get("data_nascimento", ""))
                try:
                    ano_nasc = int(dt_nasc.split("/")[-1]) if "/" in dt_nasc and len(dt_nasc.split("/")[-1]) == 4 else 0
                    if ano_nasc > 1900:
                        idades.append(datetime.now().year - ano_nasc)
                except:
                    pass
            idade_media = round(sum(idades) / len(idades), 1) if idades else 0

            tempos = []
            for _, r in df.iterrows():
                dt_adm = str(r.get("data_admissao", ""))
                try:
                    ano_adm = int(dt_adm.split("/")[-1]) if "/" in dt_adm and len(dt_adm.split("/")[-1]) == 4 else 0
                    if ano_adm > 1900:
                        tempos.append(datetime.now().year - ano_adm)
                except:
                    pass
            tempo_empresa_medio = round(sum(tempos) / len(tempos), 1) if tempos else 0

            total_cids = df["cid"].nunique() if "cid" in df.columns else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Dias Perdidos", total_dias_perdidos)
            k2.metric("Horas Perdidas", f"{total_horas_perdidas:.2f}")
            k3.metric("Idade Média (Anos)", idade_media)
            k4.metric("Tempo Empresa Médio", tempo_empresa_medio)

            k5, k6 = st.columns(2)
            k5.metric("Quantidade TOTAL CID", total_cids)
            k6.metric("Total de Ocorrências", total_afastamentos)

            st.markdown("---")

            g1, g2 = st.columns(2)
            with g1:
                st.subheader("TOP 5 Local Atendimento")
                if "motivo" in df.columns and not df["motivo"].dropna().empty:
                    st.bar_chart(df["motivo"].value_counts().head(5))
                else:
                    st.info("Sem dados suficientes.")

            with g2:
                st.subheader("TOP 5 Turnos com Maiores Ocorrências")
                if "turno" in df.columns and not df["turno"].dropna().empty:
                    st.bar_chart(df["turno"].value_counts().head(5))
                else:
                    st.info("Sem dados suficientes para turnos.")

            st.markdown("---")

            g3, g4 = st.columns(2)
            with g3:
                st.subheader("TOP 5 Quantidade de CID")
                if "cid" in df.columns and not df["cid"].dropna().empty:
                    st.bar_chart(df["cid"].value_counts().head(5))
                else:
                    st.info("Sem dados suficientes para CIDs.")

            with g4:
                st.subheader("TOP 5 Setores com Maior Índice")
                if "setor" in df.columns and not df["setor"].dropna().empty:
                    st.bar_chart(df["setor"].value_counts().head(5))
                else:
                    st.info("Sem dados suficientes para setores.")