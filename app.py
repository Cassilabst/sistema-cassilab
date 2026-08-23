import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# Configuração da Página
st.set_page_config(page_title="Cassilab - Gestão em SST", page_icon="🛡️", layout="wide")

# --- BANCO DE DADOS ---
DB_NAME = "cassilab_gestao.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Tabela Empresas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_empresa TEXT UNIQUE,
            cnpj TEXT,
            cep TEXT,
            cidade TEXT,
            bairro TEXT,
            endereco TEXT,
            telefone TEXT,
            email TEXT,
            responsavel TEXT,
            grau_risco TEXT,
            qtd_funcionarios INTEGER
        )
    """)
    
    # 2. Tabela Funcionários
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS base_funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT,
            funcionario TEXT,
            cargo TEXT,
            setor TEXT,
            cpf TEXT,
            data_admissao TEXT,
            status TEXT,
            empresa TEXT
        )
    """)
    
    # 3. Tabela Usuários do Sistema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cpf TEXT UNIQUE,
            empresa TEXT,
            senha TEXT
        )
    """)
    
    # 4. Tabela Exames
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            matricula TEXT,
            funcionario TEXT,
            cargo TEXT,
            setor TEXT,
            ultimo_exame TEXT,
            tipo_exame TEXT,
            proximo_exame TEXT,
            status TEXT
        )
    """)
    
    # 5. Tabela Treinamentos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS treinamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            matricula TEXT,
            funcionario TEXT,
            cargo TEXT,
            setor TEXT,
            treinamento TEXT,
            carga_horaria TEXT,
            data_realizacao TEXT,
            validade_meses INTEGER,
            proximo_vencimento TEXT,
            status TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(treinamentos);")
    cols_tr_db = [col[1] for col in cursor.fetchall()]
    colunas_novas_tr = [
        ("empresa", "TEXT"), ("matricula", "TEXT"), ("funcionario", "TEXT"), 
        ("cargo", "TEXT"), ("setor", "TEXT"), ("treinamento", "TEXT"), 
        ("carga_horaria", "TEXT"), ("data_realizacao", "TEXT"), 
        ("validade_meses", "INTEGER"), ("proximo_vencimento", "TEXT"), ("status", "TEXT")
    ]
    for col_nova, tipo_col in colunas_novas_tr:
        if col_nova not in cols_tr_db:
            try:
                cursor.execute(f"ALTER TABLE treinamentos ADD COLUMN {col_nova} {tipo_col};")
            except:
                pass
    
    # 6. Tabela EPIs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS epis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            matricula TEXT,
            funcionario TEXT,
            cargo TEXT,
            setor TEXT,
            epi TEXT,
            ca TEXT,
            data_entrega TEXT,
            quantidade INTEGER,
            status TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(epis);")
    cols_ep_db = [col[1] for col in cursor.fetchall()]
    colunas_novas_ep = [
        ("empresa", "TEXT"), ("matricula", "TEXT"), ("funcionario", "TEXT"), 
        ("cargo", "TEXT"), ("setor", "TEXT"), ("epi", "TEXT"), 
        ("ca", "TEXT"), ("data_entrega", "TEXT"), ("quantidade", "INTEGER"), ("status", "TEXT")
    ]
    for col_nova, tipo_col in colunas_novas_ep:
        if col_nova not in cols_ep_db:
            try:
                cursor.execute(f"ALTER TABLE epis ADD COLUMN {col_nova} {tipo_col};")
            except:
                pass

    # 7. Tabela Serviços Realizados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos_realizados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            servico TEXT,
            data_realizacao TEXT,
            responsavel TEXT,
            observacoes TEXT,
            status TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(servicos_realizados);")
    cols_srv_db = [col[1] for col in cursor.fetchall()]
    colunas_novas_srv = [
        ("empresa", "TEXT"), ("servico", "TEXT"), ("data_realizacao", "TEXT"), 
        ("responsavel", "TEXT"), ("observacoes", "TEXT"), ("status", "TEXT")
    ]
    for col_nova, tipo_col in colunas_novas_srv:
        if col_nova not in cols_srv_db:
            try:
                cursor.execute(f"ALTER TABLE servicos_realizados ADD COLUMN {col_nova} {tipo_col};")
            except:
                pass

    # Tabelas de Apoio
    cursor.execute("CREATE TABLE IF NOT EXISTS cad_cargos (id INTEGER PRIMARY KEY AUTOINCREMENT, cargo TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS cad_treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, treinamento TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS cad_epis (id INTEGER PRIMARY KEY AUTOINCREMENT, epi TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS cad_servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, servico TEXT UNIQUE)")
    
    conn.commit()
    conn.close()

init_db()

def get_empresas():
    conn = sqlite3.connect(DB_NAME)
    empresas_set = set()
    try:
        df1 = pd.read_sql("SELECT DISTINCT nome_empresa FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''", conn)
        for e in df1["nome_empresa"].tolist():
            if str(e).strip():
                empresas_set.add(str(e).strip())
    except:
        pass
    
    conn.close()
    return sorted(list(empresas_set))

def formatar_data_br(data_str):
    if not data_str or pd.isna(data_str):
        return ""
    str_val = str(data_str).strip()
    if " " in str_val:
        str_val = str_val.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(str_val, fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return str_val

def converter_para_iso(data_val):
    if not data_val or pd.isna(data_val):
        return ""
    str_val = str(data_val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str_val, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str_val

# --- CONTROLE DE SESSÃO (LOGIN COM OPÇÃO DE CADASTRO E LGPD) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    try:
        st.image("logo.png", width=140)
    except:
        pass
    
    st.markdown("<h1 style='font-size: 24px;'>Cassilab Consultoria e Treinamentos</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: gray; font-size: 15px;'>Sistema de Gestão Integrada em SST</h3>", unsafe_allow_html=True)
    st.write("")

    aba_login, aba_cadastro = st.tabs(["🔑 Entrar no Sistema", "📝 Cadastrar Novo Usuário por CPF"])

    with aba_login:
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário ou CPF")
            senha_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Acessar Sistema")
            
            if btn_login:
                if usuario_input == "admin" and senha_input == "Disc@5232":
                    st.session_state["autenticado"] = True
                    st.success("Login de Administrador efetuado com sucesso!")
                    st.rerun()
                else:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM usuarios_sistema WHERE (nome = ? OR cpf = ?) AND senha = ?", (usuario_input, usuario_input, senha_input))
                    user_db = cursor.fetchone()
                    conn.close()
                    
                    if user_db:
                        st.session_state["autenticado"] = True
                        st.success(f"Bem-vindo(a), {user_db[1]}!")
                        st.rerun()
                    else:
                        st.error("Usuário/CPF ou senha inválidos.")

    with aba_cadastro:
        st.markdown("Preencha os dados abaixo vinculados ao seu CPF cadastrado na base de funcionários para criar seu acesso:")
        with st.form("form_novo_usuario"):
            cad_nome = st.text_input("Nome Completo")
            cad_cpf = st.text_input("CPF (Somente números)")
            empresas_disponiveis = get_empresas()
            cad_empresa = st.selectbox("Empresa Vinculada", empresas_disponiveis if empresas_disponiveis else ["Nenhuma empresa cadastrada"])
            cad_senha = st.text_input("Crie uma Senha", type="password")
            btn_cad_usuario = st.form_submit_button("Cadastrar Novo Acesso")

            if btn_cad_usuario:
                if cad_nome and cad_cpf and cad_senha:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    try:
                        cursor.execute("INSERT INTO usuarios_sistema (nome, cpf, empresa, senha) VALUES (?, ?, ?, ?)", 
                                       (cad_nome, cad_cpf, cad_empresa, cad_senha))
                        conn.commit()
                        st.success("Cadastro realizado com sucesso! Vá para a aba 'Entrar no Sistema'.")
                    except sqlite3.IntegrityError:
                        st.error("Este CPF já possui cadastro no sistema.")
                    finally:
                        conn.close()
                else:
                    st.error("Preencha todos os campos obrigatórios.")

    st.markdown("---")
    st.markdown("<p style='font-size: 11px; color: gray;'>⚖️ <b>Aviso Legal / LGPD:</b> Os dados coletados neste sistema são estritamente confidenciais e utilizados unicamente para fins de Gestão de Saúde e Segurança do Trabalho (SST), em conformidade com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018).</p>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
try:
    st.sidebar.image("logo.png", width=120)
except:
    st.sidebar.markdown("### Cassilab SST")

# Menu atualizado na ordem solicitada
menu = st.sidebar.selectbox("Menu Principal", [
    "Dashboard / Visão Geral",
    "Cadastro de Empresas",
    "Cadastros Gerais",
    "Gestão de Funcionários", 
    "Treinamentos", 
    "Exames Ocupacionais", 
    "Controle de EPIs", 
    "Serviços Realizados",
    "Administração",
    "Relatórios Consolidados"
])

st.sidebar.markdown("---")

if st.sidebar.button("💾 Salvar tudo e Sair"):
    st.session_state["autenticado"] = False
    st.sidebar.success("✅ Dados salvos e sessão encerrada com segurança!")
    st.rerun()

# ==========================================
# 0. DASHBOARD / VISÃO GERAL
# ==========================================
if menu == "Dashboard / Visão Geral":
    col_t1, col_t2 = st.columns([0.8, 0.2])
    with col_t1:
        st.title("📊 Dashboard - Visão Geral Cassilab SST")
    with col_t2:
        st.write("")
        if st.button("🔄 Atualizar Dados"):
            st.rerun()
    
    conn = sqlite3.connect(DB_NAME)
    try:
        total_empresas = pd.read_sql("SELECT COUNT(DISTINCT nome_empresa) as qtd FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''", conn).iloc[0]["qtd"]
    except:
        total_empresas = 0
        
    try:
        total_funcs = pd.read_sql("SELECT COUNT(*) as qtd FROM base_funcionarios", conn).iloc[0]["qtd"]
    except:
        total_funcs = 0
        
    try:
        df_ex = pd.read_sql("SELECT * FROM exames", conn)
        total_exames = len(df_ex)
        vencidos_ex = len(df_ex[df_ex["status"].str.lower() == "vencido"]) if not df_ex.empty else 0
    except:
        total_exames = 0
        vencidos_ex = 0

    try:
        df_tr = pd.read_sql("SELECT * FROM treinamentos", conn)
        total_tr = len(df_tr)
        vencidos_tr = len(df_tr[df_tr["status"].str.lower() == "vencido"]) if not df_tr.empty else 0
    except:
        total_tr = 0
        vencidos_tr = 0
    
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏢 Empresas Clientes", total_empresas)
    c2.metric("👥 Funcionários Cadastrados", total_funcs)
    c3.metric("🩺 Exames Registrados", total_exames, delta=f"-{vencidos_ex} vencidos" if vencidos_ex > 0 else "Regular")
    c4.metric("📚 Treinamentos Registrados", total_tr, delta=f"-{vencidos_tr} vencidos" if vencidos_tr > 0 else "Regular")

    st.markdown("---")
    st.info("💡 **Dica:** Utilize o menu lateral para navegar entre os cadastros de empresas, funcionários, exames, treinamentos e emissão de backups.")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
    st.title("🏢 Cadastro de Empresas Clientes")

    with st.expander("➕ Adicionar Nova Empresa", expanded=True):
        with st.form("form_empresa"):
            c1, c2, c3 = st.columns(3)
            nome_empresa = c1.text_input("Nome da Empresa *")
            cnpj = c2.text_input("CNPJ")
            cep = c3.text_input("CEP")
            
            c4, c5, c6 = st.columns(3)
            cidade = c4.text_input("Cidade")
            bairro = c5.text_input("Bairro")
            endereco = c6.text_input("Endereço")

            c7, c8, c9 = st.columns(3)
            telefone = c7.text_input("Telefone")
            email = c8.text_input("E-mail")
            responsavel = c9.text_input("Responsável")

            c10, c11 = st.columns(2)
            grau_risco = c10.selectbox("Grau de Risco", ["1", "2", "3", "4"])
            qtd_funcionarios = c11.number_input("Qtd de Funcionários", min_value=0, value=0, step=1)
            
            if st.form_submit_button("Salvar Empresa"):
                if nome_empresa.strip():
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    try:
                        cursor.execute("""
                            INSERT INTO empresas (nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nome_empresa.strip(), cnpj.strip(), cep.strip(), cidade.strip(), bairro.strip(), 
                            endereco.strip(), telefone.strip(), email.strip(), responsavel.strip(), 
                            grau_risco, int(qtd_funcionarios)
                        ))
                        conn.commit()
                        st.success("Empresa cadastrada com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Esta empresa (com esse nome) já está cadastrada.")
                    finally:
                        conn.close()
                else:
                    st.error("O campo 'Nome da Empresa' é obrigatório.")

    st.subheader("Empresas Cadastradas")
    conn = sqlite3.connect(DB_NAME)
    df_emp = pd.read_sql("SELECT id, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, qtd_funcionarios, grau_risco FROM empresas", conn)
    conn.close()

    if not df_emp.empty:
        editado_emp = st.data_editor(df_emp.drop(columns=["id"]), num_rows="dynamic", key="editor_emp")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_emp = st.checkbox("⚠️ Confirmo salvar as alterações nas empresas", key="chk_salvar_emp")
            if st.button("💾 Salvar Alterações"):
                if chk_salvar_emp:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM empresas")
                    for _, row in editado_emp.iterrows():
                        if pd.notna(row["nome_empresa"]) and str(row["nome_empresa"]).strip():
                            try:
                                qtd_func_val = int(row["qtd_funcionarios"]) if pd.notna(row["qtd_funcionarios"]) else 0
                            except:
                                qtd_func_val = 0

                            cursor.execute("""
                                INSERT OR IGNORE INTO empresas (nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                str(row["nome_empresa"]).strip(),
                                str(row["cnpj"]).strip() if pd.notna(row["cnpj"]) else "",
                                str(row["cep"]).strip() if pd.notna(row["cep"]) else "",
                                str(row["cidade"]).strip() if pd.notna(row["cidade"]) else "",
                                str(row["bairro"]).strip() if pd.notna(row["bairro"]) else "",
                                str(row["endereco"]).strip() if pd.notna(row["endereco"]) else "",
                                str(row["telefone"]).strip() if pd.notna(row["telefone"]) else "",
                                str(row["email"]).strip() if pd.notna(row["email"]) else "",
                                str(row["responsavel"]).strip() if pd.notna(row["responsavel"]) else "",
                                str(row["grau_risco"]).strip() if pd.notna(row["grau_risco"]) else "1",
                                qtd_func_val
                            ))
                    conn.commit()
                    conn.close()
                    st.success("Empresas atualizadas com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar as alterações.")

        with col_b2:
            chk_excluir_emp = st.checkbox("⚠️ Confirmo a exclusão/remoção das empresas", key="chk_excluir_emp")
            if st.button("🗑️ Excluir Selecionadas"):
                if chk_excluir_emp:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM empresas")
                    for _, row in editado_emp.iterrows():
                        if pd.notna(row["nome_empresa"]) and str(row["nome_empresa"]).strip():
                            try:
                                qtd_func_val = int(row["qtd_funcionarios"]) if pd.notna(row["qtd_funcionarios"]) else 0
                            except:
                                qtd_func_val = 0

                            cursor.execute("""
                                INSERT OR IGNORE INTO empresas (nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                str(row["nome_empresa"]).strip(),
                                str(row["cnpj"]).strip() if pd.notna(row["cnpj"]) else "",
                                str(row["cep"]).strip() if pd.notna(row["cep"]) else "",
                                str(row["cidade"]).strip() if pd.notna(row["cidade"]) else "",
                                str(row["bairro"]).strip() if pd.notna(row["bairro"]) else "",
                                str(row["endereco"]).strip() if pd.notna(row["endereco"]) else "",
                                str(row["telefone"]).strip() if pd.notna(row["telefone"]) else "",
                                str(row["email"]).strip() if pd.notna(row["email"]) else "",
                                str(row["responsavel"]).strip() if pd.notna(row["responsavel"]) else "",
                                str(row["grau_risco"]).strip() if pd.notna(row["grau_risco"]) else "1",
                                qtd_func_val
                            ))
                    conn.commit()
                    conn.close()
                    st.success("Registros sincronizados/excluídos com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para autorizar a exclusão.")

# ==========================================
# 2. CADASTROS GERAIS
# ==========================================
elif menu == "Cadastros Gerais":
    st.title("⚙️ Gerenciamento de Cadastros")
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Cargos")
        novo_cargo = st.text_input("Novo Cargo")
        if st.button("Adicionar Cargo"):
            if novo_cargo:
                conn = sqlite3.connect(DB_NAME)
                try:
                    conn.execute("INSERT INTO cad_cargos (cargo) VALUES (?)", (novo_cargo,))
                    conn.commit()
                    st.success("Cargo adicionado!")
                except:
                    st.error("Cargo já cadastrado.")
                conn.close()
                st.rerun()

        conn = sqlite3.connect(DB_NAME)
        df_c = pd.read_sql("SELECT * FROM cad_cargos", conn)
        conn.close()
        if not df_c.empty:
            edit_c = st.data_editor(df_c.drop(columns=["id"]), num_rows="dynamic", key="edit_c")
            chk_c = st.checkbox("⚠️ Confirmo salvar/atualizar cargos", key="chk_c")
            if st.button("💾 Salvar Cargos"):
                if chk_c:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM cad_cargos")
                    for _, r in edit_c.iterrows():
                        if pd.notna(r["cargo"]) and str(r["cargo"]).strip():
                            conn.execute("INSERT OR IGNORE INTO cad_cargos (cargo) VALUES (?)", (str(r["cargo"]).strip(),))
                    conn.commit()
                    conn.close()
                    st.success("Cargos atualizados!")
                    st.rerun()
                else:
                    st.warning("Confirme a caixa acima.")

        st.subheader("Serviços")
        novo_serv = st.text_input("Novo Tipo de Serviço")
        if st.button("Adicionar Serviço"):
            if novo_serv:
                conn = sqlite3.connect(DB_NAME)
                try:
                    conn.execute("INSERT INTO cad_servicos (servico) VALUES (?)", (novo_serv,))
                    conn.commit()
                    st.success("Serviço adicionado!")
                except:
                    st.error("Serviço já cadastrado.")
                conn.close()
                st.rerun()

        conn = sqlite3.connect(DB_NAME)
        df_s = pd.read_sql("SELECT * FROM cad_servicos", conn)
        conn.close()
        if not df_s.empty:
            edit_s = st.data_editor(df_s.drop(columns=["id"]), num_rows="dynamic", key="edit_s")
            chk_s = st.checkbox("⚠️ Confirmo salvar/atualizar serviços", key="chk_s")
            if st.button("💾 Salvar Serviços"):
                if chk_s:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM cad_servicos")
                    for _, r in edit_s.iterrows():
                        if pd.notna(r["servico"]) and str(r["servico"]).strip():
                            conn.execute("INSERT OR IGNORE INTO cad_servicos (servico) VALUES (?)", (str(r["servico"]).strip(),))
                    conn.commit()
                    conn.close()
                    st.success("Serviços atualizados!")
                    st.rerun()
                else:
                    st.warning("Confirme a caixa acima.")

    with c2:
        st.subheader("Treinamentos")
        novo_trein = st.text_input("Novo Treinamento")
        if st.button("Adicionar Treinamento"):
            if novo_trein:
                conn = sqlite3.connect(DB_NAME)
                try:
                    conn.execute("INSERT INTO cad_treinamentos (treinamento) VALUES (?)", (novo_trein,))
                    conn.commit()
                    st.success("Treinamento adicionado!")
                except:
                    st.error("Treinamento já cadastrado.")
                conn.close()
                st.rerun()

        conn = sqlite3.connect(DB_NAME)
        df_t = pd.read_sql("SELECT * FROM cad_treinamentos", conn)
        conn.close()
        if not df_t.empty:
            edit_t = st.data_editor(df_t.drop(columns=["id"]), num_rows="dynamic", key="edit_t")
            chk_t = st.checkbox("⚠️ Confirmo salvar/atualizar treinamentos", key="chk_t")
            if st.button("💾 Salvar Treinamentos"):
                if chk_t:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM cad_treinamentos")
                    for _, r in edit_t.iterrows():
                        if pd.notna(r["treinamento"]) and str(r["treinamento"]).strip():
                            conn.execute("INSERT OR IGNORE INTO cad_treinamentos (treinamento) VALUES (?)", (str(r["treinamento"]).strip(),))
                    conn.commit()
                    conn.close()
                    st.success("Treinamentos atualizados!")
                    st.rerun()
                else:
                    st.warning("Confirme a caixa acima.")

        st.subheader("EPIs")
        novo_epi = st.text_input("Novo EPI (Ex: Óculos de Proteção)")
        if st.button("Adicionar EPI"):
            if novo_epi:
                conn = sqlite3.connect(DB_NAME)
                try:
                    conn.execute("INSERT INTO cad_epis (epi) VALUES (?)", (novo_epi,))
                    conn.commit()
                    st.success("EPI adicionado!")
                except:
                    st.error("EPI já cadastrado.")
                conn.close()
                st.rerun()

        conn = sqlite3.connect(DB_NAME)
        df_e = pd.read_sql("SELECT * FROM cad_epis", conn)
        conn.close()
        if not df_e.empty:
            edit_e = st.data_editor(df_e.drop(columns=["id"]), num_rows="dynamic", key="edit_e")
            chk_e = st.checkbox("⚠️ Confirmo salvar/atualizar EPIs", key="chk_e")
            if st.button("💾 Salvar EPIs"):
                if chk_e:
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM cad_epis")
                    for _, r in edit_e.iterrows():
                        if pd.notna(r["epi"]) and str(r["epi"]).strip():
                            conn.execute("INSERT OR IGNORE INTO cad_epis (epi) VALUES (?)", (str(r["epi"]).strip(),))
                    conn.commit()
                    conn.close()
                    st.success("EPIs atualizados!")
                    st.rerun()
                else:
                    st.warning("Confirme a caixa acima.")

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================
elif menu == "Gestão de Funcionários":
    st.title("👥 Cadastro de Funcionários")
    empresas_cadastradas = get_empresas()

    with st.expander("➕ Adicionar Novo Funcionário", expanded=True):
        with st.form("form_func"):
            c1, c2 = st.columns(2)
            
            if empresas_cadastradas:
                empresa = c1.selectbox("Empresa Cliente", options=empresas_cadastradas, index=0)
            else:
                empresa = c1.selectbox("Empresa Cliente", options=["Nenhuma empresa cadastrada"], index=0)
                
            matricula = c1.text_input("Matrícula")
            nome = c1.text_input("Nome do Funcionário")
            cargo = c2.text_input("Cargo")
            setor = c2.text_input("Setor")
            cpf = c1.text_input("CPF")
            data_admissao_input = c2.date_input("Data Admissão", value=datetime.today())
            status_func = c1.selectbox("Status", ["Ativo", "Afastado", "Desligado"])
            
            if st.form_submit_button("Salvar Funcionário"):
                if empresa and empresa != "Nenhuma empresa cadastrada" and nome:
                    data_admissao_br = data_admissao_input.strftime("%d/%m/%Y")
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO empresas (nome_empresa) VALUES (?)", (empresa,))
                    cursor.execute("""
                        INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (matricula, nome, cargo, setor, cpf, data_admissao_br, status_func, empresa))
                    conn.commit()
                    conn.close()
                    st.success("Funcionário e empresa cadastrados com sucesso!")
                    st.rerun()
                else:
                    st.error("Selecione uma Empresa válida e preencha o Nome do Funcionário.")

    st.subheader("Funcionários Cadastrados")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM base_funcionarios", conn)
    conn.close()
    
    if not df.empty:
        if "data_admissao" in df.columns:
            df["data_admissao"] = df["data_admissao"].apply(formatar_data_br)

        colunas_ordenadas = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "cpf", "data_admissao", "status"]
        colunas_existentes = [c for c in colunas_ordenadas if c in df.columns]
        df = df[colunas_existentes]

        editado = st.data_editor(df.drop(columns=["id"]), num_rows="dynamic", key="editor_func")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_func = st.checkbox("⚠️ Confirmo salvar as alterações nos funcionários", key="chk_salvar_func")
            if st.button("💾 Salvar Alterações"):
                if chk_salvar_func:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM base_funcionarios")
                    for _, row in editado.iterrows():
                        dt_iso = converter_para_iso(row["data_admissao"])
                        cursor.execute("""
                            INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["cpf"], dt_iso, row["status"], row["empresa"]))
                        cursor.execute("INSERT OR IGNORE INTO empresas (nome_empresa) VALUES (?)", (row["empresa"],))
                    conn.commit()
                    conn.close()
                    st.success("Alterações salvas com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar as alterações.")

        with col_b2:
            chk_excluir_func = st.checkbox("⚠️ Confirmo a exclusão dos funcionários selecionados", key="chk_excluir_func")
            if st.button("🗑️ Excluir Selecionados"):
                if chk_excluir_func:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM base_funcionarios")
                    for _, row in editado.iterrows():
                        dt_iso = converter_para_iso(row["data_admissao"])
                        cursor.execute("""
                            INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["cpf"], dt_iso, row["status"], row["empresa"]))
                        cursor.execute("INSERT OR IGNORE INTO empresas (nome_empresa) VALUES (?)", (row["empresa"],))
                    conn.commit()
                    conn.close()
                    st.success("Registros sincronizados/excluídos com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para autorizar a exclusão.")

# ==========================================
# 4. TREINAMENTOS
# ==========================================
elif menu == "Treinamentos":
    st.title("📚 Controle de Treinamentos")
    
    with st.expander("➕ Cadastrar Novo Tipo de Treinamento no Sistema"):
        with st.form("form_novo_tipo_treinamento"):
            novo_tipo_trein = st.text_input("Nome do Novo Treinamento (Ex: NR-35 Trabalho em Altura)")
            if st.form_submit_button("Cadastrar Treinamento"):
                if novo_tipo_trein.strip():
                    conn = sqlite3.connect(DB_NAME)
                    try:
                        conn.execute("INSERT INTO cad_treinamentos (treinamento) VALUES (?)", (novo_tipo_trein.strip(),))
                        conn.commit()
                        st.success(f"Treinamento '{novo_tipo_trein.strip()}' cadastrado com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Este treinamento já está cadastrado.")
                    finally:
                        conn.close()
                else:
                    st.error("Digite o nome do treinamento.")

    empresas = get_empresas()
    
    conn = sqlite3.connect(DB_NAME)
    df_cad_trein = pd.read_sql("SELECT treinamento FROM cad_treinamentos", conn)
    conn.close()
    lista_trein_cad = df_cad_trein["treinamento"].tolist() if not df_cad_trein.empty else []

    if not empresas:
        st.warning("Cadastre empresas para começar a gerenciar os treinamentos.")
    else:
        empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_trein")
        
        conn = sqlite3.connect(DB_NAME)
        df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ?", conn, params=(empresa_sel,))
        conn.close()
        
        with st.expander("➕ Inserção de Treinamento para Funcionário (Com Informações Completas)", expanded=True):
            if df_funcs.empty:
                st.warning("Não há funcionários cadastrados para esta empresa. Cadastre funcionários na aba correspondente.")
            else:
                nomes_lista = df_funcs["funcionario"].tolist()
                
                with st.form("form_inserir_treinamento_detalhado"):
                    c1, c2 = st.columns(2)
                    with c1:
                        func_sel = st.selectbox("Funcionário", nomes_lista)
                        
                        colab = df_funcs[df_funcs["funcionario"] == func_sel].iloc[0]
                        matr_val = st.text_input("Matrícula", value=str(colab['matricula']) if pd.notna(colab['matricula']) else "")
                        cargo_val = st.text_input("Cargo", value=str(colab['cargo']) if pd.notna(colab['cargo']) else "")
                        setor_val = st.text_input("Setor", value=str(colab['setor']) if pd.notna(colab['setor']) else "")
                        treinamento_escolhido = st.selectbox("Tipo de Treinamento", lista_trein_cad if lista_trein_cad else ["Nenhum treinamento cadastrado"])

                    with c2:
                        carga_horaria_val = st.text_input("Carga Horária (Ex: 8h, 16h)")
                        data_realizacao_val = st.date_input("Data de Realização", value=datetime.today())
                        validade_meses_val = st.number_input("Validade (Meses)", min_value=1, value=12, step=1)
                        proximo_vencimento_val = st.date_input("Próximo Vencimento", value=datetime.today())
                        status_val = st.selectbox("Status", ["em dia", "Vencido", "A Vencer"])

                    if st.form_submit_button("Salvar Inserção de Treinamento"):
                        if treinamento_escolhido and treinamento_escolhido != "Nenhum treinamento cadastrado":
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                empresa_sel, 
                                matr_val, 
                                func_sel, 
                                cargo_val, 
                                setor_val, 
                                treinamento_escolhido, 
                                carga_horaria_val, 
                                data_realizacao_val.strftime("%d/%m/%Y"), 
                                int(validade_meses_val), 
                                proximo_vencimento_val.strftime("%d/%m/%Y"), 
                                status_val
                            ))
                            conn.commit()
                            conn.close()
                            st.success("Treinamento inserido com sucesso!")
                            st.rerun()
                        else:
                            st.error("Selecione um tipo de treinamento válido (cadastre acima caso não haja nenhum).")

    st.subheader("Treinamentos Registrados")
    conn = sqlite3.connect(DB_NAME)
    df_tr = pd.read_sql("SELECT * FROM treinamentos", conn)
    conn.close()
    if not df_tr.empty:
        colunas_tr_ordem = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "treinamento", "carga_horaria", "data_realizacao", "validade_meses", "proximo_vencimento", "status"]
        colunas_tr_existentes = [c for c in colunas_tr_ordem if c in df_tr.columns]
        df_tr = df_tr[colunas_tr_existentes]
        
        if "data_realizacao" in df_tr.columns:
            df_tr["data_realizacao"] = df_tr["data_realizacao"].apply(formatar_data_br)
        if "proximo_vencimento" in df_tr.columns:
            df_tr["proximo_vencimento"] = df_tr["proximo_vencimento"].apply(formatar_data_br)

        editado_tr = st.data_editor(df_tr.drop(columns=["id"]), num_rows="dynamic", key="editor_tr")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_tr = st.checkbox("⚠️ Confirmo salvar as alterações nos treinamentos", key="chk_salvar_tr")
            if st.button("💾 Salvar Alterações", key="btn_salvar_tr"):
                if chk_salvar_tr:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM treinamentos")
                    for _, row in editado_tr.iterrows():
                        dt_real_iso = converter_para_iso(row["data_realizacao"])
                        dt_venc_iso = converter_para_iso(row["proximo_vencimento"])
                        try:
                            val_meses_int = int(row["validade_meses"])
                        except:
                            val_meses_int = 12

                        cursor.execute("""
                            INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["treinamento"], row["carga_horaria"], dt_real_iso, val_meses_int, dt_venc_iso, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Treinamentos atualizados com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar.")

        with col_b2:
            chk_excluir_tr = st.checkbox("⚠️ Confirmo a exclusão dos treinamentos selecionados", key="chk_excluir_tr")
            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_tr"):
                if chk_excluir_tr:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM treinamentos")
                    for _, row in editado_tr.iterrows():
                        dt_real_iso = converter_para_iso(row["data_realizacao"])
                        dt_venc_iso = converter_para_iso(row["proximo_vencimento"])
                        try:
                            val_meses_int = int(row["validade_meses"])
                        except:
                            val_meses_int = 12

                        cursor.execute("""
                            INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["treinamento"], row["carga_horaria"], dt_real_iso, val_meses_int, dt_venc_iso, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Excluído/atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

# ==========================================
# 5. EXAMES OCUPACIONAIS
# ==========================================
elif menu == "Exames Ocupacionais":
    st.title("🩺 Controle de Exames Ocupacionais e Periódicos")
    empresas = get_empresas()
    
    if not empresas:
        st.warning("Cadastre ao menos uma empresa na aba 'Cadastro de Empresas' ou 'Gestão de Funcionários' primeiro.")
    else:
        empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="ex_emp")
        
        conn = sqlite3.connect(DB_NAME)
        df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ?", conn, params=(empresa_sel,))
        conn.close()
        
        if df_funcs.empty:
            st.warning("Não há funcionários cadastrados para esta empresa ainda.")
        else:
            with st.expander("➕ Adicionar Novo Exame", expanded=True):
                nomes_lista = df_funcs["funcionario"].tolist()
                
                with st.form("form_exame"):
                    nome_sel = st.selectbox("Nome do Funcionário", nomes_lista, key="ex_func")
                    
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    matr_auto = str(colab['matricula']) if pd.notna(colab['matricula']) else ""
                    carg_auto = str(colab['cargo']) if pd.notna(colab['cargo']) else ""
                    setr_auto = str(colab['setor']) if pd.notna(colab['setor']) else ""

                    c1, c2 = st.columns(2)
                    with c1:
                        ultimo = st.date_input("Data do Último Exame", key="dt_ult")
                        tipo_exame = st.selectbox("Tipo de Exame", ["Admissional", "Periódico", "Retorno ao Trabalho", "Demissional"], key="tp_ex")
                    with c2:
                        proximo = st.date_input("Data do Próximo Exame", key="dt_prox")
                        status = st.selectbox("Status", ["Válido", "Vencido", "A Vencer"], key="st_ex")
                        
                    if st.form_submit_button("Salvar Lançamento de Exame"):
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (empresa_sel, matr_auto, nome_sel, carg_auto, setr_auto, ultimo.strftime("%d/%m/%Y"), tipo_exame, proximo.strftime("%d/%m/%Y"), status))
                        conn.commit()
                        conn.close()
                        st.success("Exame salvo com sucesso!")
                        st.rerun()

    st.subheader("Exames Registrados")
    conn = sqlite3.connect(DB_NAME)
    df_ex = pd.read_sql("SELECT * FROM exames", conn)
    conn.close()
    if not df_ex.empty:
        if 'empresa' in df_ex.columns:
            df_ex = df_ex[["id", "empresa", "matricula", "funcionario", "cargo", "setor", "ultimo_exame", "tipo_exame", "proximo_exame", "status"]]
        
        if "ultimo_exame" in df_ex.columns:
            df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br)
        if "proximo_exame" in df_ex.columns:
            df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br)
        
        editado_ex = st.data_editor(df_ex.drop(columns=["id"]), num_rows="dynamic", key="editor_ex")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_ex = st.checkbox("⚠️ Confirmo salvar as alterações nos exames", key="chk_salvar_ex")
            if st.button("💾 Salvar Alterações", key="btn_salvar_ex"):
                if chk_salvar_ex:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM exames")
                    for _, row in editado_ex.iterrows():
                        dt_ult_iso = converter_para_iso(row["ultimo_exame"])
                        dt_prox_iso = converter_para_iso(row["proximo_exame"])
                        cursor.execute("""
                            INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], dt_ult_iso, row["tipo_exame"], dt_prox_iso, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Exames atualizados com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar.")

        with col_b2:
            chk_excluir_ex = st.checkbox("⚠️ Confirmo a exclusão dos exames selecionados", key="chk_excluir_ex")
            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_ex"):
                if chk_excluir_ex:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM exames")
                    for _, row in editado_ex.iterrows():
                        dt_ult_iso = converter_para_iso(row["ultimo_exame"])
                        dt_prox_iso = converter_para_iso(row["proximo_exame"])
                        cursor.execute("""
                            INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], dt_ult_iso, row["tipo_exame"], dt_prox_iso, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Excluído/atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

# ==========================================
# 6. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
    st.title("🦺 Controle de Equipamentos de Proteção Individual (EPI)")
    
    with st.expander("➕ Cadastrar Novo Tipo de EPI no Sistema"):
        with st.form("form_novo_tipo_epi"):
            novo_tipo_epi = st.text_input("Nome do Novo EPI (Ex: Protetor Auricular)")
            if st.form_submit_button("Cadastrar EPI"):
                if novo_tipo_epi.strip():
                    conn = sqlite3.connect(DB_NAME)
                    try:
                        conn.execute("INSERT INTO cad_epis (epi) VALUES (?)", (novo_tipo_epi.strip(),))
                        conn.commit()
                        st.success(f"EPI '{novo_tipo_epi.strip()}' cadastrado com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Este EPI já está cadastrado.")
                    finally:
                        conn.close()
                else:
                    st.error("Digite o nome do EPI.")

    empresas = get_empresas()
    
    conn = sqlite3.connect(DB_NAME)
    df_cad_epis = pd.read_sql("SELECT epi FROM cad_epis", conn)
    conn.close()
    lista_epis_cad = df_cad_epis["epi"].tolist() if not df_cad_epis.empty else []

    if not empresas:
        st.warning("Cadastre empresas para começar a gerenciar os EPIs.")
    else:
        empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_epi")
        
        conn = sqlite3.connect(DB_NAME)
        df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ?", conn, params=(empresa_sel,))
        conn.close()
        
        with st.expander("➕ Registrar Entrega de EPI (Com Informações Completas)", expanded=True):
            if df_funcs.empty:
                st.warning("Não há funcionários cadastrados para esta empresa.")
            elif not lista_epis_cad:
                st.warning("Não há EPIs cadastrados. Adicione um tipo de EPI acima ou na aba 'Cadastros Gerais'.")
            else:
                nomes_lista = df_funcs["funcionario"].tolist()
                
                with st.form("form_epi"):
                    c1, c2 = st.columns(2)
                    with c1:
                        nome_sel = st.selectbox("Nome do Funcionário", nomes_lista, key="func_epi")
                        
                        colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                        matr_auto = st.text_input("Matrícula", value=str(colab['matricula']) if pd.notna(colab['matricula']) else "")
                        carg_auto = st.text_input("Cargo", value=str(colab['cargo']) if pd.notna(colab['cargo']) else "")
                        setr_auto = st.text_input("Setor", value=str(colab['setor']) if pd.notna(colab['setor']) else "")
                        epi_sel = st.selectbox("Equipamento (EPI)", lista_epis_cad)

                    with c2:
                        ca_epi = st.text_input("Número do CA (Certificado de Aprovação)")
                        data_entrega = st.date_input("Data da Entrega", value=datetime.today(), key="dt_ent_epi")
                        qtd = st.number_input("Quantidade", min_value=1, value=1, key="qtd_epi")
                        status_epi = st.selectbox("Status de Entrega", ["Entregue", "Devolvido", "Substituído"], key="st_epi")
                        
                    if st.form_submit_button("Salvar Registro de EPI"):
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (empresa_sel, matr_auto, nome_sel, carg_auto, setr_auto, epi_sel, ca_epi, data_entrega.strftime("%d/%m/%Y"), int(qtd), status_epi))
                        conn.commit()
                        conn.close()
                        st.success("EPI registrado com sucesso!")
                        st.rerun()

    st.subheader("EPIs Registrados")
    conn = sqlite3.connect(DB_NAME)
    df_ep = pd.read_sql("SELECT * FROM epis", conn)
    conn.close()
    if not df_ep.empty:
        colunas_ep_ordem = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]
        colunas_ep_existentes = [c for c in colunas_ep_ordem if c in df_ep.columns]
        df_ep = df_ep[colunas_ep_existentes]
        
        if "data_entrega" in df_ep.columns:
            df_ep["data_entrega"] = df_ep["data_entrega"].apply(formatar_data_br)

        editado_ep = st.data_editor(df_ep.drop(columns=["id"]), num_rows="dynamic", key="editor_ep")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_ep = st.checkbox("⚠️ Confirmo salvar as alterações nos EPIs", key="chk_salvar_ep")
            if st.button("💾 Salvar Alterações", key="btn_salvar_ep"):
                if chk_salvar_ep:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM epis")
                    for _, row in editado_ep.iterrows():
                        dt_ent_iso = converter_para_iso(row["data_entrega"])
                        try:
                            qtd_int = int(row["quantidade"])
                        except:
                            qtd_int = 1

                        cursor.execute("""
                            INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["epi"], row["ca"], dt_ent_iso, qtd_int, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("EPIs atualizados com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar.")

        with col_b2:
            chk_excluir_ep = st.checkbox("⚠️ Confirmo a exclusão dos EPIs selecionados", key="chk_excluir_ep")
            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_ep"):
                if chk_excluir_ep:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM epis")
                    for _, row in editado_ep.iterrows():
                        dt_ent_iso = converter_para_iso(row["data_entrega"])
                        try:
                            qtd_int = int(row["quantidade"])
                        except:
                            qtd_int = 1

                        cursor.execute("""
                            INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["epi"], row["ca"], dt_ent_iso, qtd_int, row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Excluído/atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

# ==========================================
# 7. SERVIÇOS REALIZADOS
# ==========================================
elif menu == "Serviços Realizados":
    st.title("🛠️ Controle de Serviços Realizados")
    
    with st.expander("➕ Cadastrar Novo Tipo de Serviço no Sistema"):
        with st.form("form_novo_tipo_servico"):
            novo_tipo_serv = st.text_input("Nome do Novo Serviço (Ex: Elaboração de PGR, Vistoria Técnica, Palestra)")
            if st.form_submit_button("Cadastrar Serviço"):
                if novo_tipo_serv.strip():
                    conn = sqlite3.connect(DB_NAME)
                    try:
                        conn.execute("INSERT INTO cad_servicos (servico) VALUES (?)", (novo_tipo_serv.strip(),))
                        conn.commit()
                        st.success(f"Serviço '{novo_tipo_serv.strip()}' cadastrado com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Este serviço já está cadastrado.")
                    finally:
                        conn.close()
                else:
                    st.error("Digite o nome do serviço.")

    empresas = get_empresas()
    
    conn = sqlite3.connect(DB_NAME)
    df_cad_serv = pd.read_sql("SELECT servico FROM cad_servicos", conn)
    conn.close()
    lista_serv_cad = df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []

    if not empresas:
        st.warning("Cadastre empresas para registrar serviços.")
    else:
        with st.expander("➕ Registrar Novo Serviço Realizado (Com Informações Completas)", expanded=True):
            if not lista_serv_cad:
                st.warning("Não há tipos de serviços cadastrados. Adicione um tipo acima ou na aba 'Cadastros Gerais'.")
            else:
                with st.form("form_servico_completo"):
                    c1, c2 = st.columns(2)
                    with c1:
                        empresa_sel_srv = st.selectbox("Empresa Cliente", empresas, key="emp_srv_sel")
                        servico_sel = st.selectbox("Tipo de Serviço", lista_serv_cad)
                        data_realizacao_srv = st.date_input("Data de Realização", value=datetime.today())
                    with c2:
                        responsavel_srv = st.text_input("Responsável Técnico / Instrutor", value="Luiz Marcelo Fontana")
                        status_srv = st.selectbox("Status", ["Concluído", "Em Andamento", "Agendado", "Cancelado"])
                        observacoes_srv = st.text_input("Observações / Detalhes do Serviço")
                        
                    if st.form_submit_button("Salvar Registro de Serviço"):
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                            VALUES (?,?,?,?,?,?)
                        """, (
                            empresa_sel_srv, 
                            servico_sel, 
                            data_realizacao_srv.strftime("%d/%m/%Y"), 
                            responsavel_srv, 
                            observacoes_srv, 
                            status_srv
                        ))
                        conn.commit()
                        conn.close()
                        st.success("Serviço registrado com sucesso!")
                        st.rerun()

    st.subheader("Serviços Registrados")
    conn = sqlite3.connect(DB_NAME)
    df_serv = pd.read_sql("SELECT * FROM servicos_realizados", conn)
    conn.close()
    if not df_serv.empty:
        colunas_serv_ordem = ["id", "empresa", "servico", "data_realizacao", "responsavel", "observacoes", "status"]
        colunas_serv_existentes = [c for c in colunas_serv_ordem if c in df_serv.columns]
        df_serv = df_serv[colunas_serv_existentes]
        
        if "data_realizacao" in df_serv.columns:
            df_serv["data_realizacao"] = df_serv["data_realizacao"].apply(formatar_data_br)

        editado_serv = st.data_editor(df_serv.drop(columns=["id"]), num_rows="dynamic", key="editor_serv")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            chk_salvar_serv = st.checkbox("⚠️ Confirmo salvar as alterações nos serviços", key="chk_salvar_serv")
            if st.button("💾 Salvar Alterações", key="btn_salvar_serv"):
                if chk_salvar_serv:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM servicos_realizados")
                    for _, row in editado_serv.iterrows():
                        dt_iso = converter_para_iso(row["data_realizacao"])
                        cursor.execute("""
                            INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                            VALUES (?,?,?,?,?,?)
                        """, (row["empresa"], row["servico"], dt_iso, row["responsavel"], row["observacoes"], row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Serviços atualizados com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para salvar.")

        with col_b2:
            chk_excluir_serv = st.checkbox("⚠️ Confirmo a exclusão dos serviços selecionados", key="chk_excluir_serv")
            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_serv"):
                if chk_excluir_serv:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM servicos_realizados")
                    for _, row in editado_serv.iterrows():
                        dt_iso = converter_para_iso(row["data_realizacao"])
                        cursor.execute("""
                            INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                            VALUES (?,?,?,?,?,?)
                        """, (row["empresa"], row["servico"], dt_iso, row["responsavel"], row["observacoes"], row["status"]))
                    conn.commit()
                    conn.close()
                    st.success("Excluído/atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação para excluir.")

# ==========================================
# 8. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    st.title("🛠️ Painel Administrativo e Backup")
    st.markdown("Baixe o arquivo do banco de dados para segurança do seu negócio:")
    with open(DB_NAME, "rb") as f:
        st.download_button("📥 Baixar Backup (.db)", f, file_name="cassilab_gestao.db", mime="application/octet-stream")

    st.markdown("---")
    st.subheader("⚠️ Zona de Manutenção / Limpeza")
    st.markdown("Caso queira limpar completamente linhas em branco ou órfãs que possam estar travando o contador, utilize o botão abaixo:")
    
    chk_limpeza = st.checkbox("Confirmo que deseja remover registros vazios ou duplicados")
    if st.button("🧹 Executar Limpeza de Registros Vazios"):
        if chk_limpeza:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM empresas WHERE nome_empresa IS NULL OR TRIM(nome_empresa) = ''")
            conn.commit()
            conn.close()
            st.success("Limpeza concluída com sucesso! Retorne ao Dashboard para verificar.")
            st.rerun()
        else:
            st.warning("Marque a caixa de confirmação para prosseguir.")

# ==========================================
# 9. RELATÓRIOS CONSOLIDADOS
# ==========================================
elif menu == "Relatórios Consolidados":
    st.title("📑 Relatórios Consolidados e Personalizados")
    st.markdown("Selecione abaixo quais módulos/abas você deseja incluir no relatório consolidado:")

    c1, c2, c3, c4, c5 = st.columns(5)
    inc_func = c1.checkbox("👥 Funcionários", value=True)
    inc_ex = c2.checkbox("🩺 Exames", value=True)
    inc_tr = c3.checkbox("📚 Treinamentos", value=True)
    inc_ep = c4.checkbox("🦺 EPIs", value=True)
    inc_srv = c5.checkbox("🛠️ Serviços", value=True)

    empresas = get_empresas()
    empresa_filtro = st.selectbox("Filtrar por Empresa Específica (Opcional)", ["Todas as Empresas"] + empresas)

    conn = sqlite3.connect(DB_NAME)

    if inc_func:
        st.subheader("👥 Relatório de Funcionários")
        try:
            if empresa_filtro == "Todas as Empresas":
                df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, status FROM base_funcionarios", conn)
            else:
                df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, status FROM base_funcionarios WHERE empresa = ?", conn, params=(empresa_filtro,))
            st.dataframe(df_f, use_container_width=True)
        except:
            st.info("Nenhum dado de funcionários encontrado.")

    if inc_ex:
        st.subheader("🩺 Relatório de Exames Ocupacionais")
        try:
            if empresa_filtro == "Todas as Empresas":
                df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames", conn)
            else:
                df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames WHERE empresa = ?", conn, params=(empresa_filtro,))
            if not df_e.empty and "ultimo_exame" in df_e.columns:
                df_e["ultimo_exame"] = df_e["ultimo_exame"].apply(formatar_data_br)
                df_e["proximo_exame"] = df_e["proximo_exame"].apply(formatar_data_br)
            st.dataframe(df_e, use_container_width=True)
        except:
            st.info("Nenhum dado de exames encontrado.")

    if inc_tr:
        st.subheader("📚 Relatório de Treinamentos")
        try:
            if empresa_filtro == "Todas as Empresas":
                df_t = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, proximo_vencimento, status FROM treinamentos", conn)
            else:
                df_t = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, proximo_vencimento, status FROM treinamentos WHERE empresa = ?", conn, params=(empresa_filtro,))
            if not df_t.empty:
                if "data_realizacao" in df_t.columns:
                    df_t["data_realizacao"] = df_t["data_realizacao"].apply(formatar_data_br)
                if "proximo_vencimento" in df_t.columns:
                    df_t["proximo_vencimento"] = df_t["proximo_vencimento"].apply(formatar_data_br)
            st.dataframe(df_t, use_container_width=True)
        except:
            st.info("Nenhum dado de treinamentos encontrado.")

    if inc_ep:
        st.subheader("🦺 Relatório de Entrega de EPIs")
        try:
            if empresa_filtro == "Todas as Empresas":
                df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis", conn)
            else:
                df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis WHERE empresa = ?", conn, params=(empresa_filtro,))
            if not df_p.empty and "data_entrega" in df_p.columns:
                df_p["data_entrega"] = df_p["data_entrega"].apply(formatar_data_br)
            st.dataframe(df_p, use_container_width=True)
        except:
            st.info("Nenhum dado de EPIs encontrado.")

    if inc_srv:
        st.subheader("🛠️ Relatório de Serviços Realizados")
        try:
            if empresa_filtro == "Todas as Empresas":
                df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, status FROM servicos_realizados", conn)
            else:
                df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, status FROM servicos_realizados WHERE empresa = ?", conn, params=(empresa_filtro,))
            if not df_s.empty and "data_realizacao" in df_s.columns:
                df_s["data_realizacao"] = df_s["data_realizacao"].apply(formatar_data_br)
            st.dataframe(df_s, use_container_width=True)
        except:
            st.info("Nenhum dado de serviços encontrado.")

    conn.close()