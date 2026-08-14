import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, date
from fpdf import FPDF

st.set_page_config(page_title="SST - Cassilab", layout="wide")
DB_NAME = "cassilab.db"

# --- Inicialização ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Contato_Tel TEXT, Contato_Nome TEXT, CNPJ TEXT, Qtd_Func INTEGER, Endereco TEXT, Bairro TEXT, CEP TEXT, Cidade_UF TEXT, Email TEXT, Data_Cadastro TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Matricula TEXT, Nome TEXT, Cargo TEXT, Setor TEXT, CPF TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Treinamento TEXT, Data TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, EMPRESA TEXT, Data TEXT, Documento_Programa TEXT, Vencimento TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS exames (id INTEGER PRIMARY KEY AUTOINCREMENT, Empresa TEXT, Funcionario TEXT, Exame TEXT, Data TEXT, Status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, EMPRESA TEXT, Data TEXT, Serviço_executado TEXT, Valor_do_Serviço REAL, NFES TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- Leitura ---
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

# --- PDF ---
def gerar_pdf_paisagem(emp, inc_emp, inc_func, inc_trein, inc_ex, df_e, df_f, df_t, df_exames):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(277, 10, txt=f"RELATORIO GERAL: {emp.upper()}", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(277, 6, txt=f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(5)
    
    if inc_emp:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Dados Cadastrais:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_e[df_e['Empresa'].astype(str).str.strip() == str(emp).strip()]
        for _, row in dados.iterrows():
            pdf.cell(277, 6, txt=f"CNPJ: {row.get('CNPJ', '-')} | Contato: {row.get('Contato_Nome', '-')} | Tel: {row.get('Contato_Tel', '-')}", ln=True)
        pdf.ln(5)

    if inc_func:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Relação de Funcionários:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_f[df_f['Empresa'].astype(str).str.strip() == str(emp).strip()]
        for _, row in dados.iterrows():
            pdf.cell(277, 6, txt=f"Nome: {row.get('Nome', '-')} | Cargo: {row.get('Cargo', '-')} | Setor: {row.get('Setor', '-')}", ln=True)
        pdf.ln(5)
        
    return pdf.output(dest='S').encode('latin-1')

# --- Interface ---
df_e, df_f, df_t, df_d, df_ex, df_s = get_data()

st.sidebar.title("Navegação")
menu = st.sidebar.radio("Escolha:", ["Painel", "🏢 Empresas (Central de Gestão)"])
st.title("SISTEMA CASSILAB - VERSÃO ATUALIZADA")

if menu == "Painel":
    st.subheader("📊 Painel Geral de Controle")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Empresas", len(df_e))
    col2.metric("Funcionários", len(df_f))
    col3.metric("Documentos", len(df_d))
    col4.metric("Exames", len(df_ex))

elif menu == "🏢 Empresas (Central de Gestão)":
    if not df_e.empty:
        emp_escolhida = st.selectbox("Selecione a Empresa:", sorted(df_e['Empresa'].unique().tolist()))
        tabs = st.tabs(["🏢 Empresas", "👥 Funcionários", "📚 Treinamentos", "📄 Documentos", "🩺 Exames", "🛠️ Serviços", "📊 Dashboard", "🖨️ Relatórios"])
        
        with tabs[1]:
            st.dataframe(df_f[df_f['Empresa'] == emp_escolhida], use_container_width=True)
            with st.expander("➕ Cadastrar Novo Funcionário"):
                with st.form("c_func", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Nome do Funcionário")
                    mat = c2.text_input("Matrícula")
                    cargo = c1.text_input("Cargo") # CORRIGIDO AQUI
                    setor = c2.text_input("Setor")
                    cpf = st.text_input("CPF")
                    if st.form_submit_button("Salvar"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO funcionarios (Empresa, Matricula, Nome, Cargo, Setor, CPF) VALUES (?,?,?,?,?,?)", (emp_escolhida, mat, nome, cargo, setor, cpf))
                        conn.commit(); conn.close(); st.rerun()

        # ... (Outras abas mantêm a mesma estrutura) ...
        with tabs[7]:
            if st.button("Gerar PDF"):
                pdf_data = gerar_pdf_paisagem(emp_escolhida, True, True, True, True, df_e, df_f, df_t, df_ex)
                st.download_button("Baixar PDF", data=pdf_data, file_name="relatorio.pdf", mime="application/pdf")
    else:
        st.warning("Cadastre uma empresa primeiro.")
