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
    
    # 3. Tabela Usuários do Sistema (Com e-mail e celular)
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

def get_empresas():
    conn = sqlite3.connect(DB_NAME)
    empresas_set = set()
    try:
        df1 = pd.read_sql("SELECT DISTINCT nome_empresa FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != '' ORDER BY nome_empresa ASC", conn)
        for e in df1["nome_empresa"].tolist():
            if str(e).strip():
                empresas_set.add(str(e).strip())
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
                        "logradouro": dados.get("logradouro", ""),
                        "bairro": dados.get("bairro", ""),
                        "cidade": f"{dados.get('localidade', '')} - {dados.get('uf', '')}" if dados.get('uf') else dados.get('localidade', '')
                    }
        except:
            pass
    return None

def validar_e_formatar_data_input(data_str):
    if not data_str or not str(data_str).strip():
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

def formatar_status_visual(val, tipo):
    if pd.isna(val) or not str(val).strip():
        if tipo == "func":
            return "🟢 Ativo"
        elif tipo == "trein":
            return "🟢 em dia"
        elif tipo == "ex":
            return "🟢 Válido"
        elif tipo == "epi":
            return "🟢 Entregue"
        else:
            return "🟢 Concluído"
            
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

# --- CONTROLE DE SESSÃO (LOGIN, CADASTRO E RECUPERAÇÃO) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "empresa_usuario" not in st.session_state:
    st.session_state["empresa_usuario"] = ""

if not st.session_state["autenticado"]:
    try:
        st.image("logo.png", width=140)
    except:
        pass
    
    st.markdown("<h1 style='font-size: 24px;'>Cassilab Consultoria e Treinamentos</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: gray; font-size: 15px;'>Sistema de Gestão Integrada em SST</h3>", unsafe_allow_html=True)
    st.write("")

    aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔑 Entrar no Sistema", "📝 Cadastrar Novo Usuário", "🔄 Recuperar Senha"])

    with aba_login:
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário ou CPF", value="", autocomplete="off")
            senha_input = st.text_input("Senha", value="", type="password", autocomplete="new-password")
            btn_login = st.form_submit_button("Acessar Sistema")
            
            if btn_login:
                if usuario_input == "admin" and senha_input == "Disc@5232":
                    st.session_state["autenticado"] = True
                    st.session_state["is_admin"] = True
                    st.session_state["empresa_usuario"] = "Todas"
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
                        st.session_state["is_admin"] = False
                        st.session_state["empresa_usuario"] = user_db[3]
                        st.success(f"Bem-vindo(a), {user_db[1]}! (Acesso restrito à empresa: {user_db[3]})")
                        st.rerun()
                    else:
                        st.error("Usuário/CPF ou senha inválidos.")

    with aba_cadastro:
        st.markdown("Preencha os dados abaixo. Digite parte do nome da sua empresa para vinculação:")
        with st.form("form_novo_usuario"):
            cad_nome = st.text_input("Nome Completo", value="", autocomplete="off")
            cad_cpf = st.text_input("CPF (Somente números ou pontuado)", value="", autocomplete="off")
            cad_email = st.text_input("E-mail para Contato / Recuperação", value="", autocomplete="off")
            cad_celular = st.text_input("Celular / WhatsApp (Com DDD)", value="", autocomplete="off")
            cad_empresa_busca = st.text_input("Nome ou Parte do Nome da Empresa", value="", autocomplete="off")
            cad_senha = st.text_input("Crie uma Senha", value="", type="password", autocomplete="new-password")
            btn_cad_usuario = st.form_submit_button("Cadastrar Novo Acesso")

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
                                           (cad_nome, cpf_formatado, empresa_final, cad_email.strip(), cad_celular.strip(), cad_senha))
                            conn.commit()
                            st.success(f"Cadastro realizado com sucesso vinculado à empresa '{empresa_final}'! Vá para a aba 'Entrar no Sistema'.")
                        except sqlite3.IntegrityError:
                            st.error("Este CPF já possui cadastro no sistema.")
                    else:
                        st.error("Nenhuma empresa encontrada com esse nome. Verifique com o administrador se a empresa já está cadastrada.")
                    conn.close()
                else:
                    st.error("Preencha todos os campos obrigatórios.")

    with aba_recuperar:
        st.markdown("Informe seu CPF cadastrado e escolha o meio para envio ou validação da recuperação de senha:")
        with st.form("form_recuperar"):
            rec_cpf = st.text_input("Digite seu CPF cadastrado", value="", autocomplete="off")
            rec_opcao = st.radio("Deseja recuperar via:", ["E-mail cadastrado", "Celular / WhatsApp cadastrado"])
            btn_rec_enviar = st.form_submit_button("Localizar Cadastro para Recuperação")

            if btn_rec_enviar:
                if rec_cpf.strip():
                    cpf_formatado = formatar_cpf(rec_cpf)
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("SELECT nome, email, celular FROM usuarios_sistema WHERE cpf = ?", (cpf_formatado,))
                    res_user = cursor.fetchone()
                    conn.close()

                    if res_user:
                        nome_u, email_u, cel_u = res_user
                        st.success(f"Cadastro localizado para **{nome_u}**!")
                        if "E-mail" in rec_opcao:
                            st.info(f"📩 As instruções de redefinição de senha foram enviadas para o e-mail: **{email_u if email_u else 'Não cadastrado'}**")
                        else:
                            st.info(f"📱 As instruções de redefinição de senha foram enviadas via WhatsApp para o celular: **{cel_u if cel_u else 'Não cadastrado'}**")
                    else:
                        st.error("CPF não encontrado na base de usuários do sistema.")
                else:
                    st.error("Digite o CPF para prosseguir.")

    st.markdown("---")
    st.markdown("<p style='font-size: 11px; color: gray;'>⚖️ <b>Aviso Legal / LGPD:</b> Os dados coletados neste sistema são estritamente confidenciais e utilizados unicamente para fins de Gestão de Saúde e Segurança do Trabalho (SST), em conformidade com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018).</p>", unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
try:
    st.sidebar.image("logo.png", width=120)
except:
    st.sidebar.markdown("### Cassilab SST")

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
    st.sidebar.success("✅ Dados salvos e sessão encerrada com segurança!")
    st.rerun()

is_admin = st.session_state["is_admin"]
emp_usuario = st.session_state["empresa_usuario"]

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
        if is_admin:
            total_empresas = pd.read_sql("SELECT COUNT(DISTINCT nome_empresa) as qtd FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''", conn).iloc[0]["qtd"]
        else:
            total_empresas = 1 if emp_usuario else 0
    except:
        total_empresas = 0
        
    try:
        if is_admin:
            total_funcs = pd.read_sql("SELECT COUNT(*) as qtd FROM base_funcionarios", conn).iloc[0]["qtd"]
        else:
            total_funcs = pd.read_sql("SELECT COUNT(*) as qtd FROM base_funcionarios WHERE empresa = ?", conn, params=(emp_usuario,)).iloc[0]["qtd"]
    except:
        total_funcs = 0
        
    try:
        if is_admin:
            df_ex = pd.read_sql("SELECT * FROM exames", conn)
        else:
            df_ex = pd.read_sql("SELECT * FROM exames WHERE empresa = ?", conn, params=(emp_usuario,))
        total_exames = len(df_ex)
        vencidos_ex = len(df_ex[df_ex["status"].str.lower().str.contains("vencido")]) if not df_ex.empty else 0
    except:
        total_exames = 0
        vencidos_ex = 0

    try:
        if is_admin:
            df_tr = pd.read_sql("SELECT * FROM treinamentos", conn)
        else:
            df_tr = pd.read_sql("SELECT * FROM treinamentos WHERE empresa = ?", conn, params=(emp_usuario,))
        total_tr = len(df_tr)
        vencidos_tr = len(df_tr[df_tr["status"].str.lower().str.contains("vencido")]) if not df_tr.empty else 0
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
    if not is_admin:
        st.info(f"ℹ️ Você está conectado com acesso restrito aos dados da empresa: **{emp_usuario}**.")
    else:
        st.info("💡 **Dica:** Utilize o menu lateral para navegar entre os cadastros de empresas, funcionários, exames, treinamentos e emissão de backups.")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
    st.title("🏢 Cadastro de Empresas Clientes")

    if is_admin:
        with st.expander("➕ Adicionar Nova Empresa", expanded=True):
            # Session states para preenchimento automático via CEP
            if "form_cep" not in st.session_state: st.session_state["form_cep"] = ""
            if "form_end" not in st.session_state: st.session_state["form_end"] = ""
            if "form_bair" not in st.session_state: st.session_state["form_bair"] = ""
            if "form_cid" not in st.session_state: st.session_state["form_cid"] = ""

            with st.form("form_empresa"):
                c1, c2, c3 = st.columns(3)
                nome_empresa = c1.text_input("Nome da Empresa *")
                cnpj = c2.text_input("CNPJ (Somente números ou pontuado)")
                
                # Campo CEP com botão de consulta ou auto-preenchimento
                cep_input = c3.text_input("CEP", value=st.session_state["form_cep"])
                
                # Ordem solicitada: Endereço - Bairro - Cidade
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
                            st.success("CEP encontrado e campos preenchidos com sucesso!")
                            st.rerun()
                        else:
                            st.error("CEP não encontrado ou inválido.")
                    else:
                        st.warning("Digite um CEP para consultar.")

                if btn_salvar_empresa:
                    if nome_empresa.strip():
                        cnpj_formatado = formatar_cnpj(cnpj)
                        data_registro_atual = datetime.now().strftime("%d/%m/%Y")
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                INSERT INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                data_registro_atual, nome_empresa.strip(), cnpj_formatado, cep_input.strip(), cidade_input.strip(), bairro_input.strip(), 
                                endereco_input.strip(), telefone.strip(), email.strip(), responsavel.strip(), 
                                grau_risco, int(qtd_funcionarios)
                            ))
                            conn.commit()
                            # Limpar session states
                            st.session_state["form_cep"] = ""
                            st.session_state["form_end"] = ""
                            st.session_state["form_bair"] = ""
                            st.session_state["form_cid"] = ""
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
    if is_admin:
        df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, qtd_funcionarios, grau_risco FROM empresas ORDER BY nome_empresa ASC", conn)
    else:
        df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, qtd_funcionarios, grau_risco FROM empresas WHERE nome_empresa = ? ORDER BY nome_empresa ASC", conn, params=(emp_usuario,))
    conn.close()

    if not df_emp.empty:
        if "cnpj" in df_emp.columns:
            df_emp["cnpj"] = df_emp["cnpj"].apply(formatar_cnpj)
            
        if "data_registro" in df_emp.columns:
            df_emp["data_registro"] = df_emp["data_registro"].apply(formatar_data_br)

        colunas_emp_ordem = ["id", "data_registro", "nome_empresa", "cnpj", "endereco", "bairro", "cep", "cidade", "email", "telefone", "responsavel", "qtd_funcionarios", "grau_risco"]
        colunas_emp_existentes = [c for c in colunas_emp_ordem if c in df_emp.columns]
        df_emp = df_emp[colunas_emp_existentes]

        if is_admin:
            editado_emp = st.data_editor(df_emp.drop(columns=["id"]), num_rows="dynamic", key="editor_emp", use_container_width=True)
            
            chk_salvar_emp = st.checkbox("⚠️ Confirmo salvar as alterações feitas na tabela de empresas", key="chk_salvar_emp")
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

                            cnpj_fmt = formatar_cnpj(row["cnpj"])
                            dt_reg = validar_e_formatar_data_input(row["data_registro"]) if "data_registro" in row and pd.notna(row["data_registro"]) else datetime.now().strftime("%d/%m/%Y")
                            
                            cursor.execute("""
                                INSERT OR IGNORE INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, grau_risco, qtd_funcionarios) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                dt_reg,
                                str(row["nome_empresa"]).strip(),
                                cnpj_fmt,
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
            st.dataframe(df_emp.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhuma empresa encontrada.")

# ==========================================
# 2. CADASTROS GERAIS
# ==========================================
elif menu == "Cadastros Gerais":
    st.title("⚙️ Gerenciamento de Cadastros")
    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador. Esta seção é apenas para gerenciamento geral.")
    else:
        empresas_cadastradas = get_empresas()
        
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Cargos por Empresa")
            if not empresas_cadastradas:
                st.warning("Cadastre ao menos uma empresa para gerenciar os cargos específicos.")
            else:
                empresa_cargo_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas, key="sel_emp_cargo")
                novo_cargo = st.text_input(f"Novo Cargo para {empresa_cargo_sel}")
                
                if st.button("Adicionar Cargo"):
                    if novo_cargo.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (empresa_cargo_sel, novo_cargo.strip()))
                            conn.commit()
                            st.success("Cargo adicionado com sucesso!")
                        except sqlite3.IntegrityError:
                            st.error("Este cargo já está cadastrado para esta empresa.")
                        finally:
                            conn.close()
                        st.rerun()
                    else:
                        st.error("Digite o nome do cargo.")

                conn = sqlite3.connect(DB_NAME)
                df_c = pd.read_sql("SELECT id, cargo FROM cad_cargos WHERE empresa = ? ORDER BY cargo ASC", conn, params=(empresa_cargo_sel,))
                conn.close()
                
                if not df_c.empty:
                    edit_c = st.data_editor(df_c.drop(columns=["id"]), num_rows="dynamic", key=f"edit_c_{empresa_cargo_sel}", use_container_width=True)
                    chk_c = st.checkbox(f"⚠️ Confirmo salvar/atualizar cargos de {empresa_cargo_sel}", key="chk_c")
                    if st.button("💾 Salvar Cargos da Empresa"):
                        if chk_c:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM cad_cargos WHERE empresa = ?", (empresa_cargo_sel,))
                            for _, r in edit_c.iterrows():
                                if pd.notna(r["cargo"]) and str(r["cargo"]).strip():
                                    try:
                                        conn.execute("INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (empresa_cargo_sel, str(r["cargo"]).strip()))
                                    except:
                                        pass
                            conn.commit()
                            conn.close()
                            st.success("Cargos atualizados!")
                            st.rerun()
                        else:
                            st.warning("Confirme a caixa acima.")
                else:
                    st.info(f"Nenhum cargo cadastrado para {empresa_cargo_sel} ainda.")

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
            df_s = pd.read_sql("SELECT * FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            if not df_s.empty:
                edit_s = st.data_editor(df_s.drop(columns=["id"]), num_rows="dynamic", key="edit_s", use_container_width=True)
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
            df_t = pd.read_sql("SELECT * FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            if not df_t.empty:
                edit_t = st.data_editor(df_t.drop(columns=["id"]), num_rows="dynamic", key="edit_t", use_container_width=True)
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

            st.subheader("EPIs por Empresa (com CA)")
            if not empresas_cadastradas:
                st.warning("Cadastre ao menos uma empresa para gerenciar EPIs específicos.")
            else:
                empresa_epi_sel = st.selectbox("Selecione a Empresa para EPI", empresas_cadastradas, key="sel_emp_epi_geral")
                c_epi_1, c_epi_2 = st.columns(2)
                novo_epi_nome = c_epi_1.text_input("Nome do EPI (Ex: Óculos de Proteção)")
                novo_epi_ca = c_epi_2.text_input("Número do CA")
                
                if st.button("Adicionar EPI e CA"):
                    if novo_epi_nome.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_epis (empresa, epi, ca) VALUES (?, ?, ?)", (empresa_epi_sel, novo_epi_nome.strip(), novo_epi_ca.strip()))
                            conn.commit()
                            st.success("EPI adicionado com sucesso!")
                        except sqlite3.IntegrityError:
                            st.error("Este EPI já está cadastrado para esta empresa.")
                        finally:
                            conn.close()
                        st.rerun()
                    else:
                        st.error("Digite o nome do EPI.")

                conn = sqlite3.connect(DB_NAME)
                df_e = pd.read_sql("SELECT id, epi, ca FROM cad_epis WHERE empresa = ? ORDER BY epi ASC", conn, params=(empresa_epi_sel,))
                conn.close()
                
                if not df_e.empty:
                    edit_e = st.data_editor(df_e.drop(columns=["id"]), num_rows="dynamic", key=f"edit_e_{empresa_epi_sel}", use_container_width=True)
                    chk_e = st.checkbox(f"⚠️ Confirmo salvar/atualizar EPIs de {empresa_epi_sel}", key="chk_e_epi")
                    if st.button("💾 Salvar EPIs da Empresa"):
                        if chk_e:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("DELETE FROM cad_epis WHERE empresa = ?", (empresa_epi_sel,))
                            for _, r in edit_e.iterrows():
                                if pd.notna(r["epi"]) and str(r["epi"]).strip():
                                    try:
                                        conn.execute("INSERT INTO cad_epis (empresa, epi, ca) VALUES (?, ?, ?)", (empresa_epi_sel, str(r["epi"]).strip(), str(r["ca"]).strip() if pd.notna(r["ca"]) else ""))
                                    except:
                                        pass
                            conn.commit()
                            conn.close()
                            st.success("EPIs atualizados!")
                            st.rerun()
                        else:
                            st.warning("Confirme a caixa acima.")
                else:
                    st.info(f"Nenhum EPI cadastrado para {empresa_epi_sel} ainda.")

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================
elif menu == "Gestão de Funcionários":
    st.title("👥 Cadastro de Funcionários")
    empresas_cadastradas = get_empresas()

    if is_admin:
        with st.expander("➕ Adicionar Novo Funcionário", expanded=True):
            with st.form("form_func"):
                c1, c2 = st.columns(2)
                
                if empresas_cadastradas:
                    empresa = c1.selectbox("Empresa Cliente", options=empresas_cadastradas, index=0, key="func_emp_sel_form")
                else:
                    empresa = c1.selectbox("Empresa Cliente", options=["Nenhuma empresa cadastrada"], index=0)
                
                cargos_empresa_lista = []
                if empresa and empresa != "Nenhuma empresa cadastrada":
                    conn_c = sqlite3.connect(DB_NAME)
                    df_c_emp = pd.read_sql("SELECT cargo FROM cad_cargos WHERE empresa = ? ORDER BY cargo ASC", conn_c, params=(empresa,))
                    conn_c.close()
                    cargos_empresa_lista = df_c_emp["cargo"].tolist() if not df_c_emp.empty else []

                matricula = c1.text_input("Matrícula")
                nome = c1.text_input("Nome do Funcionário")
                
                if cargos_empresa_lista:
                    cargo = c2.selectbox("Cargo", options=cargos_empresa_lista)
                else:
                    cargo = c2.text_input("Cargo (Nenhum cargo cadastrado para esta empresa, digite livremente)")

                setor = c2.text_input("Setor")
                cpf = c1.text_input("CPF (Somente números ou pontuado)")
                data_admissao_input = c2.text_input("Data Admissão (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                status_func = c1.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"])
                
                if st.form_submit_button("Salvar Funcionário"):
                    if empresa and empresa != "Nenhuma empresa cadastrada" and nome:
                        data_admissao_br = validar_e_formatar_data_input(data_admissao_input)
                        status_limpo = limpar_status_banco(status_func)
                        cpf_formatado = formatar_cpf(cpf)
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR IGNORE INTO empresas (nome_empresa) VALUES (?)", (empresa,))
                        cursor.execute("""
                            INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (matricula, nome, cargo, setor, cpf_formatado, data_admissao_br, status_limpo, empresa))
                        conn.commit()
                        conn.close()
                        st.success("Funcionário e empresa cadastrados com sucesso!")
                        st.rerun()
                    else:
                        st.error("Selecione uma Empresa válida e preencha o Nome do Funcionário.")

    st.subheader("Funcionários Cadastrados")
    
    if is_admin:
        if empresas_cadastradas:
            filtro_empresa_func = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_func_emp")
        else:
            filtro_empresa_func = "Todas as Empresas"
    else:
        filtro_empresa_func = emp_usuario
        st.info(f"Exibindo dados exclusivos da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)
    if is_admin and filtro_empresa_func == "Todas as Empresas":
        df = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
    else:
        emp_busca = filtro_empresa_func if is_admin else emp_usuario
        df = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_busca,))
    conn.close()
    
    if not df.empty:
        if "data_admissao" in df.columns:
            df["data_admissao"] = df["data_admissao"].apply(formatar_data_br)
            
        if "cpf" in df.columns:
            df["cpf"] = df["cpf"].apply(formatar_cpf)

        if "status" in df.columns:
            df["status"] = df["status"].apply(lambda x: formatar_status_visual(x, "func"))

        colunas_ordenadas = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "cpf", "data_admissao", "status"]
        colunas_existentes = [c for c in colunas_ordenadas if c in df.columns]
        df = df[colunas_existentes]

        if is_admin:
            editado = st.data_editor(
                df.drop(columns=["id"]), 
                num_rows="dynamic", 
                key="editor_func",
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "status",
                        help="Selecione o status do funcionário",
                        options=["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"],
                        required=True
                    ),
                    "data_admissao": st.column_config.TextColumn(
                        "data_admissao",
                        help="Insira no formato DD/MM/AAAA",
                        required=True
                    ),
                    "cpf": st.column_config.TextColumn(
                        "cpf",
                        help="Formato 000.000.000-00",
                        required=True
                    )
                },
                use_container_width=True
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                chk_salvar_func = st.checkbox("⚠️ Confirmo salvar as alterações nos funcionários", key="chk_salvar_func")
                if st.button("💾 Salvar Alterações"):
                    if chk_salvar_func:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        if filtro_empresa_func == "Todas as Empresas":
                            cursor.execute("DELETE FROM base_funcionarios")
                        else:
                            cursor.execute("DELETE FROM base_funcionarios WHERE empresa = ?", (filtro_empresa_func,))
                        
                        for _, row in editado.iterrows():
                            dt_br = validar_e_formatar_data_input(row["data_admissao"])
                            status_limpo = limpar_status_banco(row["status"])
                            cpf_fmt = formatar_cpf(row["cpf"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                                    VALUES (?,?,?,?,?,?,?,?)
                                """, (row["matricula"], row["funcionario"], row["cargo"], row["setor"], cpf_fmt, dt_br, status_limpo, row["empresa"]))
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
                        if filtro_empresa_func == "Todas as Empresas":
                            cursor.execute("DELETE FROM base_funcionarios")
                        else:
                            cursor.execute("DELETE FROM base_funcionarios WHERE empresa = ?", (filtro_empresa_func,))

                        for _, row in editado.iterrows():
                            dt_br = validar_e_formatar_data_input(row["data_admissao"])
                            status_limpo = limpar_status_banco(row["status"])
                            cpf_fmt = formatar_cpf(row["cpf"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                                    VALUES (?,?,?,?,?,?,?,?)
                                """, (row["matricula"], row["funcionario"], row["cargo"], row["setor"], cpf_fmt, dt_br, status_limpo, row["empresa"]))
                        conn.commit()
                        conn.close()
                        st.success("Registros sincronizados/excluídos com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para autorizar a exclusão.")
        else:
            st.dataframe(df.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhum funcionário encontrado para o filtro selecionado.")

# ==========================================
# 4. TREINAMENTOS
# ==========================================
elif menu == "Treinamentos":
    st.title("📚 Controle de Treinamentos")
    
    if is_admin:
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
    df_cad_trein = pd.read_sql("SELECT treinamento FROM cad_treinamentos ORDER BY treinamento ASC", conn)
    conn.close()
    lista_trein_cad = df_cad_trein["treinamento"].tolist() if not df_cad_trein.empty else []

    if is_admin:
        if not empresas:
            st.warning("Cadastre empresas para começar a gerenciar os treinamentos.")
        else:
            empresa_sel = st.selectbox("Selecione a Empresa para Cadastro", empresas, key="emp_trein")
            
            conn = sqlite3.connect(DB_NAME)
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(empresa_sel,))
            conn.close()
            
            with st.expander("➕ Inserção de Treinamento para Funcionário", expanded=True):
                if df_funcs.empty:
                    st.warning("Não há funcionários cadastrados para esta empresa. Cadastre funcionários na aba correspondente.")
                else:
                    nomes_lista = sorted(df_funcs["funcionario"].tolist())
                    
                    with st.form("form_inserir_treinamento_detalhado"):
                        func_sel = st.selectbox("Funcionário", nomes_lista)
                        
                        colab = df_funcs[df_funcs["funcionario"] == func_sel].iloc[0]
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            matr_val = st.text_input("Matrícula", value=str(colab['matricula']) if pd.notna(colab['matricula']) else "")
                            cargo_val = st.text_input("Cargo", value=str(colab['cargo']) if pd.notna(colab['cargo']) else "")
                            setor_val = st.text_input("Setor", value=str(colab['setor']) if pd.notna(colab['setor']) else "")
                            treinamento_escolhido = st.selectbox("Tipo de Treinamento", lista_trein_cad if lista_trein_cad else ["Nenhum treinamento cadastrado"])

                        with c2:
                            carga_horaria_val = st.text_input("Carga Horária (Ex: 8h, 16h)")
                            data_realizacao_val = st.text_input("Data de Realização (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                            validade_meses_val = st.number_input("Validade (Meses)", min_value=1, value=12, step=1)
                            proximo_vencimento_val = st.text_input("Próximo Vencimento (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                            status_val = st.selectbox("Status", ["🟢 em dia", "🟠 A Vencer", "🔴 Vencido"])

                        if st.form_submit_button("Salvar Inserção de Treinamento"):
                            if treinamento_escolhido and treinamento_escolhido != "Nenhum treinamento cadastrado":
                                conn_val = sqlite3.connect(DB_NAME)
                                cursor_val = conn_val.cursor()
                                cursor_val.execute("""
                                    SELECT 1 FROM treinamentos 
                                    WHERE empresa = ? AND funcionario = ? AND treinamento = ?
                                """, (empresa_sel, func_sel, treinamento_escolhido))
                                duplicado = cursor_val.fetchone()
                                conn_val.close()

                                if duplicado:
                                    st.error(f"⚠️ Este dado já foi cadastrado! O funcionário '{func_sel}' já possui o treinamento '{treinamento_escolhido}' registrado para a empresa '{empresa_sel}'.")
                                else:
                                    status_limpo = limpar_status_banco(status_val)
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
                                        validar_e_formatar_data_input(data_realizacao_val), 
                                        int(validade_meses_val), 
                                        validar_e_formatar_data_input(proximo_vencimento_val), 
                                        status_limpo
                                    ))
                                    conn.commit()
                                    conn.close()
                                    st.success("Treinamento inserido com sucesso para o funcionário!")
                                    st.rerun()
                            else:
                                st.error("Selecione um tipo de treinamento válido.")

    st.subheader("Treinamentos Registrados")
    
    if is_admin:
        if empresas:
            filtro_empresa_tr = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_tr_emp")
        else:
            filtro_empresa_tr = "Todas as Empresas"
    else:
        filtro_empresa_tr = emp_usuario
        st.info(f"Exibindo dados exclusivos da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)
    if is_admin and filtro_empresa_tr == "Todas as Empresas":
        df_tr = pd.read_sql("SELECT * FROM treinamentos ORDER BY funcionario ASC", conn)
    else:
        emp_busca = filtro_empresa_tr if is_admin else emp_usuario
        df_tr = pd.read_sql("SELECT * FROM treinamentos WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_busca,))
    conn.close()

    if not df_tr.empty:
        colunas_tr_ordem = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "treinamento", "carga_horaria", "data_realizacao", "validade_meses", "proximo_vencimento", "status"]
        colunas_tr_existentes = [c for c in colunas_tr_ordem if c in df_tr.columns]
        df_tr = df_tr[colunas_tr_existentes]
        
        if "data_realizacao" in df_tr.columns:
            df_tr["data_realizacao"] = df_tr["data_realizacao"].apply(formatar_data_br)
        if "proximo_vencimento" in df_tr.columns:
            df_tr["proximo_vencimento"] = df_tr["proximo_vencimento"].apply(formatar_data_br)
        if "status" in df_tr.columns:
            df_tr["status"] = df_tr["status"].apply(lambda x: formatar_status_visual(x, "trein"))

        if is_admin:
            editado_tr = st.data_editor(
                df_tr.drop(columns=["id"]), 
                num_rows="dynamic", 
                key="editor_tr",
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "status",
                        help="Selecione o status do treinamento",
                        options=["🟢 em dia", "🟠 A Vencer", "🔴 Vencido"],
                        required=True
                    ),
                    "data_realizacao": st.column_config.TextColumn(
                        "data_realizacao",
                        help="Formato DD/MM/AAAA",
                        required=True
                    ),
                    "proximo_vencimento": st.column_config.TextColumn(
                        "proximo_vencimento",
                        help="Formato DD/MM/AAAA",
                        required=True
                    )
                },
                use_container_width=True
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                chk_salvar_tr = st.checkbox("⚠️ Confirmo salvar as alterações nos treinamentos", key="chk_salvar_tr")
                if st.button("💾 Salvar Alterações", key="btn_salvar_tr"):
                    if chk_salvar_tr:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        if filtro_empresa_tr == "Todas as Empresas":
                            cursor.execute("DELETE FROM treinamentos")
                        else:
                            cursor.execute("DELETE FROM treinamentos WHERE empresa = ?", (filtro_empresa_tr,))

                        for _, row in editado_tr.iterrows():
                            dt_real_br = validar_e_formatar_data_input(row["data_realizacao"])
                            dt_venc_br = validar_e_formatar_data_input(row["proximo_vencimento"])
                            status_limpo = limpar_status_banco(row["status"])
                            try:
                                val_meses_int = int(row["validade_meses"])
                            except:
                                val_meses_int = 12

                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["treinamento"], row["carga_horaria"], dt_real_br, val_meses_int, dt_venc_br, status_limpo))
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
                        if filtro_empresa_tr == "Todas as Empresas":
                            cursor.execute("DELETE FROM treinamentos")
                        else:
                            cursor.execute("DELETE FROM treinamentos WHERE empresa = ?", (filtro_empresa_tr,))

                        for _, row in editado_tr.iterrows():
                            dt_real_br = validar_e_formatar_data_input(row["data_realizacao"])
                            dt_venc_br = validar_e_formatar_data_input(row["proximo_vencimento"])
                            status_limpo = limpar_status_banco(row["status"])
                            try:
                                val_meses_int = int(row["validade_meses"])
                            except:
                                val_meses_int = 12

                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, validade_meses, proximo_vencimento, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["treinamento"], row["carga_horaria"], dt_real_br, val_meses_int, dt_venc_br, status_limpo))
                        conn.commit()
                        conn.close()
                        st.success("Excluído/atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")
        else:
            st.dataframe(df_tr.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhum treinamento registrado para o filtro selecionado.")

# ==========================================
# 5. EXAMES OCUPACIONAIS
# ==========================================
elif menu == "Exames Ocupacionais":
    st.title("🩺 Controle de Exames Ocupacionais e Periódicos")
    empresas = get_empresas()
    
    if is_admin:
        if not empresas:
            st.warning("Cadastre ao menos uma empresa na aba 'Cadastro de Empresas' ou 'Gestão de Funcionários' primeiro.")
        else:
            empresa_sel = st.selectbox("Selecione a Empresa para Cadastro", empresas, key="ex_emp")
            
            conn = sqlite3.connect(DB_NAME)
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(empresa_sel,))
            conn.close()
            
            if df_funcs.empty:
                st.warning("Não há funcionários cadastrados para esta empresa ainda.")
            else:
                with st.expander("➕ Adicionar Novo Exame", expanded=True):
                    nomes_lista = sorted(df_funcs["funcionario"].tolist())
                    
                    with st.form("form_exame"):
                        nome_sel = st.selectbox("Nome do Funcionário", nomes_lista, key="ex_func")
                        
                        colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                        matr_auto = str(colab['matricula']) if pd.notna(colab['matricula']) else ""
                        carg_auto = str(colab['cargo']) if pd.notna(colab['cargo']) else ""
                        setr_auto = str(colab['setor']) if pd.notna(colab['setor']) else ""

                        c1, c2 = st.columns(2)
                        with c1:
                            ultimo = st.text_input("Data do Último Exame (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"), key="dt_ult")
                            tipo_exame = st.selectbox("Tipo de Exame", sorted(["Admissional", "Periódico", "Retorno ao Trabalho", "Demissional"]), key="tp_ex")
                        with c2:
                            proximo = st.text_input("Data do Próximo Exame (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"), key="dt_prox")
                            status = st.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"], key="st_ex")
                            
                        if st.form_submit_button("Salvar Lançamento de Exame"):
                            status_limpo = limpar_status_banco(status)
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                                VALUES (?,?,?,?,?,?,?,?,?)
                            """, (empresa_sel, matr_auto, nome_sel, carg_auto, setr_auto, validar_e_formatar_data_input(ultimo), tipo_exame, validar_e_formatar_data_input(proximo), status_limpo))
                            conn.commit()
                            conn.close()
                            st.success("Exame salvo com sucesso!")
                            st.rerun()

    st.subheader("Exames Registrados")
    
    if is_admin:
        if empresas:
            filtro_empresa_ex = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ex_emp")
        else:
            filtro_empresa_ex = "Todas as Empresas"
    else:
        filtro_empresa_ex = emp_usuario
        st.info(f"Exibindo dados exclusivos da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)
    if is_admin and filtro_empresa_ex == "Todas as Empresas":
        df_ex = pd.read_sql("SELECT * FROM exames ORDER BY funcionario ASC", conn)
    else:
        emp_busca = filtro_empresa_ex if is_admin else emp_usuario
        df_ex = pd.read_sql("SELECT * FROM exames WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_busca,))
    conn.close()

    if not df_ex.empty:
        if 'empresa' in df_ex.columns:
            df_ex = df_ex[["id", "empresa", "matricula", "funcionario", "cargo", "setor", "ultimo_exame", "tipo_exame", "proximo_exame", "status"]]
        
        if "ultimo_exame" in df_ex.columns:
            df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br)
        if "proximo_exame" in df_ex.columns:
            df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br)
        if "status" in df_ex.columns:
            df_ex["status"] = df_ex["status"].apply(lambda x: formatar_status_visual(x, "ex"))
        
        if is_admin:
            editado_ex = st.data_editor(
                df_ex.drop(columns=["id"]), 
                num_rows="dynamic", 
                key="editor_ex",
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "status",
                        help="Selecione o status do exame",
                        options=["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"],
                        required=True
                    ),
                    "ultimo_exame": st.column_config.TextColumn(
                        "ultimo_exame",
                        help="Formato DD/MM/AAAA",
                        required=True
                    ),
                    "proximo_exame": st.column_config.TextColumn(
                        "proximo_exame",
                        help="Formato DD/MM/AAAA",
                        required=True
                    )
                },
                use_container_width=True
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                chk_salvar_ex = st.checkbox("⚠️ Confirmo salvar as alterações nos exames", key="chk_salvar_ex")
                if st.button("💾 Salvar Alterações", key="btn_salvar_ex"):
                    if chk_salvar_ex:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        if filtro_empresa_ex == "Todas as Empresas":
                            cursor.execute("DELETE FROM exames")
                        else:
                            cursor.execute("DELETE FROM exames WHERE empresa = ?", (filtro_empresa_ex,))

                        for _, row in editado_ex.iterrows():
                            dt_ult_br = validar_e_formatar_data_input(row["ultimo_exame"])
                            dt_prox_br = validar_e_formatar_data_input(row["proximo_exame"])
                            status_limpo = limpar_status_banco(row["status"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], dt_ult_br, row["tipo_exame"], dt_prox_br, status_limpo))
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
                        if filtro_empresa_ex == "Todas as Empresas":
                            cursor.execute("DELETE FROM exames")
                        else:
                            cursor.execute("DELETE FROM exames WHERE empresa = ?", (filtro_empresa_ex,))

                        for _, row in editado_ex.iterrows():
                            dt_ult_br = validar_e_formatar_data_input(row["ultimo_exame"])
                            dt_prox_br = validar_e_formatar_data_input(row["proximo_exame"])
                            status_limpo = limpar_status_banco(row["status"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], dt_ult_br, row["tipo_exame"], dt_prox_br, status_limpo))
                        conn.commit()
                        conn.close()
                        st.success("Excluído/atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")
        else:
            st.dataframe(df_ex.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhum exame registrado para o filtro selecionado.")

# ==========================================
# 6. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
    st.title("🦺 Controle de Equipamentos de Proteção Individual (EPI)")
    
    empresas = get_empresas()

    if is_admin:
        if not empresas:
            st.warning("Cadastre empresas para começar a gerenciar os EPIs.")
        else:
            empresa_sel = st.selectbox("Selecione a Empresa para Cadastro", empresas, key="emp_epi")
            
            conn_e = sqlite3.connect(DB_NAME)
            df_e_emp = pd.read_sql("SELECT epi, ca FROM cad_epis WHERE empresa = ? ORDER BY epi ASC", conn_e, params=(empresa_sel,))
            conn_e.close()
            
            lista_epis_emp = df_e_emp["epi"].tolist() if not df_e_emp.empty else []
            mapa_ca_epis = dict(zip(df_e_emp["epi"], df_e_emp["ca"])) if not df_e_emp.empty else {}

            conn = sqlite3.connect(DB_NAME)
            df_funcs = pd.read_sql("SELECT * FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(empresa_sel,))
            conn.close()
            
            with st.expander("➕ Registrar Entrega de EPI", expanded=True):
                if df_funcs.empty:
                    st.warning("Não há funcionários cadastrados para esta empresa.")
                elif not lista_epis_emp:
                    st.warning("Não há EPIs cadastrados para esta empresa. Cadastre-os na aba 'Cadastros Gerais'.")
                else:
                    nomes_lista = sorted(df_funcs["funcionario"].tolist())
                    
                    with st.form("form_epi"):
                        c1, c2 = st.columns(2)
                        with c1:
                            nome_sel = st.selectbox("Nome do Funcionário", nomes_lista, key="func_epi")
                            
                            colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                            matr_auto = st.text_input("Matrícula", value=str(colab['matricula']) if pd.notna(colab['matricula']) else "")
                            carg_auto = st.text_input("Cargo", value=str(colab['cargo']) if pd.notna(colab['cargo']) else "")
                            setr_auto = st.text_input("Setor", value=str(colab['setor']) if pd.notna(colab['setor']) else "")
                            epi_sel = st.selectbox("Equipamento (EPI)", lista_epis_emp)

                        with c2:
                            ca_sugerido = mapa_ca_epis.get(epi_sel, "")
                            ca_epi = st.text_input("Número do CA", value=ca_sugerido)
                            data_entrega = st.text_input("Data da Entrega (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"), key="dt_ent_epi")
                            qtd = st.number_input("Quantidade", min_value=1, value=1, key="qtd_epi")
                            status_epi = st.selectbox("Status de Entrega", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"], key="st_epi")
                            
                        if st.form_submit_button("Salvar Registro de EPI"):
                            status_limpo = limpar_status_banco(status_epi)
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                                VALUES (?,?,?,?,?,?,?,?,?,?)
                            """, (empresa_sel, matr_auto, nome_sel, carg_auto, setr_auto, epi_sel, ca_epi, validar_e_formatar_data_input(data_entrega), int(qtd), status_limpo))
                            conn.commit()
                            conn.close()
                            st.success("EPI registrado com sucesso!")
                            st.rerun()

    st.subheader("EPIs Registrados")
    
    if is_admin:
        if empresas:
            filtro_empresa_ep = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ep_emp")
        else:
            filtro_empresa_ep = "Todas as Empresas"
    else:
        filtro_empresa_ep = emp_usuario
        st.info(f"Exibindo dados exclusivos da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)
    if is_admin and filtro_empresa_ep == "Todas as Empresas":
        df_ep = pd.read_sql("SELECT * FROM epis ORDER BY funcionario ASC", conn)
    else:
        emp_busca = filtro_empresa_ep if is_admin else emp_usuario
        df_ep = pd.read_sql("SELECT * FROM epis WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_busca,))
    conn.close()

    if not df_ep.empty:
        colunas_ep_ordem = ["id", "empresa", "matricula", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]
        colunas_ep_existentes = [c for c in colunas_ep_ordem if c in df_ep.columns]
        df_ep = df_ep[colunas_ep_existentes]
        
        if "data_entrega" in df_ep.columns:
            df_ep["data_entrega"] = df_ep["data_entrega"].apply(formatar_data_br)
        if "status" in df_ep.columns:
            df_ep["status"] = df_ep["status"].apply(lambda x: formatar_status_visual(x, "epi"))

        if is_admin:
            editado_ep = st.data_editor(
                df_ep.drop(columns=["id"]), 
                num_rows="dynamic", 
                key="editor_ep",
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "status",
                        help="Selecione o status do EPI",
                        options=["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"],
                        required=True
                    ),
                    "data_entrega": st.column_config.TextColumn(
                        "data_entrega",
                        help="Formato DD/MM/AAAA",
                        required=True
                    )
                },
                use_container_width=True
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                chk_salvar_ep = st.checkbox("⚠️ Confirmo salvar as alterações nos EPIs", key="chk_salvar_ep")
                if st.button("💾 Salvar Alterações", key="btn_salvar_ep"):
                    if chk_salvar_ep:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        if filtro_empresa_ep == "Todas as Empresas":
                            cursor.execute("DELETE FROM epis")
                        else:
                            cursor.execute("DELETE FROM epis WHERE empresa = ?", (filtro_empresa_ep,))

                        for _, row in editado_ep.iterrows():
                            dt_ent_br = validar_e_formatar_data_input(row["data_entrega"])
                            status_limpo = limpar_status_banco(row["status"])
                            try:
                                qtd_int = int(row["quantidade"])
                            except:
                                qtd_int = 1

                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["epi"], row["ca"], dt_ent_br, qtd_int, status_limpo))
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
                        if filtro_empresa_ep == "Todas as Empresas":
                            cursor.execute("DELETE FROM epis")
                        else:
                            cursor.execute("DELETE FROM epis WHERE empresa = ?", (filtro_empresa_ep,))

                        for _, row in editado_ep.iterrows():
                            dt_ent_br = validar_e_formatar_data_input(row["data_entrega"])
                            status_limpo = limpar_status_banco(row["status"])
                            try:
                                qtd_int = int(row["quantidade"])
                            except:
                                qtd_int = 1

                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) 
                                    VALUES (?,?,?,?,?,?,?,?,?,?)
                                """, (row["empresa"], row["matricula"], row["funcionario"], row["cargo"], row["setor"], row["epi"], row["ca"], dt_ent_br, qtd_int, status_limpo))
                        conn.commit()
                        conn.close()
                        st.success("Excluído/atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")
        else:
            st.dataframe(df_ep.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhum EPI registrado para o filtro selecionado.")

# ==========================================
# 7. SERVIÇOS REALIZADOS
# ==========================================
elif menu == "Serviços Realizados":
    st.title("🛠️ Controle de Serviços Realizados")
    
    if is_admin:
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
    df_cad_serv = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
    conn.close()
    lista_serv_cad = df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []

    if is_admin:
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
                            data_realizacao_srv = st.text_input("Data de Realização (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                        with c2:
                            responsavel_srv = st.text_input("Responsável Técnico / Instrutor", value="Luiz Marcelo Fontana")
                            status_srv = st.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"])
                            observacoes_srv = st.text_input("Observações / Detalhes do Serviço")
                            
                        if st.form_submit_button("Salvar Registro de Serviço"):
                            status_limpo = limpar_status_banco(status_srv)
                            conn = sqlite3.connect(DB_NAME)
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                                VALUES (?,?,?,?,?,?)
                            """, (
                                empresa_sel_srv, 
                                servico_sel, 
                                validar_e_formatar_data_input(data_realizacao_srv), 
                                responsavel_srv, 
                                observacoes_srv, 
                                status_limpo
                            ))
                            conn.commit()
                            conn.close()
                            st.success("Serviço registrado com sucesso!")
                            st.rerun()

    st.subheader("Serviços Registrados")
    
    if is_admin:
        if empresas:
            filtro_empresa_srv = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_srv_emp")
        else:
            filtro_empresa_srv = "Todas as Empresas"
    else:
        filtro_empresa_srv = emp_usuario
        st.info(f"Exibindo dados exclusivos da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)
    if is_admin and filtro_empresa_srv == "Todas as Empresas":
        df_serv = pd.read_sql("SELECT * FROM servicos_realizados ORDER BY empresa ASC", conn)
    else:
        emp_busca = filtro_empresa_srv if is_admin else emp_usuario
        df_serv = pd.read_sql("SELECT * FROM servicos_realizados WHERE empresa = ? ORDER BY empresa ASC", conn, params=(emp_busca,))
    conn.close()

    if not df_serv.empty:
        colunas_serv_ordem = ["id", "empresa", "servico", "data_realizacao", "responsavel", "observacoes", "status"]
        colunas_serv_existentes = [c for c in colunas_serv_ordem if c in df_serv.columns]
        df_serv = df_serv[colunas_serv_existentes]
        
        if "data_realizacao" in df_serv.columns:
            df_serv["data_realizacao"] = df_serv["data_realizacao"].apply(formatar_data_br)
        if "status" in df_serv.columns:
            df_serv["status"] = df_serv["status"].apply(lambda x: formatar_status_visual(x, "serv"))

        if is_admin:
            editado_serv = st.data_editor(
                df_serv.drop(columns=["id"]), 
                num_rows="dynamic", 
                key="editor_serv",
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "status",
                        help="Selecione o status do serviço",
                        options=["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"],
                        required=True
                    ),
                    "data_realizacao": st.column_config.TextColumn(
                        "data_realizacao",
                        help="Formato DD/MM/AAAA",
                        required=True
                    )
                },
                use_container_width=True
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                chk_salvar_serv = st.checkbox("⚠️ Confirmo salvar as alterações nos serviços", key="chk_salvar_serv")
                if st.button("💾 Salvar Alterações", key="btn_salvar_serv"):
                    if chk_salvar_serv:
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        if filtro_empresa_srv == "Todas as Empresas":
                            cursor.execute("DELETE FROM servicos_realizados")
                        else:
                            cursor.execute("DELETE FROM servicos_realizados WHERE empresa = ?", (filtro_empresa_srv,))

                        for _, row in editado_serv.iterrows():
                            dt_br = validar_e_formatar_data_input(row["data_realizacao"])
                            status_limpo = limpar_status_banco(row["status"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                                    VALUES (?,?,?,?,?,?)
                                """, (row["empresa"], row["servico"], dt_br, row["responsavel"], row["observacoes"], status_limpo))
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
                        if filtro_empresa_srv == "Todas as Empresas":
                            cursor.execute("DELETE FROM servicos_realizados")
                        else:
                            cursor.execute("DELETE FROM servicos_realizados WHERE empresa = ?", (filtro_empresa_srv,))

                        for _, row in editado_serv.iterrows():
                            dt_br = validar_e_formatar_data_input(row["data_realizacao"])
                            status_limpo = limpar_status_banco(row["status"])
                            cursor.execute("SELECT 1 FROM empresas WHERE nome_empresa = ?", (row["empresa"],))
                            if cursor.fetchone():
                                cursor.execute("""
                                    INSERT INTO servicos_realizados (empresa, servico, data_realizacao, responsavel, observacoes, status) 
                                    VALUES (?,?,?,?,?,?)
                                """, (row["empresa"], row["servico"], dt_br, row["responsavel"], row["observacoes"], status_limpo))
                        conn.commit()
                        conn.close()
                        st.success("Excluído/atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Marque a caixa de confirmação para excluir.")
        else:
            st.dataframe(df_serv.drop(columns=["id"]), use_container_width=True)
            st.info("🔒 Visualização restrita (Somente Leitura).")
    else:
        st.info("Nenhum serviço registrado para o filtro selecionado.")

# ==========================================
# 8. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    st.title("🛠️ Painel Administrativo e Backup")
    if not is_admin:
        st.warning("🔒 Área exclusiva para o Administrador.")
    else:
        st.markdown("Baixe o arquivo do banco de dados para segurança do seu negócio:")
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 Baixar Backup (.db)", f, file_name="cassilab_gestao.db", mime="application/octet-stream")

        st.markdown("---")
        st.subheader("👥 Gerenciamento de Cadastros de Usuários (Reset / Exclusão)")
        st.markdown("Visualize os usuários cadastrados e remova o acesso caso alguém precise refazer o cadastro:")

        conn = sqlite3.connect(DB_NAME)
        df_users = pd.read_sql("SELECT id, nome, cpf, empresa, email, celular FROM usuarios_sistema ORDER BY nome ASC", conn)
        conn.close()

        if not df_users.empty:
            if "cpf" in df_users.columns:
                df_users["cpf"] = df_users["cpf"].apply(formatar_cpf)
            st.dataframe(df_users, use_container_width=True)
            
            with st.form("form_reset_user"):
                cpf_para_remover = st.text_input("Digite o CPF do usuário que deseja remover/resetar o acesso", value="", autocomplete="off")
                chk_confirma_reset = st.checkbox("⚠️ Confirmo que desejo apagar o cadastro deste usuário permitindo que ele refaça o acesso")
                btn_executar_reset = st.form_submit_button("🗑️ Excluir Cadastro de Usuário")

                if btn_executar_reset:
                    if chk_confirma_reset and cpf_para_remover.strip():
                        cpf_fmt_rem = formatar_cpf(cpf_para_remover)
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM usuarios_sistema WHERE cpf = ?", (cpf_fmt_rem,))
                        conn.commit()
                        conn.close()
                        st.success(f"Cadastro com o CPF {cpf_fmt_rem} removido com sucesso! O usuário já pode refazer o cadastro.")
                        st.rerun()
                    else:
                        st.error("CPF e confirmação obrigatórios.")
        else:
            st.info("Nenhum usuário cadastrado no sistema além do administrador.")

        st.markdown("---")
        st.subheader("🧹 Limpeza Geral de Registros Órfãos")
        st.markdown("Caso alguma empresa fantasma tenha retornado, utilize o botão abaixo para purgar permanentemente todos os registros vinculados a empresas que já foram deletadas:")
        
        chk_limpeza_orfas = st.checkbox("Confirmo a limpeza de dados órfãos do sistema")
        if st.button("🧹 Executar Varredura e Limpeza Definitiva"):
            if chk_limpeza_orfas:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM base_funcionarios WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM exames WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM treinamentos WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM epis WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM servicos_realizados WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM cad_cargos WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                cursor.execute("DELETE FROM cad_epis WHERE empresa NOT IN (SELECT nome_empresa FROM empresas)")
                conn.commit()
                conn.close()
                st.success("Varredura concluída! Todos os registros órfãos e empresas deletadas foram purgados em definitivo.")
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
    if is_admin:
        empresa_filtro = st.selectbox("Filtrar por Empresa Específica (Opcional)", ["Todas as Empresas"] + empresas)
    else:
        empresa_filtro = emp_usuario
        st.info(f"Relatório restrito aos dados da empresa: **{emp_usuario}**")

    conn = sqlite3.connect(DB_NAME)

    if inc_func:
        st.subheader("👥 Relatório de Funcionários")
        try:
            if is_admin and empresa_filtro == "Todas as Empresas":
                df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios ORDER BY funcionario ASC", conn)
            else:
                emp_b = empresa_filtro if is_admin else emp_usuario
                df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_b,))
            
            if not df_f.empty:
                if "data_admissao" in df_f.columns:
                    df_f["data_admissao"] = df_f["data_admissao"].apply(formatar_data_br)
                if "cpf" in df_f.columns:
                    df_f["cpf"] = df_f["cpf"].apply(formatar_cpf)
                if "status" in df_f.columns:
                    df_f["status"] = df_f["status"].apply(lambda x: formatar_status_visual(x, "func"))
            st.dataframe(df_f, use_container_width=True)
        except:
            st.info("Nenhum dado de funcionários encontrado.")

    if inc_ex:
        st.subheader("🩺 Relatório de Exames Ocupacionais")
        try:
            if is_admin and empresa_filtro == "Todas as Empresas":
                df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames ORDER BY funcionario ASC", conn)
            else:
                emp_b = empresa_filtro if is_admin else emp_usuario
                df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_b,))
            if not df_e.empty:
                if "ultimo_exame" in df_e.columns:
                    df_e["ultimo_exame"] = df_e["ultimo_exame"].apply(formatar_data_br)
                if "proximo_exame" in df_e.columns:
                    df_e["proximo_exame"] = df_e["proximo_exame"].apply(formatar_data_br)
                if "status" in df_e.columns:
                    df_e["status"] = df_e["status"].apply(lambda x: formatar_status_visual(x, "ex"))
            st.dataframe(df_e, use_container_width=True)
        except:
            st.info("Nenhum dado de exames encontrado.")

    if inc_tr:
        st.subheader("📚 Relatório de Treinamentos")
        try:
            if is_admin and empresa_filtro == "Todas as Empresas":
                df_t = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, proximo_vencimento, status FROM treinamentos ORDER BY funcionario ASC", conn)
            else:
                emp_b = empresa_filtro if is_admin else emp_usuario
                df_t = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, data_realizacao, proximo_vencimento, status FROM treinamentos WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_b,))
            if not df_t.empty:
                if "data_realizacao" in df_t.columns:
                    df_t["data_realizacao"] = df_t["data_realizacao"].apply(formatar_data_br)
                if "proximo_vencimento" in df_t.columns:
                    df_t["proximo_vencimento"] = df_t["proximo_vencimento"].apply(formatar_data_br)
                if "status" in df_t.columns:
                    df_t["status"] = df_t["status"].apply(lambda x: formatar_status_visual(x, "trein"))
            st.dataframe(df_t, use_container_width=True)
        except:
            st.info("Nenhum dado de treinamentos encontrado.")

    if inc_ep:
        st.subheader("🦺 Relatório de Entrega de EPIs")
        try:
            if is_admin and empresa_filtro == "Todas as Empresas":
                df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis ORDER BY funcionario ASC", conn)
            else:
                emp_b = empresa_filtro if is_admin else emp_usuario
                df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_b,))
            if not df_p.empty:
                if "data_entrega" in df_p.columns:
                    df_p["data_entrega"] = df_p["data_entrega"].apply(formatar_data_br)
                if "status" in df_p.columns:
                    df_p["status"] = df_p["status"].apply(lambda x: formatar_status_visual(x, "epi"))
            st.dataframe(df_p, use_container_width=True)
        except:
            st.info("Nenhum dado de EPIs encontrado.")

    if inc_srv:
        st.subheader("🛠️ Relatório de Serviços Realizados")
        try:
            if is_admin and empresa_filtro == "Todas as Empresas":
                df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, status FROM servicos_realizados ORDER BY empresa ASC", conn)
            else:
                emp_b = empresa_filtro if is_admin else emp_usuario
                df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, status FROM servicos_realizados WHERE empresa = ? ORDER BY empresa ASC", conn, params=(emp_b,))
            if not df_s.empty:
                if "data_realizacao" in df_s.columns:
                    df_s["data_realizacao"] = df_s["data_realizacao"].apply(formatar_data_br)
                if "status" in df_s.columns:
                    df_s["status"] = df_s["status"].apply(lambda x: formatar_status_visual(x, "serv"))
            st.dataframe(df_s, use_container_width=True)
        except:
            st.info("Nenhum dado de serviços encontrado.")

    conn.close()