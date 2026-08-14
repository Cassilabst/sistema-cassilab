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

# --- Função Auxiliar para Datas ---
def parse_date(date_str):
    try:
        return datetime.strptime(str(date_str), '%d/%m/%Y').date()
    except:
        return date.today()

# --- Função de Gráfico de Rosca ---
def criar_grafico_rosca(titulo, executado, meta):
    falta = max(0, meta - executado)
    porcentagem = int((executado / meta * 100)) if meta > 0 else 0
    
    fig = go.Figure(data=[go.Pie(
        labels=['Executado', 'Faltante'],
        values=[executado, falta],
        hole=.7,
        marker_colors=['#6366f1', '#e2e8f0'],
        textinfo='none'
    )])
    fig.update_layout(
        title_text=titulo, title_x=0.5, showlegend=False,
        annotations=[dict(text=f"{porcentagem}%<br>Atingimento", x=0.5, y=0.5, font_size=14, showarrow=False)],
        height=220, margin=dict(t=40, b=10, l=10, r=10)
    )
    return fig

# --- PDF Personalizado ---
def gerar_pdf_paisagem(emp, inc_emp, inc_func, inc_trein, inc_ex, inc_serv, df_e, df_f, df_t, df_exames, df_s):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    dados_emp_reg = df_e[df_e['Empresa'].astype(str).str.strip() == str(emp).strip()]
    nome_completo_emp = str(dados_emp_reg.iloc[0]['Empresa']) if not dados_emp_reg.empty else str(emp)

    pdf.set_font("Arial", 'B', 15)
    pdf.cell(277, 10, txt=f"RELATORIO GERAL: {nome_completo_emp.upper()}", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(277, 6, txt=f"Data de Emissão: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(5)
    
    if inc_emp:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Dados Cadastrais da Empresa:", ln=True)
        pdf.set_font("Arial", size=10)
        for _, row in dados_emp_reg.iterrows():
            pdf.cell(277, 6, txt=f"Empresa: {str(row.get('Empresa', '-'))}", ln=True)
            pdf.cell(277, 6, txt=f"CNPJ: {str(row.get('CNPJ', '-'))} | Contato: {str(row.get('Contato_Nome', '-'))} | Tel: {str(row.get('Contato_Tel', '-'))} | E-mail: {str(row.get('Email', '-'))}", ln=True)
            pdf.cell(277, 6, txt=f"Endereço: {str(row.get('Endereco', '-'))} - {str(row.get('Bairro', '-'))} - {str(row.get('Cidade_UF', '-'))}", ln=True)
        pdf.ln(5)

    if inc_func:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Relação de Funcionários:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_f[df_f['Empresa'].astype(str).str.strip() == str(emp).strip()]
        if not dados.empty:
            for _, row in dados.iterrows():
                pdf.cell(277, 6, txt=f"Matrícula: {row.get('Matricula', '-')} | Nome: {row.get('Nome', '-')} | Cargo: {row.get('Cargo', '-')} | Setor: {row.get('Setor', '-')}", ln=True)
        else:
            pdf.cell(277, 6, txt="Nenhum funcionário cadastrado.", ln=True)
        pdf.ln(5)

    if inc_trein:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Treinamentos:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_t[df_t['Empresa'].astype(str).str.strip() == str(emp).strip()]
        if not dados.empty:
            for _, row in dados.iterrows():
                pdf.cell(277, 6, txt=f"Treinamento: {row.get('Treinamento', '-')} | Data: {row.get('Data', '-')} | Status: {row.get('Status', '-')}", ln=True)
        else:
            pdf.cell(277, 6, txt="Nenhum treinamento registrado.", ln=True)
        pdf.ln(5)

    if inc_ex:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Exames Ocupacionais:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_ex[df_ex['Empresa'].astype(str).str.strip() == str(emp).strip()]
        if not dados.empty:
            for _, row in dados.iterrows():
                pdf.cell(277, 6, txt=f"Funcionário: {row.get('Funcionario', '-')} | Exame: {row.get('Exame', '-')} | Data: {row.get('Data', '-')} | Status: {row.get('Status', '-')}", ln=True)
        else:
            pdf.cell(277, 6, txt="Nenhum exame registrado.", ln=True)
        pdf.ln(5)

    if inc_serv:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(277, 8, txt="Serviços Prestados / Faturamento:", ln=True)
        pdf.set_font("Arial", size=10)
        dados = df_s[df_s['EMPRESA'].astype(str).str.strip() == str(emp).strip()]
        if not dados.empty:
            for _, row in dados.iterrows():
                pdf.cell(277, 6, txt=f"Serviço: {row.get('Serviço_executado', '-')} | Data: {row.get('Data', '-')} | Valor: R$ {row.get('Valor_do_Serviço', 0):.2f} | NF-e: {row.get('NFES', '-')}", ln=True)
        else:
            pdf.cell(277, 6, txt="Nenhum serviço registrado.", ln=True)
        pdf.ln(5)
        
    return pdf.output(dest='S').encode('latin-1')

# --- Interface ---
df_e, df_f, df_t, df_d, df_ex, df_s = get_data()

# Exibição da Logo na Barra Lateral
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)

st.sidebar.title("Navegação")
menu = st.sidebar.radio("Escolha:", ["Painel", "🏢 Empresas (Central de Gestão)", "➕ Cadastrar Nova Empresa"])

st.title("Sistema para Gestão em Saúde e Segurança do Trabalho")

if menu == "Painel":
    st.subheader("📊 Painel Geral de Controle & Indicadores")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Empresas Cadastradas", len(df_e))
    col2.metric("Total de Funcionários", len(df_f))
    col3.metric("Documentos Registrados", len(df_d))
    col4.metric("Exames Realizados", len(df_ex))
    
    st.markdown("---")
    st.subheader("🚨 Alertas e Status Operacionais")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("#### 📚 Treinamentos")
        realizados = len(df_t[df_t['Status'] == 'Realizado']) if not df_t.empty else 0
        pendentes = len(df_t[df_t['Status'] != 'Realizado']) if not df_t.empty else 0
        st.metric("Treinamentos Realizados", realizados)
        st.metric("Treinamentos Pendentes / Não Feitos", pendentes, delta_color="inverse")
        if not df_t.empty:
            st.plotly_chart(criar_grafico_rosca("Atingimento Treinamentos", realizados, max(1, realizados + pendentes)), use_container_width=True)

    with col_b:
        st.markdown("#### 🩺 Exames Ocupacionais")
        aptos = len(df_ex[df_ex['Status'] == 'APTO']) if not df_ex.empty else 0
        atrasados_pend = len(df_ex[df_ex['Status'] != 'APTO']) if not df_ex.empty else 0
        st.metric("Exames em Dia (Aptos)", aptos)
        st.metric("Exames Atrasados / Pendentes", atrasados_pend, delta_color="inverse")
        if not df_ex.empty:
            st.plotly_chart(criar_grafico_rosca("Status Exames", aptos, max(1, aptos + atrasados_pend)), use_container_width=True)

    with col_c:
        st.markdown("#### 📄 Documentos / Programas")
        vigentes = len(df_d[df_d['Status'] == 'Vigente']) if not df_d.empty else 0
        vencidos = len(df_d[df_d['Status'] != 'Vigente']) if not df_d.empty else 0
        st.metric("Documentos Vigentes", vigentes)
        st.metric("Documentos Vencidos / Alerta", vencidos, delta_color="inverse")
        if not df_d.empty:
            st.plotly_chart(criar_grafico_rosca("Vigência Documentos", vigentes, max(1, vigentes + vencidos)), use_container_width=True)

elif menu == "➕ Cadastrar Nova Empresa":
    st.subheader("🏢 Cadastro de Nova Empresa")
    with st.form("form_cad_empresa", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome_emp = c1.text_input("Nome da Empresa")
        cnpj = c2.text_input("CNPJ")
        contato_nome = c1.text_input("Nome do Contato")
        contato_tel = c2.text_input("Telefone do Contato")
        email = c1.text_input("E-mail")
        qtd_func = c2.number_input("Qtd de Funcionários", min_value=0, step=1)
        endereco = c1.text_input("Endereço")
        bairro = c2.text_input("Bairro")
        cep = c1.text_input("CEP")
        cidade_uf = c2.text_input("Cidade/UF")
        
        if st.form_submit_button("Salvar Empresa"):
            if nome_emp:
                conn = sqlite3.connect(DB_NAME)
                conn.execute("""INSERT INTO empresas (Empresa, Contato_Tel, Contato_Nome, CNPJ, Qtd_Func, Endereco, Bairro, CEP, Cidade_UF, Email, Data_Cadastro) 
                                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", 
                             (nome_emp, contato_tel, contato_nome, cnpj, qtd_func, endereco, bairro, cep, cidade_uf, email, datetime.now().strftime('%d/%m/%Y')))
                conn.commit(); conn.close()
                st.success(f"Empresa '{nome_emp}' cadastrada com sucesso!")
                st.rerun()
            else:
                st.error("O nome da empresa é obrigatório.")

elif menu == "🏢 Empresas (Central de Gestão)":
    if not df_e.empty:
        emp_escolhida = st.selectbox("Selecione a Empresa:", sorted(df_e['Empresa'].unique().tolist()))
        tabs = st.tabs(["🏢 Empresas", "👥 Funcionários", "📚 Treinamentos", "📄 Documentos", "🩺 Exames", "🛠️ Serviços", "📊 Dashboard", "🖨️ Relatórios"])
        
        # --- ABA 0: EMPRESAS ---
        with tabs[0]:
            st.subheader(f"Dados da Empresa: {emp_escolhida}")
            dados_emp = df_e[df_e['Empresa'] == emp_escolhida]
            st.dataframe(dados_emp, use_container_width=True)
            
            with st.expander("✏️ Editar Dados da Empresa"):
                if not dados_emp.empty:
                    d_emp = dados_emp.iloc[0]
                    with st.form("form_edit_empresa"):
                        c1, c2 = st.columns(2)
                        e_nome_emp = c1.text_input("Nome da Empresa", d_emp['Empresa'])
                        e_cnpj = c2.text_input("CNPJ", d_emp['CNPJ'])
                        e_contato_nome = c1.text_input("Nome do Contato", d_emp['Contato_Nome'])
                        e_contato_tel = c2.text_input("Telefone do Contato", d_emp['Contato_Tel'])
                        e_email = c1.text_input("E-mail", d_emp.get('Email', ''))
                        e_qtd_func = c2.number_input("Qtd de Funcionários", min_value=0, value=int(d_emp['Qtd_Func']), step=1)
                        e_endereco = c1.text_input("Endereço", d_emp['Endereco'])
                        e_bairro = c2.text_input("Bairro", d_emp['Bairro'])
                        e_cep = c1.text_input("CEP", d_emp['CEP'])
                        e_cidade_uf = c2.text_input("Cidade/UF", d_emp['Cidade_UF'])
                        
                        if st.form_submit_button("Salvar Alterações da Empresa"):
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("""UPDATE empresas SET Empresa=?, Contato_Tel=?, Contato_Nome=?, CNPJ=?, Qtd_Func=?, Endereco=?, Bairro=?, CEP=?, Cidade_UF=?, Email=? WHERE id=?""", 
                                        (e_nome_emp, e_contato_tel, e_contato_nome, e_cnpj, e_qtd_func, e_endereco, e_bairro, e_cep, e_cidade_uf, e_email, int(d_emp['id'])))
                            
                            if e_nome_emp != emp_escolhida:
                                conn.execute("UPDATE funcionarios SET Empresa=? WHERE Empresa=?", (e_nome_emp, emp_escolhida))
                                conn.execute("UPDATE treinamentos SET Empresa=? WHERE Empresa=?", (e_nome_emp, emp_escolhida))
                                conn.execute("UPDATE documentos SET EMPRESA=? WHERE EMPRESA=?", (e_nome_emp, emp_escolhida))
                                conn.execute("UPDATE exames SET Empresa=? WHERE Empresa=?", (e_nome_emp, emp_escolhida))
                                conn.execute("UPDATE servicos SET EMPRESA=? WHERE EMPRESA=?", (e_nome_emp, emp_escolhida))
                                
                            conn.commit(); conn.close()
                            st.success("Dados da empresa atualizados com sucesso!")
                            st.rerun()

            st.markdown("---")
            with st.expander("🗑️ Zona de Perigo - Excluir Empresa"):
                st.warning(f"Atenção: Excluir a empresa '{emp_escolhida}' também removerá todos os registros vinculados a ela.")
                if st.button(f"Excluir definitivamente a empresa {emp_escolhida}"):
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM empresas WHERE Empresa = ?", (emp_escolhida,))
                    conn.execute("DELETE FROM funcionarios WHERE Empresa = ?", (emp_escolhida,))
                    conn.execute("DELETE FROM treinamentos WHERE Empresa = ?", (emp_escolhida,))
                    conn.execute("DELETE FROM documentos WHERE EMPRESA = ?", (emp_escolhida,))
                    conn.execute("DELETE FROM exames WHERE Empresa = ?", (emp_escolhida,))
                    conn.execute("DELETE FROM servicos WHERE EMPRESA = ?", (emp_escolhida,))
                    conn.commit(); conn.close()
                    st.success(f"Empresa '{emp_escolhida}' excluída com sucesso!")
                    st.rerun()

        # --- ABA 1: FUNCIONÁRIOS ---
        with tabs[1]:
            st.subheader("Relação de Funcionários")
            funcs_da_empresa = df_f[df_f['Empresa'] == emp_escolhida]
            st.dataframe(funcs_da_empresa, use_container_width=True)
            
            with st.expander("➕ Cadastrar Novo Funcionário"):
                with st.form("c_func", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nome = c1.text_input("Nome do Funcionário")
                    mat = c2.text_input("Matrícula")
                    cargo = c1.text_input("Cargo")
                    setor = c2.text_input("Setor")
                    cpf = st.text_input("CPF")
                    if st.form_submit_button("Salvar Funcionário"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO funcionarios (Empresa, Matricula, Nome, Cargo, Setor, CPF) VALUES (?,?,?,?,?,?)", (emp_escolhida, mat, nome, cargo, setor, cpf))
                        conn.commit(); conn.close(); st.rerun()
            
            with st.expander("✏️ Editar Funcionário"):
                if not funcs_da_empresa.empty:
                    opcoes_f = funcs_da_empresa.apply(lambda x: f"{x['id']} - {x['Nome']}", axis=1).tolist()
                    func_selecionado = st.selectbox("Selecione o funcionário:", opcoes_f)
                    if func_selecionado:
                        id_func = int(func_selecionado.split(" - ")[0])
                        d_func = funcs_da_empresa[funcs_da_empresa['id'] == id_func].iloc[0]
                        with st.form("e_func"):
                            c1, c2 = st.columns(2)
                            e_nome = c1.text_input("Nome do Funcionário", d_func['Nome'])
                            e_mat = c2.text_input("Matrícula", d_func['Matricula'])
                            e_cargo = c1.text_input("Cargo", d_func['Cargo'])
                            e_setor = c2.text_input("Setor", d_func['Setor'])
                            e_cpf = st.text_input("CPF", d_func['CPF'])
                            if st.form_submit_button("Salvar Alterações"):
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE funcionarios SET Nome=?, Matricula=?, Cargo=?, Setor=?, CPF=? WHERE id=?", (e_nome, e_mat, e_cargo, e_setor, e_cpf, id_func))
                                conn.commit(); conn.close(); st.rerun()

        # --- ABA 2: TREINAMENTOS ---
        with tabs[2]:
            st.subheader("Treinamentos da Empresa")
            trein_da_empresa = df_t[df_t['Empresa'] == emp_escolhida]
            st.dataframe(trein_da_empresa, use_container_width=True)
            
            with st.expander("➕ Registrar Treinamento"):
                with st.form("c_trein", clear_on_submit=True):
                    treinamento = st.text_input("Nome do Treinamento")
                    data_t = st.date_input("Data do Treinamento", value=date.today())
                    status_t = st.selectbox("Status", ["Realizado", "Pendente", "Agendado"])
                    if st.form_submit_button("Salvar Treinamento"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO treinamentos (Empresa, Treinamento, Data, Status) VALUES (?,?,?,?)", (emp_escolhida, treinamento, data_t.strftime('%d/%m/%Y'), status_t))
                        conn.commit(); conn.close(); st.rerun()
                        
            with st.expander("✏️ Editar Treinamento"):
                if not trein_da_empresa.empty:
                    opcoes_t = trein_da_empresa.apply(lambda x: f"{x['id']} - {x['Treinamento']} ({x['Data']})", axis=1).tolist()
                    trein_selecionado = st.selectbox("Selecione o treinamento:", opcoes_t)
                    if trein_selecionado:
                        id_trein = int(trein_selecionado.split(" - ")[0])
                        d_trein = trein_da_empresa[trein_da_empresa['id'] == id_trein].iloc[0]
                        with st.form("e_trein"):
                            e_treinamento = st.text_input("Nome do Treinamento", d_trein['Treinamento'])
                            e_data_t = st.date_input("Data", value=parse_date(d_trein['Data']))
                            status_idx = ["Realizado", "Pendente", "Agendado"].index(d_trein['Status']) if d_trein['Status'] in ["Realizado", "Pendente", "Agendado"] else 0
                            e_status_t = st.selectbox("Status", ["Realizado", "Pendente", "Agendado"], index=status_idx)
                            if st.form_submit_button("Salvar Alterações"):
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE treinamentos SET Treinamento=?, Data=?, Status=? WHERE id=?", (e_treinamento, e_data_t.strftime('%d/%m/%Y'), e_status_t, id_trein))
                                conn.commit(); conn.close(); st.rerun()

        # --- ABA 3: DOCUMENTOS ---
        with tabs[3]:
            st.subheader("Documentos e Programas (PPRA/PCMSO/PGR)")
            docs_da_empresa = df_d[df_d['EMPRESA'] == emp_escolhida]
            st.dataframe(docs_da_empresa, use_container_width=True)
            
            with st.expander("➕ Adicionar Documento"):
                with st.form("c_doc", clear_on_submit=True):
                    doc_nome = st.text_input("Nome do Documento / Programa")
                    data_d = st.date_input("Data de Emissão", value=date.today())
                    venc_d = st.date_input("Data de Vencimento", value=date.today())
                    status_d = st.selectbox("Status do Documento", ["Vigente", "Vencido", "Em Andamento"])
                    if st.form_submit_button("Salvar Documento"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO documentos (EMPRESA, Data, Documento_Programa, Vencimento, Status) VALUES (?,?,?,?,?)", (emp_escolhida, data_d.strftime('%d/%m/%Y'), doc_nome, venc_d.strftime('%d/%m/%Y'), status_d))
                        conn.commit(); conn.close(); st.rerun()
                        
            with st.expander("✏️ Editar Documento"):
                if not docs_da_empresa.empty:
                    opcoes_d = docs_da_empresa.apply(lambda x: f"{x['id']} - {x['Documento_Programa']}", axis=1).tolist()
                    doc_selecionado = st.selectbox("Selecione o documento:", opcoes_d)
                    if doc_selecionado:
                        id_doc = int(doc_selecionado.split(" - ")[0])
                        d_doc = docs_da_empresa[docs_da_empresa['id'] == id_doc].iloc[0]
                        with st.form("e_doc"):
                            e_doc_nome = st.text_input("Nome do Documento / Programa", d_doc['Documento_Programa'])
                            e_data_d = st.date_input("Data de Emissão", value=parse_date(d_doc['Data']))
                            e_venc_d = st.date_input("Data de Vencimento", value=parse_date(d_doc['Vencimento']))
                            s_idx_d = ["Vigente", "Vencido", "Em Andamento"].index(d_doc['Status']) if d_doc['Status'] in ["Vigente", "Vencido", "Em Andamento"] else 0
                            e_status_d = st.selectbox("Status do Documento", ["Vigente", "Vencido", "Em Andamento"], index=s_idx_d)
                            if st.form_submit_button("Salvar Alterações"):
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE documentos SET Documento_Programa=?, Data=?, Vencimento=?, Status=? WHERE id=?", (e_doc_nome, e_data_d.strftime('%d/%m/%Y'), e_venc_d.strftime('%d/%m/%Y'), e_status_d, id_doc))
                                conn.commit(); conn.close(); st.rerun()

        # --- ABA 4: EXAMES ---
        with tabs[4]:
            st.subheader("Exames Ocupacionais")
            exames_da_empresa = df_ex[df_ex['Empresa'] == emp_escolhida]
            st.dataframe(exames_da_empresa, use_container_width=True)
            
            with st.expander("➕ Registrar Exame"):
                with st.form("c_exame", clear_on_submit=True):
                    func_ex = st.text_input("Nome do Funcionário")
                    tipo_ex = st.text_input("Tipo de Exame (Admissional, Periódico...)")
                    data_ex = st.date_input("Data do Exame", value=date.today())
                    status_ex = st.selectbox("Status do Exame", ["APTO", "INAPTO", "Pendente"])
                    if st.form_submit_button("Salvar Exame"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO exames (Empresa, Funcionario, Exame, Data, Status) VALUES (?,?,?,?,?)", (emp_escolhida, func_ex, tipo_ex, data_ex.strftime('%d/%m/%Y'), status_ex))
                        conn.commit(); conn.close(); st.rerun()

            with st.expander("✏️ Editar Exame"):
                if not exames_da_empresa.empty:
                    opcoes_ex = exames_da_empresa.apply(lambda x: f"{x['id']} - {x['Funcionario']} ({x['Exame']})", axis=1).tolist()
                    ex_selecionado = st.selectbox("Selecione o exame:", opcoes_ex)
                    if ex_selecionado:
                        id_ex = int(ex_selecionado.split(" - ")[0])
                        d_ex = exames_da_empresa[exames_da_empresa['id'] == id_ex].iloc[0]
                        with st.form("e_ex"):
                            e_func_ex = st.text_input("Nome do Funcionário", d_ex['Funcionario'])
                            e_tipo_ex = st.text_input("Tipo de Exame", d_ex['Exame'])
                            e_data_ex = st.date_input("Data do Exame", value=parse_date(d_ex['Data']))
                            s_idx_ex = ["APTO", "INAPTO", "Pendente"].index(d_ex['Status']) if d_ex['Status'] in ["APTO", "INAPTO", "Pendente"] else 0
                            e_status_ex = st.selectbox("Status do Exame", ["APTO", "INAPTO", "Pendente"], index=s_idx_ex)
                            if st.form_submit_button("Salvar Alterações"):
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE exames SET Funcionario=?, Exame=?, Data=?, Status=? WHERE id=?", (e_func_ex, e_tipo_ex, e_data_ex.strftime('%d/%m/%Y'), e_status_ex, id_ex))
                                conn.commit(); conn.close(); st.rerun()

        # --- ABA 5: SERVIÇOS ---
        with tabs[5]:
            st.subheader("Serviços Prestados")
            servicos_da_empresa = df_s[df_s['EMPRESA'] == emp_escolhida]
            st.dataframe(servicos_da_empresa, use_container_width=True)
            
            with st.expander("➕ Registrar Serviço"):
                with st.form("c_serv", clear_on_submit=True):
                    serv_nome = st.text_input("Serviço Executado")
                    valor_serv = st.number_input("Valor do Serviço (R$)", min_value=0.0, format="%.2f")
                    nf_serv = st.text_input("NFS-e / Faturamento")
                    data_serv = st.date_input("Data do Serviço", value=date.today())
                    if st.form_submit_button("Salvar Serviço"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO servicos (EMPRESA, Data, Serviço_executado, Valor_do_Serviço, NFES) VALUES (?,?,?,?,?)", (emp_escolhida, data_serv.strftime('%d/%m/%Y'), serv_nome, valor_serv, nf_serv))
                        conn.commit(); conn.close(); st.rerun()

            with st.expander("✏️ Editar Serviço"):
                if not servicos_da_empresa.empty:
                    opcoes_s = servicos_da_empresa.apply(lambda x: f"{x['id']} - {x['Serviço_executado']}", axis=1).tolist()
                    serv_selecionado = st.selectbox("Selecione o serviço:", opcoes_s)
                    if serv_selecionado:
                        id_serv = int(serv_selecionado.split(" - ")[0])
                        d_serv = servicos_da_empresa[servicos_da_empresa['id'] == id_serv].iloc[0]
                        with st.form("e_serv"):
                            e_serv_nome = st.text_input("Serviço Executado", d_serv['Serviço_executado'])
                            e_valor_serv = st.number_input("Valor (R$)", min_value=0.0, value=float(d_serv['Valor_do_Serviço']), format="%.2f")
                            e_nf_serv = st.text_input("NFS-e / Faturamento", d_serv['NFES'])
                            e_data_serv = st.date_input("Data do Serviço", value=parse_date(d_serv['Data']))
                            if st.form_submit_button("Salvar Alterações"):
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE servicos SET Serviço_executado=?, Valor_do_Serviço=?, NFES=?, Data=? WHERE id=?", (e_serv_nome, e_valor_serv, e_nf_serv, e_data_serv.strftime('%d/%m/%Y'), id_serv))
                                conn.commit(); conn.close(); st.rerun()

        # --- ABA 6: DASHBOARD ---
        with tabs[6]:
            st.subheader("📊 Indicadores da Empresa")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.metric("Total de Funcionários", len(df_f[df_f['Empresa'] == emp_escolhida]))
            with col_d2:
                st.metric("Treinamentos Realizados", len(df_t[df_t['Empresa'] == emp_escolhida]))

        # --- ABA 7: RELATÓRIOS ---
        with tabs[7]:
            st.subheader("🖨️ Configuração de Relatório em PDF")
            st.write("Selecione abaixo os itens que deseja incluir no relatório da empresa **" + emp_escolhida + "**:")
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                inc_emp = st.checkbox("Cadastro Completo da Empresa", value=True)
                inc_func = st.checkbox("Relação de Funcionários", value=True)
                inc_trein = st.checkbox("Treinamentos", value=True)
            with c_r2:
                inc_ex = st.checkbox("Exames Ocupacionais", value=True)
                inc_serv = st.checkbox("Serviços Prestados / Faturamento", value=True)
            
            st.markdown("---")
            if st.button("Gerar PDF Personalizado"):
                pdf_data = gerar_pdf_paisagem(emp_escolhida, inc_emp, inc_func, inc_trein, inc_ex, inc_serv, df_e, df_f, df_t, df_ex, df_s)
                st.download_button("📥 Baixar Relatório em PDF", data=pdf_data, file_name=f"relatorio_{emp_escolhida}.pdf", mime="application/pdf")
    else:
        st.warning("Nenhuma empresa cadastrada. Vá até a opção 'Cadastrar Nova Empresa' no menu lateral para começar.")
