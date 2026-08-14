import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from fpdf import FPDF
import os

st.set_page_config(page_title="SST - Cassilab", layout="wide")
DB_NAME = "cassilab.db"

# --- Inicialização do Banco de Dados e Tabelas ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Contato_Tel TEXT, Contato_Nome TEXT, CNPJ TEXT, Qtd_Func INTEGER, Endereco TEXT, Bairro TEXT, CEP TEXT, Cidade_UF TEXT, Email TEXT, Data_Cadastro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Matricula TEXT, Nome TEXT, Cargo TEXT, Setor TEXT, CPF TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Treinamento TEXT, Carga_Horaria TEXT, Data TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, EMPRESA TEXT, Data TEXT, Documento_Programa TEXT, Vencimento TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS exames (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Funcionario TEXT, Exame TEXT, Data TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, EMPRESA TEXT, Data TEXT, Serviço_executado TEXT, Valor_do_Serviço REAL, NFES TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cargos (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Cargo TEXT)''')
    
    # Tabela de Usuários do Sistema
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Nome TEXT, CPF TEXT, Email TEXT, Senha TEXT)''')
    
    try:
        cursor.execute("ALTER TABLE treinamentos ADD COLUMN Carga_Horaria TEXT")
    except:
        pass

    conn.commit(); conn.close()

init_db()

# --- Sistema de Autenticação e Cadastro ---
def tela_autenticacao():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.sidebar.title("🔐 Acesso ao Sistema")
        modo = st.sidebar.radio("Escolha:", ["Entrar (Login)", "Cadastrar Novo Usuário"])

        if modo == "Entrar (Login)":
            st.title("🔐 Entrar no Sistema - Cassilab SST")
            with st.form("form_login"):
                email_login = st.text_input("E-mail, CPF ou Usuário")
                senha_login = st.text_input("Senha", type="password")
                botao_login = st.form_submit_button("Entrar")
                
                if botao_login:
                    # Validação do Admin Principal
                    if email_login == "admin" and senha_login == "Disc@5232":
                        st.session_state.autenticado = True
                        st.session_state.usuario_logado = "Administrador"
                        st.success("Acesso administrativo realizado com sucesso!")
                        st.rerun()
                    else:
                        # Validação de usuários cadastrados no banco
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM usuarios WHERE (Email = ? OR CPF = ?) AND Senha = ?", (email_login, email_login, senha_login))
                        usuario = cursor.fetchone()
                        conn.close()
                        
                        if usuario:
                            st.session_state.autenticado = True
                            st.session_state.usuario_logado = email_login
                            st.success("Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Credenciais inválidas. Verifique seus dados ou faça o cadastro.")

        elif modo == "Cadastrar Novo Usuário":
            st.title("📝 Cadastro de Novo Usuário")
            st.info("Para se cadastrar, a empresa e seus dados já devem estar cadastrados no sistema.")
            
            with st.form("form_cadastro_usuario"):
                empresa_cad = st.text_input("Nome exato da Empresa cadastrada")
                nome_cad = st.text_input("Seu Nome Completo")
                cpf_cad = st.text_input("Seu CPF")
                email_cad = st.text_input("Seu E-mail")
                senha_cad = st.text_input("Crie uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                
                botao_cadastrar = st.form_submit_button("Finalizar Cadastro")
                
                if botao_cadastrar:
                    if not empresa_cad or not nome_cad or not cpf_cad or not email_cad or not senha_cad:
                        st.error("Todos os campos são obrigatórios!")
                    elif senha_cad != confirma_senha:
                        st.error("As senhas não coincidem!")
                    else:
                        conn = sqlite3.connect(DB_NAME)
                        df_emp = pd.read_sql("SELECT * FROM empresas WHERE Empresa = ?", conn, params=(empresa_cad,))
                        
                        if df_emp.empty:
                            st.error(f"A empresa '{empresa_cad}' não está cadastrada no sistema.")
                            conn.close()
                        else:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO usuarios (Empresa, Nome, CPF, Email, Senha) VALUES (?, ?, ?, ?, ?)", 
                                           (empresa_cad, nome_cad, cpf_cad, email_cad, senha_cad))
                            conn.commit()
                            conn.close()
                            st.success("Cadastro realizado com sucesso! Alterne para a aba 'Entrar (Login)' para acessar.")
        return False
    return True

# --- Funções Auxiliares ---
def formatar_tabela(df, tipo="padrao"):
    if not df.empty:
        df_ex = df.copy()
        if 'CNPJ' in df_ex.columns: 
            df_ex = df_ex.rename(columns={'CNPJ': 'CNPJ/CPF'})
        
        # Reposicionar Data_Cadastro antes de Empresa na aba de Empresas
        if tipo == "empresas" and all(col in df_ex.columns for col in ['Data_Cadastro', 'Empresa']):
            cols_atuais = list(df_ex.columns)
            cols_atuais.remove('Data_Cadastro')
            idx_empresa = cols_atuais.index('Empresa')
            cols_atuais.insert(idx_empresa, 'Data_Cadastro')
            df_ex = df_ex[cols_atuais]

        # Reordenar colunas para a aba de Treinamentos (Carga_Horaria rigorosamente à esquerda de Data)
        if tipo == "treinamentos" and all(col in df_ex.columns for col in ['Carga_Horaria', 'Data']):
            cols_atuais = list(df_ex.columns)
            cols_atuais.remove('Carga_Horaria')
            idx_data = cols_atuais.index('Data')
            cols_atuais.insert(idx_data, 'Carga_Horaria')
            df_ex = df_ex[cols_atuais]

        df_ex.index = range(1, len(df_ex) + 1)
        return df_ex
    return df

def criar_grafico_rosca(titulo, executado, meta):
    falta = max(0, meta - executado)
    porcentagem = int((executado / meta * 100)) if meta > 0 else 0
    fig = go.Figure(data=[go.Pie(labels=['Executado', 'Faltante'], values=[executado, falta], hole=.7, marker_colors=['#6366f1', '#e2e8f0'], textinfo='none')])
    fig.update_layout(title_text=titulo, title_x=0.5, showlegend=False, annotations=[dict(text=f"{porcentagem}%", x=0.5, y=0.5, font_size=14, showarrow=False)], height=200, margin=dict(t=30, b=10, l=10, r=10))
    return fig

def get_data():
    conn = sqlite3.connect(DB_NAME)
    df_e = pd.read_sql("SELECT * FROM empresas", conn)
    df_f = pd.read_sql("SELECT * FROM funcionarios", conn)
    df_t = pd.read_sql("SELECT * FROM treinamentos", conn)
    df_d = pd.read_sql("SELECT * FROM documentos", conn)
    df_ex = pd.read_sql("SELECT * FROM exames", conn)
    df_s = pd.read_sql("SELECT * FROM servicos", conn)
    conn.close()
    return df_e, df_f, df_t, df_d, df_ex, df_s

# --- Execução Principal Protegida por Login ---
if tela_autenticacao():
    df_e, df_f, df_t, df_d, df_ex, df_s = get_data()

    # --- Interface ---
    if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Escolha:", ["Painel", "🏢 Empresas (Central de Gestão)", "➕ Cadastrar Nova Empresa"])
    
    if st.sidebar.button("🚪 Sair / Logout"):
        st.session_state.autenticado = False
        st.rerun()

    st.title("Sistema para Gestão em Saúde e Segurança do Trabalho")

    if menu == "Painel":
        st.subheader("📊 Painel Geral de Controle & Indicadores")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Empresas", len(df_e)); c2.metric("Funcionários", len(df_f)); c3.metric("Documentos", len(df_d)); c4.metric("Exames", len(df_ex))
        
        st.markdown("---")
        st.subheader("🚨 Alertas e Status Operacionais")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("#### 📚 Treinamentos")
            r = len(df_t[df_t['Status'] == 'Realizado']) if not df_t.empty else 0
            p = len(df_t[df_t['Status'] != 'Realizado']) if not df_t.empty else 0
            st.metric("Realizados", r); st.metric("Pendentes", p)
            if not df_t.empty: st.plotly_chart(criar_grafico_rosca("Treinamentos", r, r+p), use_container_width=True)
        with col_b:
            st.markdown("#### 🩺 Exames")
            a = len(df_ex[df_ex['Status'] == 'APTO']) if not df_ex.empty else 0
            pend = len(df_ex[df_ex['Status'] != 'APTO']) if not df_ex.empty else 0
            st.metric("Em Dia", a); st.metric("Pendentes", pend)
            if not df_ex.empty: st.plotly_chart(criar_grafico_rosca("Exames", a, a+pend), use_container_width=True)
        with col_c:
            st.markdown("#### 📄 Documentos")
            v = len(df_d[df_d['Status'] == 'Vigente']) if not df_d.empty else 0
            venc = len(df_d[df_d['Status'] != 'Vigente']) if not df_d.empty else 0
            st.metric("Vigentes", v); st.metric("Vencidos", venc)
            if not df_d.empty: st.plotly_chart(criar_grafico_rosca("Documentos", v, v+venc), use_container_width=True)

    elif menu == "➕ Cadastrar Nova Empresa":
        st.subheader("🏢 Cadastro de Nova Empresa")
        with st.form("form_cad", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nome da Empresa")
            cnpj = c2.text_input("CNPJ/CPF")
            contato = c1.text_input("Nome do Contato")
            tel = c2.text_input("Telefone")
            email = c1.text_input("E-mail")
            qtd = c2.number_input("Qtd de Funcionários", min_value=0)
            end = c1.text_input("Endereço")
            bairro = c2.text_input("Bairro")
            cep = c1.text_input("CEP")
            cidade = c2.text_input("Cidade/UF")
            if st.form_submit_button("Salvar Empresa"):
                conn = sqlite3.connect(DB_NAME)
                conn.execute("INSERT INTO empresas (Empresa, Contato_Tel, Contato_Nome, CNPJ, Qtd_Func, Endereco, Bairro, CEP, Cidade_UF, Email, Data_Cadastro) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                             (n, tel, contato, cnpj, qtd, end, bairro, cep, cidade, email, datetime.now().strftime('%d/%m/%Y')))
                conn.commit(); conn.close(); st.rerun()

    elif menu == "🏢 Empresas (Central de Gestão)":
        if not df_e.empty:
            emp = st.selectbox("Selecione a Empresa:", sorted(df_e['Empresa'].unique().tolist()))
            tabs = st.tabs(["🏢 Empresas", "👥 Funcionários", "📚 Treinamentos", "📄 Documentos", "🩺 Exames", "🛠️ Serviços"])
            
            with tabs[0]: 
                st.dataframe(formatar_tabela(df_e[df_e['Empresa'] == emp], tipo="empresas"), use_container_width=True)
                with st.expander("✏️ Editar Empresa"):
                    st.info("Ferramenta de edição de empresa selecionada.")
            
            with tabs[1]:
                st.subheader("Relação de Funcionários")
                st.dataframe(formatar_tabela(df_f[df_f['Empresa'] == emp]), use_container_width=True)
                with st.expander("➕ Cadastrar Novo Funcionário"):
                    with st.form("cad_f", clear_on_submit=True):
                        nome = st.text_input("Nome"); mat = st.text_input("Matrícula")
                        conn = sqlite3.connect(DB_NAME)
                        cargos_op = pd.read_sql(f"SELECT Cargo FROM cargos WHERE Empresa = '{emp}'", conn)['Cargo'].tolist()
                        conn.close()
                        cargo = st.selectbox("Cargo", cargos_op if cargos_op else ["Cadastre cargo abaixo"])
                        if st.form_submit_button("Salvar"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO funcionarios (Empresa, Nome, Cargo, Matricula) VALUES (?,?,?,?)", (emp, nome, cargo, mat))
                            conn.commit(); conn.close(); st.rerun()
                with st.expander("⚙️ Gerenciar Cargos"):
                    novo_c = st.text_input("Novo Cargo")
                    if st.button("Salvar Cargo"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO cargos (Empresa, Cargo) VALUES (?,?)", (emp, novo_c))
                        conn.commit(); conn.close(); st.rerun()
                with st.expander("✏️ Editar Funcionário"):
                    st.info("Ferramenta de edição de funcionário.")

            with tabs[2]:
                st.subheader("Treinamentos")
                st.dataframe(formatar_tabela(df_t[df_t['Empresa'] == emp], tipo="treinamentos"), use_container_width=True)
                with st.expander("➕ Registrar Treinamento"):
                    with st.form("cad_t", clear_on_submit=True):
                        t = st.text_input("Nome Treinamento")
                        ch = st.text_input("Carga Horária (ex: 8h)")
                        d = st.date_input("Data")
                        if st.form_submit_button("Salvar"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO treinamentos (Empresa, Treinamento, Carga_Horaria, Data, Status) VALUES (?,?,?,?,?)", (emp, t, ch, d.strftime('%d/%m/%Y'), 'Pendente'))
                            conn.commit(); conn.close(); st.rerun()
                with st.expander("✏️ Editar Treinamento"):
                    st.info("Ferramenta de edição de treinamento.")

            with tabs[3]:
                st.subheader("Documentos")
                st.dataframe(formatar_tabela(df_d[df_d['EMPRESA'] == emp]), use_container_width=True)
                with st.expander("➕ Registrar Documento"):
                    with st.form("cad_d", clear_on_submit=True):
                        doc = st.text_input("Nome Documento"); d = st.date_input("Data")
                        if st.form_submit_button("Salvar"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO documentos (EMPRESA, Data, Documento_Programa, Status) VALUES (?,?,?,?)", (emp, d.strftime('%d/%m/%Y'), doc, 'Vigente'))
                            conn.commit(); conn.close(); st.rerun()
                with st.expander("✏️ Editar Documento"):
                    st.info("Ferramenta de edição de documento.")

            with tabs[4]:
                st.subheader("Exames")
                st.dataframe(formatar_tabela(df_ex[df_ex['Empresa'] == emp]), use_container_width=True)
                with st.expander("➕ Registrar Exame"):
                    with st.form("cad_ex", clear_on_submit=True):
                        ex = st.text_input("Exame"); d = st.date_input("Data")
                        if st.form_submit_button("Salvar"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO exames (Empresa, Exame, Data, Status) VALUES (?,?,?,?)", (emp, ex, d.strftime('%d/%m/%Y'), 'APTO'))
                            conn.commit(); conn.close(); st.rerun()
                with st.expander("✏️ Editar Exame"):
                    st.info("Ferramenta de edição de exame.")

            with tabs[5]:
                st.subheader("Serviços")
                st.dataframe(formatar_tabela(df_s[df_s['EMPRESA'] == emp]), use_container_width=True)
                with st.expander("➕ Registrar Serviço"):
                    with st.form("cad_s", clear_on_submit=True):
                        serv = st.text_input("Serviço"); d = st.date_input("Data")
                        if st.form_submit_button("Salvar"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("INSERT INTO servicos (EMPRESA, Data, Serviço_executado) VALUES (?,?,?)", (emp, d.strftime('%d/%m/%Y'), serv))
                            conn.commit(); conn.close(); st.rerun()
                with st.expander("✏️ Editar Serviço"):
                    st.info("Ferramenta de edição de serviço.")
