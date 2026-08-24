import sqlite3
from datetime import datetime
import re
import pandas as pd
import streamlit as st
import requests

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
            data_registro TEXT,
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
    
    cursor.execute("PRAGMA table_info(empresas);")
    cols_emp_db = [col[1] for col in cursor.fetchall()]
    if "data_registro" not in cols_emp_db:
        try:
            cursor.execute("ALTER TABLE empresas ADD COLUMN data_registro TEXT;")
        except:
            pass
            
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    cursor.execute("UPDATE empresas SET data_registro = ? WHERE data_registro IS NULL OR data_registro = '' OR data_registro = 'nan'", (data_hoje,))
    
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
            email TEXT,
            celular TEXT,
            senha TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(usuarios_sistema);")
    cols_user_db = [col[1] for col in cursor.fetchall()]
    for col_nova, tipo_col in [("email", "TEXT"), ("celular", "TEXT")]:
        if col_nova not in cols_user_db:
            try:
                cursor.execute(f"ALTER TABLE usuarios_sistema ADD COLUMN {col_nova} {tipo_col};")
            except:
                pass

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

    # Tabelas de Apoio
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_cargos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            cargo TEXT,
            UNIQUE(empresa, cargo)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_epis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            epi TEXT,
            ca TEXT,
            UNIQUE(empresa, epi)
        )
    """)
    
    cursor.execute("PRAGMA table_info(cad_cargos);")
    if "empresa" not in [col[1] for col in cursor.fetchall()]:
        try: cursor.execute("ALTER TABLE cad_cargos ADD COLUMN empresa TEXT;")
        except: pass

    cursor.execute("PRAGMA table_info(cad_epis);")
    cols_cad_epis = [col[1] for col in cursor.fetchall()]
    if "empresa" not in cols_cad_epis:
        try: cursor.execute("ALTER TABLE cad_epis ADD COLUMN empresa TEXT;")
        except: pass
    if "ca" not in cols_cad_epis:
        try: cursor.execute("ALTER TABLE cad_epis ADD COLUMN ca TEXT;")
        except: pass

    cursor.execute("CREATE TABLE IF NOT EXISTS cad_treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, treinamento TEXT UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS cad_servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, servico TEXT UNIQUE)")
    
    conn.commit()
    conn.close()

init_db()

def formatar_titulo(texto):
    if not texto or pd.isna(texto):
        return ""
    excecoes = {"e", "da", "de", "do", "das", "dos", "em", "para", "com", "ltda", "S.A."}
    palavras = str(texto).strip().split()
    palavras_formatadas = []
    for i, p in enumerate(palavras):
        p_lower = p.lower()
        if i > 0 and p_lower in excecoes:
            palavras_formatadas.append(p_lower)
        else:
            palavras_formatadas.append(p.capitalize())
    return " ".join(palavras_formatadas)

def formatar_colunas_tabela(df):
    if df is None or df.empty:
        return df
    rename_dict = {
        "data_registro": "Data Registro",
        "nome_empresa": "Nome Empresa",
        "cnpj": "CNPJ",
        "cep": "CEP",
        "cidade": "Cidade",
        "bairro": "Bairro",
        "endereco": "Endereço",
        "telefone": "Telefone",
        "email": "E-mail",
        "responsavel": "Responsável",
        "qtd_funcionarios": "Qtd Funcionários",
        "grau_risco": "Grau Risco",
        "matricula": "Matrícula",
        "funcionario": "Funcionário",
        "cargo": "Cargo",
        "setor": "Setor",
        "cpf": "CPF",
        "data_admissao": "Data Admissão",
        "status": "Status",
        "empresa": "Empresa",
        "treinamento": "Treinamento",
        "carga_horaria": "Carga Horária",
        "data_realizacao": "Data Realização",
        "validade_meses": "Validade (Meses)",
        "proximo_vencimento": "Próximo Vencimento",
        "ultimo_exame": "Último Exame",
        "tipo_exame": "Tipo Exame",
        "proximo_exame": "Próximo Exame",
        "epi": "EPI",
        "ca": "CA",
        "data_entrega": "Data Entrega",
        "quantidade": "Quantidade",
        "servico": "Serviço",
        "observacoes": "Observações"
    }
    return df.rename(columns=rename_dict)

def get_empresas():
    conn = sqlite3.connect(DB_NAME)
    empresas_set = set()
    try:
        df1 = pd.read_sql("SELECT DISTINCT nome_empresa FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != '' ORDER BY nome_empresa ASC", conn)
        for e in df1["nome_empresa"].tolist():
            if str(e).strip():
                empresas_set.add(formatar_titulo(str(e).strip()))
    except:
        pass
    conn.close()
    return sorted(list(empresas_set))

def formatar_cpf(val):
    if not val or pd.isna(val):
        return ""
    numeros = re.sub(r"\D", "", str(val))
    if len(numeros) == 11:
        return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"
    return str(val).strip()

def formatar_cnpj(val):
    if not val or pd.isna(val):
        return ""
    numeros = re.sub(r"\D", "", str(val))
    if len(numeros) == 14:
        return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
    return str(val).strip()

def consultar_cep(cep_str):
    cep_limpo = re.sub(r"\D", "", str(cep_str))
    if len(cep_limpo) == 8:
        try:
            url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                dados = response.json()
                if "erro" not in dados:
                    return {
                        "logradouro": formatar_titulo(dados.get("logradouro", "")),
                        "bairro": formatar_titulo(dados.get("bairro", "")),
                        "cidade": f"{formatar_titulo(dados.get('localidade', ''))} - {dados.get('uf', '').upper()}" if dados.get('uf') else formatar_titulo(dados.get('localidade', ''))
                    }
        except:
            pass
    return None

def validar_e_formatar_data_input(data_str):
    if not data_str or pd.isna(data_str) or str(data_str).strip() in ("", "nan", "None"):
        return datetime.today().strftime("%d/%m/%Y")
    str_val = str(data_str).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str_val, fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return str_val

def formatar_data_br(data_str):
    return validar_e_formatar_data_input(data_str)

def formatar_status_visual(val, tipo):
    if pd.isna(val) or not str(val).strip():
        if tipo == "func": return "🟢 Ativo"
        elif tipo == "trein": return "🟢 em dia"
        elif tipo == "ex": return "🟢 Válido"
        elif tipo == "epi": return "🟢 Entregue"
        else: return "🟢 Concluído"
            
    v = str(val).strip()
    if "🟢" in v or "🔴" in v or "🟠" in v or "🟡" in v:
        return v
        
    v_low = v.lower()
    if tipo == "func":
        if "afastado" in v_low: return f"🟠 {v}"
        if "desligado" in v_low: return f"🔴 {v}"
        return f"🟢 {v}"
    elif tipo == "trein" or tipo == "ex":
        if "vencido" in v_low: return f"🔴 {v}"
        if "a vencer" in v_low or "vencer" in v_low: return f"🟠 {v}"
        return f"🟢 {v}"
    elif tipo == "epi":
        if "devolvido" in v_low: return f"🟠 {v}"
        if "substituído" in v_low or "substituido" in v_low: return f"🟡 {v}"
        return f"🟢 {v}"
    else:
        if "andamento" in v_low: return f"🟠 {v}"
        if "agendado" in v_low: return f"🟡 {v}"
        if "cancelado" in v_low: return f"🔴 {v}"
        return f"🟢 {v}"

def limpar_status_banco(val):
    if pd.isna(val):
        return "Ativo"
    return str(val).replace("🟢", "").replace("🔴", "").replace("🟠", "").replace("🟡", "").strip()

# --- CONTROLE DE SESSÃO COM TELA DE LOGIN CENTRALIZADA ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False
if "empresa_usuario" not in st.session_state: st.session_state["empresa_usuario"] = ""

if not st.session_state["autenticado"]:
    col_esq, col_centro, col_dir = st.columns([1, 1.4, 1])
    
    with col_centro:
        st.write("")
        st.write("")
        try: 
            st.image("logo.png", width=140)
        except: 
            pass
        
        st.markdown("<h1 style='font-size: 22px; margin-bottom: 0px;'>Cassilab Consultoria e Treinamentos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: gray; font-size: 14px; margin-top: 0px;'>Sistema de Gestão Integrada em SST</p>", unsafe_allow_html=True)
        st.write("")

        aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔑 Entrar", "📝 Cadastrar", "🔄 Recuperar"])

        with aba_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário ou CPF", value="", autocomplete="off")
                senha_input = st.text_input("Senha", value="", type="password", autocomplete="new-password")
                btn_login = st.form_submit_button("Acessar Sistema", use_container_width=True)
                
                if btn_login:
                    if usuario_input == "admin" and senha_input == "Disc@5232":
                        st.session_state["autenticado"] = True
                        st.session_state["is_admin"] = True
                        st.session_state["empresa_usuario"] = "Todas"
                        st.success("Login efetuado com sucesso!")
                        st.rerun()
                    else:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM usuarios_sistema WHERE (nome = ? OR cpf = ?) AND senha = ?", (usuario_input, usuario_input, senha_input))
                        user_db = cursor.fetchone()
                        conn.close()
                        
                        if user_db:
                            st.session_state["autenticado"] = True
                            st.session_state["is_admin"] = False
                            st.session_state["empresa_usuario"] = user_db[3]
                            st.success(f"Bem-vindo(a), {user_db[1]}!")
                            st.rerun()
                        else:
                            st.error("Usuário/CPF ou senha inválidos.")

        with aba_cadastro:
            with st.form("form_novo_usuario"):
                cad_nome = st.text_input("Nome Completo", value="", autocomplete="off")
                cad_cpf = st.text_input("CPF", value="", autocomplete="off")
                cad_email = st.text_input("E-mail", value="", autocomplete="off")
                cad_celular = st.text_input("Celular / WhatsApp", value="", autocomplete="off")
                cad_empresa_busca = st.text_input("Nome da Empresa", value="", autocomplete="off")
                cad_senha = st.text_input("Crie uma Senha", value="", type="password", autocomplete="new-password")
                btn_cad_usuario = st.form_submit_button("Cadastrar Acesso", use_container_width=True)

                if btn_cad_usuario:
                    if cad_nome and cad_cpf and cad_email and cad_celular and cad_empresa_busca and cad_senha:
                        cpf_formatado = formatar_cpf(cad_cpf)
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT nome_empresa FROM empresas WHERE nome_empresa LIKE ? LIMIT 1", (f"%{cad_empresa_busca.strip()}%",))
                        emp_encontrada = cursor.fetchone()
                        
                        if emp_encontrada:
                            empresa_final = emp_encontrada[0]
                            try:
                                cursor.execute("INSERT INTO usuarios_sistema (nome, cpf, empresa, email, celular, senha) VALUES (?, ?, ?, ?, ?, ?)", 
                                               (formatar_titulo(cad_nome), cpf_formatado, empresa_final, cad_email.strip(), cad_celular.strip(), cad_senha))
                                conn.commit()
                                st.success(f"Cadastro realizado com sucesso!")
                            except sqlite3.IntegrityError:
                                st.error("Este CPF já possui cadastro.")
                        else:
                            st.error("Nenhuma empresa encontrada com esse nome.")
                        conn.close()
                    else:
                        st.error("Preencha todos os campos.")

        with aba_recuperar:
            with st.form("form_recuperar"):
                rec_cpf = st.text_input("Digite seu CPF cadastrado", value="", autocomplete="off")
                rec_opcao = st.radio("Recuperar via:", ["E-mail cadastrado", "Celular / WhatsApp cadastrado"])
                btn_rec_enviar = st.form_submit_button("Localizar Cadastro", use_container_width=True)
                if btn_rec_enviar:
                    if rec_cpf.strip():
                        cpf_formatado = formatar_cpf(rec_cpf)
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT nome, email, celular FROM usuarios_sistema WHERE cpf = ?", (cpf_formatado,))
                        res_user = cursor.fetchone()
                        conn.close()
                        if res_user:
                            st.success(f"Cadastro localizado para **{res_user[0]}**!")
                        else:
                            st.error("CPF não encontrado.")
                    else:
                        st.error("Digite o CPF.")

    st.stop()

# --- SIDEBAR ---
try: st.sidebar.image("logo.png", width=120)
except: st.sidebar.markdown("### Cassilab SST")

if not st.session_state["is_admin"]:
    st.sidebar.info(f"👤 **Perfil:** Colaborador\n🏢 **Empresa:** {st.session_state['empresa_usuario']}")

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
    st.session_state["is_admin"] = False
    st.session_state["empresa_usuario"] = ""
    st.sidebar.success("✅ Sessão encerrada com segurança!")
    st.rerun()

is_admin = st.session_state["is_admin"]
emp_usuario = st.session_state["empresa_usuario"]

# ==========================================
# 0. DASHBOARD
# ==========================================
if menu == "Dashboard / Visão Geral":
    col_t1, col_t2 = st.columns([0.8, 0.2])
    with col_t1: st.title("📊 Dashboard - Visão Geral Cassilab SST")
    with col_t2:
        st.write("")
        if st.button("🔄 Atualizar Dados"): st.rerun()
    
    conn = sqlite3.connect(DB_NAME)
    try:
        total_empresas = pd.read_sql("SELECT COUNT(DISTINCT nome_empresa) as qtd FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''", conn).iloc[0]["qtd"] if is_admin else (1 if emp_usuario else 0)
        total_funcs = pd.read_sql("SELECT COUNT(*) as qtd FROM base_funcionarios" + ("" if is_admin else " WHERE empresa = ?"), conn, params=None if is_admin else (emp_usuario,)).iloc[0]["qtd"]
        df_ex = pd.read_sql("SELECT * FROM exames" + ("" if is_admin else " WHERE empresa = ?"), conn, params=None if is_admin else (emp_usuario,))
        df_tr = pd.read_sql("SELECT * FROM treinamentos" + ("" if is_admin else " WHERE empresa = ?"), conn, params=None if is_admin else (emp_usuario,))
    except:
        total_empresas, total_funcs = 0, 0
        df_ex, df_tr = pd.DataFrame(), pd.DataFrame()
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏢 Empresas Clientes", total_empresas)
    c2.metric("👥 Funcionários Cadastrados", total_funcs)
    c3.metric("🩺 Exames Registrados", len(df_ex))
    c4.metric("📚 Treinamentos Registrados", len(df_tr))
    st.markdown("---")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
    st.title("🏢 Cadastro de Empresas Clientes")

    if is_admin:
        with st.expander("➕ Adicionar Nova Empresa", expanded=False):
            if "form_cep" not in st.session_state: st.session_state["form_cep"] = ""
            if "form_end" not in st.session_state: st.session_state["form_end"] = ""
            if "form_bair" not in st.session_state: st.session_state["form_bair"] = ""
            if "form_cid" not in st.session_state: st.session_state["form_cid"] = ""

            with st.form("form_empresa"):
                c1, c2, c3 = st.columns(3)
                nome_empresa = c1.text_input("Nome da Empresa *")
                cnpj = c2.text_input("CNPJ (Somente números ou pontuado)")
                cep_input = c3.text_input("CEP", value=st.session_state["form_cep"])
                
                c4, c5, c6 = st.columns(3)
                endereco_input = c4.text_input("Endereço", value=st.session_state["form_end"])
                bairro_input = c5.text_input("Bairro", value=st.session_state["form_bair"])
                cidade_input = c6.text_input("Cidade / UF", value=st.session_state["form_cid"])

                c7, c8, c9 = st.columns(3)
                telefone = c7.text_input("Telefone")
                email = c8.text_input("E-mail")
                responsavel = c9.text_input("Responsável")

                c10, c11 = st.columns(2)
                grau_risco = c10.selectbox("Grau de Risco", ["1", "2", "3", "4"])
                qtd_funcionarios = c11.number_input("Qtd de Funcionários", min_value=0, value=0, step=1)
                
                btn_buscar_cep = st.form_submit_button("🔍 Consultar CEP")
                btn_salvar_empresa = st.form_submit_button("💾 Salvar Empresa")

                if btn_buscar_cep:
                    if cep_input.strip():
                        res_cep = consultar_cep(cep_input)
                        if res_cep:
                            st.session_state["form_cep"] = cep_input
                            st.session_state["form_end"] = res_cep["logradouro"]
                            st.session_state["form_bair"] = res_cep["bairro"]
                            st.session_state["form_cid"] = res_cep["cidade"]
                            st.success("CEP encontrado!")
                            st.rerun()
                        else:
                            st.error("CEP não encontrado.")

                if btn_salvar_empresa:
                    if nome_empresa.strip():
                        nome_fmt = formatar_titulo(nome_empresa)
                        cnpj_formatado = formatar_cnpj(cnpj)
                        data_registro_atual = datetime.now().strftime("%d/%m/%Y")
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                INSERT INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                data_registro_atual, nome_fmt, cnpj_formatado, cep_input.strip(), 
                                formatar_titulo(cidade_input), formatar_titulo(bairro_input), 
                                formatar_titulo(endereco_input), telefone.strip(), email.strip(), 
                                formatar_titulo(responsavel), grau_risco, int(qtd_funcionarios)
                            ))
                            conn.commit()
                            st.session_state["form_cep"] = ""
                            st.session_state["form_end"] = ""
                            st.session_state["form_bair"] = ""
                            st.session_state["form_cid"] = ""
                            st.success("Empresa cadastrada com sucesso!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esta empresa já está cadastrada.")
                        finally:
                            conn.close()
                    else:
                        st.error("O campo 'Nome da Empresa' é obrigatório.")

    st.subheader("Empresas Cadastradas")
    conn = sqlite3.connect(DB_NAME)
    df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, qtd_funcionarios, grau_risco FROM empresas " + ("" if is_admin else "WHERE nome_empresa = ? ") + "ORDER BY nome_empresa ASC", conn, params=None if is_admin else (emp_usuario,))
    conn.close()

    if not df_emp.empty:
        if "data_registro" in df_emp.columns: df_emp["data_registro"] = df_emp["data_registro"].apply(formatar_data_br)
        if "cnpj" in df_emp.columns: df_emp["cnpj"] = df_emp["cnpj"].apply(formatar_cnpj)

        if is_admin:
            df_emp_exibicao = formatar_colunas_tabela(df_emp.drop(columns=["id"]))
            editado_emp = st.data_editor(df_emp_exibicao, num_rows="dynamic", key="editor_emp", use_container_width=True)
            chk_salvar_emp = st.checkbox("⚠️ Confirmo salvar as alterações feitas na tabela de empresas", key="chk_salvar_emp")
            if st.button("💾 Salvar Alterações"):
                if chk_salvar_emp:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM empresas")
                    for _, row in editado_emp.iterrows():
                        nome_emp_val = row.get("Nome Empresa", row.get("nome_empresa", ""))
                        if pd.notna(nome_emp_val) and str(nome_emp_val).strip():
                            try: qtd_func_val = int(row.get("Qtd Funcionários", row.get("qtd_funcionarios", 0)))
                            except: qtd_func_val = 0
                            cursor.execute("""
                                INSERT OR IGNORE INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                validar_e_formatar_data_input(row.get("Data Registro", row.get("data_registro"))),
                                formatar_titulo(nome_emp_val),
                                formatar_cnpj(row.get("CNPJ", row.get("cnpj"))),
                                str(row.get("CEP", row.get("cep", ""))).strip(),
                                formatar_titulo(row.get("Cidade", row.get("cidade", ""))),
                                formatar_titulo(row.get("Bairro", row.get("bairro", ""))),
                                formatar_titulo(row.get("Endereço", row.get("endereco", ""))),
                                str(row.get("Telefone", row.get("telefone", ""))).strip(),
                                str(row.get("E-mail", row.get("email", ""))).strip(),
                                formatar_titulo(row.get("Responsável", row.get("responsavel", ""))),
                                str(row.get("Grau Risco", row.get("grau_risco", "1"))).strip(),
                                qtd_func_val
                            ))
                    conn.commit()
                    conn.close()
                    st.success("Atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação.")

            st.markdown("---")
            st.subheader("🗑️ Excluir Empresa Definitivamente")
            with st.form("form_excluir_empresa"):
                lista_nomes_empresas = sorted(df_emp["nome_empresa"].tolist())
                empresa_para_excluir = st.selectbox("Selecione a empresa que deseja excluir:", lista_nomes_empresas)
                chk_excluir_emp = st.checkbox("⚠️ Confirmo que desejo excluir esta empresa e todos os seus dados vinculados permanentemente")
                btn_executar_exclusao = st.form_submit_button("🗑️ Excluir Empresa e Dados Relacionados")

                if btn_executar_exclusao:
                    if chk_excluir_emp and empresa_para_excluir:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM empresas WHERE nome_empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM base_funcionarios WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM exames WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM treinamentos WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM epis WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM servicos_realizados WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM usuarios_sistema WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_cargos WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_epis WHERE empresa = ?", (empresa_para_excluir,))
                        conn.commit()
                        conn.close()
                        st.success(f"Empresa '{empresa_para_excluir}' e todos os seus registros associados foram excluídos com sucesso!")
                        st.rerun()
                    else:
                        st.error("Selecione a empresa e marque a caixa de confirmação para autorizar a exclusão.")
        else:
            st.dataframe(formatar_colunas_tabela(df_emp.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 2. CADASTROS GERAIS (COM BOTÕES UNIFICADOS DE ADICIONAR E SALVAR)
# ==========================================
elif menu == "Cadastros Gerais":
    st.title("⚙️ Gerenciamento de Cadastros Gerais")
    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador.")
    else:
        empresas_cadastradas = get_empresas()
        aba_g1, aba_g2, aba_g3, aba_g4 = st.tabs(["Cargos", "Serviços", "Treinamentos", "EPIs"])

        with aba_g1:
            st.subheader("Gerenciar Cargos por Empresa")
            with st.form("form_cad_cargo_unico"):
                empresa_cargo_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_cargo")
                novo_cargo = st.text_input("Novo Cargo")
                btn_add_salvar_cargo = st.form_submit_button("Adicionar e Salvar Cargo")
                
                if btn_add_salvar_cargo:
                    if empresa_cargo_sel != "Nenhuma" and novo_cargo.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (empresa_cargo_sel, formatar_titulo(novo_cargo)))
                            conn.commit()
                            st.success("Cargo adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este cargo já está cadastrado para esta empresa.")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do cargo.")

            st.markdown("---")
            conn = sqlite3.connect(DB_NAME)
            df_cargos_geral = pd.read_sql("SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC", conn)
            conn.close()
            if not df_cargos_geral.empty:
                df_cargos_ex = formatar_colunas_tabela(df_cargos_geral.drop(columns=["id"]))
                edit_cargos = st.data_editor(df_cargos_ex, num_rows="dynamic", key="edit_cargos_tbl", use_container_width=True)
                if st.button("💾 Salvar Alterações na Tabela de Cargos"):
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cad_cargos")
                    for _, row in edit_cargos.iterrows():
                        e_val = row.get("Empresa", row.get("empresa"))
                        c_val = row.get("Cargo", row.get("cargo"))
                        if pd.notna(e_val) and pd.notna(c_val) and str(c_val).strip():
                            cursor.execute("INSERT OR IGNORE INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (str(e_val).strip(), formatar_titulo(c_val)))
                    conn.commit()
                    conn.close()
                    st.success("Cargos atualizados com sucesso!")
                    st.rerun()

        with aba_g2:
            st.subheader("Gerenciar Tipos de Serviços")
            with st.form("form_cad_servico_unico"):
                novo_serv = st.text_input("Novo Tipo de Serviço")
                btn_add_salvar_serv = st.form_submit_button("Adicionar e Salvar Serviço")
                
                if btn_add_salvar_serv:
                    if novo_serv.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_servicos (servico) VALUES (?)", (formatar_titulo(novo_serv),))
                            conn.commit()
                            st.success("Serviço adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este serviço já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do serviço.")

            st.markdown("---")
            conn = sqlite3.connect(DB_NAME)
            df_serv_geral = pd.read_sql("SELECT id, servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            if not df_serv_geral.empty:
                df_serv_ex = formatar_colunas_tabela(df_serv_geral.drop(columns=["id"]))
                edit_serv = st.data_editor(df_serv_ex, num_rows="dynamic", key="edit_serv_tbl", use_container_width=True)
                if st.button("💾 Salvar Alterações na Tabela de Serviços"):
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cad_servicos")
                    for _, row in edit_serv.iterrows():
                        s_val = row.get("Serviço", row.get("servico"))
                        if pd.notna(s_val) and str(s_val).strip():
                            cursor.execute("INSERT OR IGNORE INTO cad_servicos (servico) VALUES (?)", (formatar_titulo(s_val),))
                    conn.commit()
                    conn.close()
                    st.success("Serviços atualizados com sucesso!")
                    st.rerun()

        with aba_g3:
            st.subheader("Gerenciar Tipos de Treinamentos")
            with st.form("form_cad_treinamento_unico"):
                novo_trein = st.text_input("Novo Treinamento")
                btn_add_salvar_trein = st.form_submit_button("Adicionar e Salvar Treinamento")
                
                if btn_add_salvar_trein:
                    if novo_trein.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_treinamentos (treinamento) VALUES (?)", (formatar_titulo(novo_trein),))
                            conn.commit()
                            st.success("Treinamento adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este treinamento já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do treinamento.")

            st.markdown("---")
            conn = sqlite3.connect(DB_NAME)
            df_trein_geral = pd.read_sql("SELECT id, treinamento FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            if not df_trein_geral.empty:
                df_trein_ex = formatar_colunas_tabela(df_trein_geral.drop(columns=["id"]))
                edit_trein = st.data_editor(df_trein_ex, num_rows="dynamic", key="edit_trein_tbl", use_container_width=True)
                if st.button("💾 Salvar Alterações na Tabela de Treinamentos"):
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cad_treinamentos")
                    for _, row in edit_trein.iterrows():
                        t_val = row.get("Treinamento", row.get("treinamento"))
                        if pd.notna(t_val) and str(t_val).strip():
                            cursor.execute("INSERT OR IGNORE INTO cad_treinamentos (treinamento) VALUES (?)", (formatar_titulo(t_val),))
                    conn.commit()
                    conn.close()
                    st.success("Treinamentos atualizados com sucesso!")
                    st.rerun()

        with aba_g4:
            st.subheader("Gerenciar EPIs por Empresa (com CA)")
            with st.form("form_cad_epi_unico"):
                empresa_epi_sel = st.selectbox("Selecione a Empresa para EPI", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_epi_geral")
                c_epi_1, c_epi_2 = st.columns(2)
                novo_epi_nome = c_epi_1.text_input("Nome do EPI")
                novo_epi_ca = c_epi_2.text_input("Número do CA")
                btn_add_salvar_epi = st.form_submit_button("Adicionar e Salvar EPI e CA")
                
                if btn_add_salvar_epi:
                    if empresa_epi_sel != "Nenhuma" and novo_epi_nome.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_epis (empresa, epi, ca) VALUES (?, ?, ?)", (empresa_epi_sel, formatar_titulo(novo_epi_nome), novo_epi_ca.strip()))
                            conn.commit()
                            st.success("EPI adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este EPI já está cadastrado para esta empresa.")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do EPI.")

            st.markdown("---")
            conn = sqlite3.connect(DB_NAME)
            df_epis_geral = pd.read_sql("SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC", conn)
            conn.close()
            if not df_epis_geral.empty:
                df_epis_ex = formatar_colunas_tabela(df_epis_geral.drop(columns=["id"]))
                edit_epis = st.data_editor(df_epis_ex, num_rows="dynamic", key="edit_epis_tbl", use_container_width=True)
                if st.button("💾 Salvar Alterações na Tabela de EPIs"):
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cad_epis")
                    for _, row in edit_epis.iterrows():
                        e_val = row.get("Empresa", row.get("empresa"))
                        epi_val = row.get("EPI", row.get("epi"))
                        ca_val = row.get("CA", row.get("ca"))
                        if pd.notna(e_val) and pd.notna(epi_val) and str(epi_val).strip():
                            cursor.execute("INSERT OR IGNORE INTO cad_epis (empresa, epi, ca) VALUES (?, ?, ?)", (str(e_val).strip(), formatar_titulo(epi_val), str(ca_val).strip()))
                    conn.commit()
                    conn.close()
                    st.success("EPIs atualizados com sucesso!")
                    st.rerun()

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================
elif menu == "Gestão de Funcionários":
    st.title("👥 Cadastro de Funcionários")
    empresas_cadastradas = get_empresas()

    if is_admin:
        with st.expander("➕ Adicionar Novo Funcionário", expanded=False):
            with st.form("form_func"):
                c1, c2 = st.columns(2)
                empresa = c1.selectbox("Empresa Cliente", options=empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="func_emp_sel_form")
                
                cargos_empresa_lista = []
                if empresa and empresa != "Nenhuma":
                    conn_c = sqlite3.connect(DB_NAME)
                    df_c_emp = pd.read_sql("SELECT cargo FROM cad_cargos WHERE empresa = ? ORDER BY cargo ASC", conn_c, params=(empresa,))
                    conn_c.close()
                    cargos_empresa_lista = df_c_emp["cargo"].tolist()

                matricula = c1.text_input("Matrícula")
                nome = c1.text_input("Nome do Funcionário")
                cargo = c2.selectbox("Cargo", options=cargos_empresa_lista) if cargos_empresa_lista else c2.text_input("Cargo")
                setor = c2.text_input("Setor")
                cpf = c1.text_input("CPF")
                data_admissao_input = c2.text_input("Data Admissão (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                status_func = c1.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"])
                
                if st.form_submit_button("Salvar Funcionário"):
                    if empresa != "Nenhuma" and nome.strip():
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (matricula, formatar_titulo(nome), formatar_titulo(cargo), formatar_titulo(setor), formatar_cpf(cpf), validar_e_formatar_data_input(data_admissao_input), limpar_status_banco(status_func), empresa))
                        conn.commit()
                        conn.close()
                        st.success("Funcionário cadastrado com sucesso!")
                        st.rerun()

    st.subheader("Funcionários Cadastrados")
    filtro_empresa_func = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_func_emp") if is_admin else emp_usuario
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM base_funcionarios" + ("" if (not is_admin or filtro_empresa_func == "Todas as Empresas") else " WHERE empresa = ?") + " ORDER BY funcionario ASC", conn, params=None if (not is_admin or filtro_empresa_func == "Todas as Empresas") else (filtro_empresa_func,))
    conn.close()
    
    if not df.empty:
        df["data_admissao"] = df["data_admissao"].apply(formatar_data_br)
        df["cpf"] = df["cpf"].apply(formatar_cpf)
        df["status"] = df["status"].apply(lambda x: formatar_status_visual(x, "func"))
        
        if is_admin:
            df_exibicao = formatar_colunas_tabela(df.drop(columns=["id"]))
            editado = st.data_editor(df_exibicao, num_rows="dynamic", key="editor_func", use_container_width=True)
            if st.button("💾 Salvar Alterações Funcionários"):
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                if filtro_empresa_func == "Todas as Empresas": cursor.execute("DELETE FROM base_funcionarios")
                else: cursor.execute("DELETE FROM base_funcionarios WHERE empresa = ?", (filtro_empresa_func,))
                for _, row in editado.iterrows():
                    emp_val = row.get("Empresa", row.get("empresa"))
                    func_val = row.get("Funcionário", row.get("funcionario"))
                    cargo_val = row.get("Cargo", row.get("cargo"))
                    setor_val = row.get("Setor", row.get("setor"))
                    cpf_val = row.get("CPF", row.get("cpf"))
                    dt_val = row.get("Data Admissão", row.get("data_admissao"))
                    status_val = row.get("Status", row.get("status"))
                    mat_val = row.get("Matrícula", row.get("matricula"))

                    cursor.execute("INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) VALUES (?,?,?,?,?,?,?,?)",
                                   (mat_val, formatar_titulo(func_val), formatar_titulo(cargo_val), formatar_titulo(setor_val), formatar_cpf(cpf_val), validar_e_formatar_data_input(dt_val), limpar_status_banco(status_val), emp_val))
                conn.commit()
                conn.close()
                st.success("Salvo com sucesso!")
                st.rerun()
        else:
            st.dataframe(formatar_colunas_tabela(df.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 4. TREINAMENTOS
# ==========================================
elif menu == "Treinamentos":
    st.title("📚 Controle de Treinamentos")
    empresas = get_empresas()
    
    if is_admin:
        with st.expander("➕ Inserção de Treinamento para Funcionário", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_trein")
            conn = sqlite3.connect(DB_NAME)
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(empresa_sel,))
            df_cad_trein = pd.read_sql("SELECT treinamento FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            
            if not df_funcs.empty:
                with st.form("form_trein"):
                    func_sel = st.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == func_sel].iloc[0]
                    c1, c2 = st.columns(2)
                    matr_v = c1.text_input("Matrícula", value=str(colab['matricula']))
                    cargo_v = c1.text_input("Cargo", value=str(colab['cargo']))
                    setor_v = c1.text_input("Setor", value=str(colab['setor']))
                    trein_sel = c2.selectbox("Treinamento", df_cad_trein["treinamento"].tolist() if not df_cad_trein.empty else ["Nenhum"])
                    carga_v = c2.text_input("Carga Horária", value="8h")
                    dt_real = c1.text_input("Data Realização", value=datetime.today().strftime("%d/%m/%Y"))
                    val_mes = c2.number_input("Validade (Meses)", min_value=1, value=12)
                    dt_venc = c1.text_input("Próximo Vencimento", value=datetime.today().strftime("%d/%m/%Y"))
                    status_tr = c2.selectbox("Status", ["🟢 em dia", "🟠 A Vencer", "🔴 Vencido"])
                    
                    if st.form_submit_button("Salvar Treinamento"):
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                       (empresa_sel, matr_v, func_sel, cargo_v, setor_v, trein_sel, carga_v, validar_e_formatar_data_input(dt_real), int(val_mes), validar_e_formatar_data_input(dt_venc), limpar_status_banco(status_tr)))
                        conn.commit()
                        conn.close()
                        st.success("Salvo com sucesso!")
                        st.rerun()

    st.subheader("Treinamentos Registrados")
    filtro_tr = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_tr_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    df_tr = pd.read_sql("SELECT * FROM treinamentos" + ("" if (not is_admin or filtro_tr == "Todas as Empresas") else " WHERE empresa = ?") + " ORDER BY funcionario ASC", conn, params=None if (not is_admin or filtro_tr == "Todas as Empresas") else (filtro_tr,))
    conn.close()
    if not df_tr.empty:
        df_tr["data_realizacao"] = df_tr["data_realizacao"].apply(formatar_data_br)
        df_tr["proximo_vencimento"] = df_tr["proximo_vencimento"].apply(formatar_data_br)
        df_tr["status"] = df_tr["status"].apply(lambda x: formatar_status_visual(x, "trein"))
        st.dataframe(formatar_colunas_tabela(df_tr.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 5. EXAMES OCUPACIONAIS
# ==========================================
elif menu == "Exames Ocupacionais":
    st.title("🩺 Controle de Exames Ocupacionais")
    empresas = get_empresas()
    
    if is_admin:
        with st.expander("➕ Adicionar Novo Exame", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="ex_emp")
            conn = sqlite3.connect(DB_NAME)
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(empresa_sel,))
            conn.close()
            if not df_funcs.empty:
                with st.form("form_exame"):
                    nome_sel = st.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    c1, c2 = st.columns(2)
                    ultimo = c1.text_input("Data Último Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    tipo_ex = c1.selectbox("Tipo", ["Admissional", "Periódico", "Retorno ao Trabalho", "Demissional"])
                    proximo = c2.text_input("Data Próximo Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    status_ex = c2.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"])
                    if st.form_submit_button("Salvar Exame"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) VALUES (?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], validar_e_formatar_data_input(ultimo), tipo_ex, validar_e_formatar_data_input(proximo), limpar_status_banco(status_ex)))
                        conn.commit()
                        conn.close()
                        st.success("Exame salvo!")
                        st.rerun()

    st.subheader("Exames Registrados")
    filtro_ex = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ex_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    df_ex = pd.read_sql("SELECT * FROM exames" + ("" if (not is_admin or filtro_ex == "Todas as Empresas") else " WHERE empresa = ?") + " ORDER BY funcionario ASC", conn, params=None if (not is_admin or filtro_ex == "Todas as Empresas") else (filtro_ex,))
    conn.close()
    if not df_ex.empty:
        df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br)
        df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br)
        df_ex["status"] = df_ex["status"].apply(lambda x: formatar_status_visual(x, "ex"))
        st.dataframe(formatar_colunas_tabela(df_ex.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 6. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
    st.title("🦺 Controle de Equipamentos de Proteção Individual (EPI)")
    empresas = get_empresas()

    if is_admin:
        with st.expander("➕ Registrar Entrega de EPI", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_epi")
            conn_e = sqlite3.connect(DB_NAME)
            df_e_emp = pd.read_sql("SELECT epi, ca FROM cad_epis WHERE empresa = ? ORDER BY epi ASC", conn_e, params=(empresa_sel,))
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn_e, params=(empresa_sel,))
            conn_e.close()
            
            lista_epis_emp = df_e_emp["epi"].tolist() if not df_e_emp.empty else []
            mapa_ca_epis = dict(zip(df_e_emp["epi"], df_e_emp["ca"])) if not df_e_emp.empty else {}

            if not df_funcs.empty and lista_epis_emp:
                with st.form("form_epi"):
                    c1, c2 = st.columns(2)
                    nome_sel = c1.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    epi_sel = c1.selectbox("EPI", lista_epis_emp)
                    ca_epi = c2.text_input("Número do CA", value=mapa_ca_epis.get(epi_sel, ""))
                    data_entrega = c1.text_input("Data Entrega", value=datetime.today().strftime("%d/%m/%Y"))
                    qtd = c2.number_input("Quantidade", min_value=1, value=1)
                    status_epi = c1.selectbox("Status", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"])
                    if st.form_submit_button("Salvar EPI"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], epi_sel, ca_epi, validar_e_formatar_data_input(data_entrega), int(qtd), limpar_status_banco(status_epi)))
                        conn.commit()
                        conn.close()
                        st.success("EPI registrado!")
                        st.rerun()

    st.subheader("EPIs Registrados")
    filtro_ep = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ep_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    df_ep = pd.read_sql("SELECT * FROM epis" + ("" if (not is_admin or filtro_ep == "Todas as Empresas") else " WHERE empresa = ?") + " ORDER BY funcionario ASC", conn, params=None if (not is_admin or filtro_ep == "Todas as Empresas") else (filtro_ep,))
    conn.close()
    if not df_ep.empty:
        df_ep["data_entrega"] = df_ep["data_entrega"].apply(formatar_data_br)
        df_ep["status"] = df_ep["status"].apply(lambda x: formatar_status_visual(x, "epi"))
        st.dataframe(formatar_colunas_tabela(df_ep.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 7. SERVIÇOS REALIZADOS
# ==========================================
elif menu == "Serviços Realizados":
    st.title("🛠️ Controle de Serviços Realizados")
    empresas = get_empresas()
    
    if is_admin:
        with st.expander("➕ Registrar Novo Serviço Realizado", expanded=False):
            conn = sqlite3.connect(DB_NAME)
            df_cad_serv = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            lista_serv_cad = df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []
            
            if empresas and lista_serv_cad:
                with st.form("form_servico_completo"):
                    c1, c2 = st.columns(2)
                    empresa_sel_srv = c1.selectbox("Empresa Cliente", empresas)
                    servico_sel = c1.selectbox("Tipo de Serviço", lista_serv_cad)
                    data_realizacao_srv = c1.text_input("Data Realização", value=datetime.today().strftime("%d/%m/%Y"))
                    responsavel_srv = c2.text_input("Responsável Técnico", value="Luiz Marcelo Fontana")
                    status_srv = c2.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"])
                    observacoes_srv = c2.text_input("Observações")
                    if st.form_submit_button("Salvar Serviço"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) VALUES (?,?,?,?,?,?)",
                                     (empresa_sel, servico_sel, validar_e_formatar_data_input(data_realizacao_srv), formatar_titulo(responsavel_srv), observacoes_srv, limpar_status_banco(status_srv)))
                        conn.commit()
                        conn.close()
                        st.success("Serviço registrado!")
                        st.rerun()

    st.subheader("Serviços Registrados")
    filtro_srv = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_srv_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    df_serv = pd.read_sql("SELECT * FROM servicos_realizados" + ("" if (not is_admin or filtro_srv == "Todas as Empresas") else " WHERE empresa = ?") + " ORDER BY empresa ASC", conn, params=None if (not is_admin or filtro_srv == "Todas as Empresas") else (filtro_srv,))
    conn.close()
    if not df_serv.empty:
        df_serv["data_realizacao"] = df_serv["data_realizacao"].apply(formatar_data_br)
        df_serv["status"] = df_serv["status"].apply(lambda x: formatar_status_visual(x, "serv"))
        st.dataframe(formatar_colunas_tabela(df_serv.drop(columns=["id"])), use_container_width=True)

# ==========================================
# 8. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    st.title("🛠️ Painel Administrativo e Backup")
    if not is_admin:
        st.warning("🔒 Área exclusiva para o Administrador.")
    else:
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 Baixar Backup (.db)", f, file_name="cassilab_gestao.db", mime="application/octet-stream")

# ==========================================
# 9. RELATÓRIOS CONSOLIDADOS
# ==========================================
elif menu == "Relatórios Consolidados":
    st.title("📑 Relatórios Consolidados")
    c1, c2, c3, c4, c5 = st.columns(5)
    inc_func = c1.checkbox("👥 Funcionários", value=True)
    inc_ex = c2.checkbox("🩺 Exames", value=True)
    inc_tr = c3.checkbox("📚 Treinamentos", value=True)
    inc_ep = c4.checkbox("🦺 EPIs", value=True)
    inc_srv = c5.checkbox("🛠️ Serviços", value=True)
    
    empresas = get_empresas()
    empresa_filtro = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas) if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    
    if inc_func:
        st.subheader("Funcionários")
        df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios" + ("" if (not is_admin or empresa_filtro == "Todas as Empresas") else " WHERE empresa = ?"), conn, params=None if (not is_admin or empresa_filtro == "Todas as Empresas") else (empresa_filtro,))
        if not df_f.empty: st.dataframe(formatar_colunas_tabela(df_f), use_container_width=True)
    if inc_ex:
        st.subheader("Exames")
        df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames" + ("" if (not is_admin or empresa_filtro == "Todas as Empresas") else " WHERE empresa = ?"), conn, params=None if (not is_admin or empresa_filtro == "Todas as Empresas") else (empresa_filtro,))
        if not df_e.empty: st.dataframe(formatar_colunas_tabela(df_e), use_container_width=True)
    if inc_tr:
        st.subheader("Treinamentos")
        df_t = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, proximo_vencimento, status FROM treinamentos" + ("" if (not is_admin or empresa_filtro == "Todas as Empresas") else " WHERE empresa = ?"), conn, params=None if (not is_admin or empresa_filtro == "Todas as Empresas") else (empresa_filtro,))
        if not df_t.empty: st.dataframe(formatar_colunas_tabela(df_t), use_container_width=True)
    if inc_ep:
        st.subheader("EPIs")
        df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis" + ("" if (not is_admin or empresa_filtro == "Todas as Empresas") else " WHERE empresa = ?"), conn, params=None if (not is_admin or empresa_filtro == "Todas as Empresas") else (empresa_filtro,))
        if not df_p.empty: st.dataframe(formatar_colunas_tabela(df_p), use_container_width=True)
    if inc_srv:
        st.subheader("Serviços")
        df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, status FROM servicos_realizados" + ("" if (not is_admin or empresa_filtro == "Todas as Empresas") else " WHERE empresa = ?"), conn, params=None if (not is_admin or empresa_filtro == "Todas as Empresas") else (empresa_filtro,))
        if not df_s.empty: st.dataframe(formatar_colunas_tabela(df_s), use_container_width=True)
    conn.close()