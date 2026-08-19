import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
import hashlib
from PIL import Image

# --- Função para limpar CPF (remove pontos e traços) ---
def limpar_cpf(cpf):
    if not cpf:
        return ""
    return "".join(filter(str.isdigit, str(cpf)))

# --- Função para criptografar senhas ---
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- Configuração da Página ---
st.set_page_config(page_title="SISTEMA PARA GESTÃO EM SAÚDE E SEGURANÇA DO TRABALHO", layout="wide")

# --- Conexão e Inicialização do Banco de Dados ---
def init_db():
    conn = sqlite3.connect('cassilab_gestao.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS empresas (
                        nome TEXT, contato TEXT, cnpj TEXT, 
                        qtd_funcionarios INTEGER, grau_risco INTEGER,
                        endereco TEXT, bairro TEXT, cep TEXT, 
                        cidade_uf TEXT, email TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (
                        matricula TEXT, nome TEXT, cargo TEXT, 
                        setor TEXT, cpf TEXT, data_admissao TEXT, status TEXT, empresa TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS cargos (
                        cargo TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS tipos_treinamentos (
                        nome_treinamento TEXT,
                        carga_horaria_padrao TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS treinamentos (
                        empresa TEXT, funcionario TEXT, treinamento TEXT, 
                        carga_horaria TEXT, data_realizacao TEXT, validade TEXT, status TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS documentos (
                        empresa TEXT, data TEXT, servico TEXT, 
                        vencimento TEXT, status TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS exames (
                        matricula TEXT, funcionario TEXT, cargo TEXT, 
                        setor TEXT, ultimo_exame TEXT, tipo_exame TEXT, 
                        proximo_exame TEXT, status TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS servicos (
                        empresa TEXT, data TEXT, servico TEXT, 
                        valor REAL, nfes TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS epis (
                        data_lancamento TEXT, funcionario TEXT, cargo TEXT, 
                        setor TEXT, epi TEXT, ca TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                        usuario TEXT UNIQUE,
                        senha TEXT,
                        tipo TEXT,
                        empresa_vinculada TEXT,
                        cpf TEXT)''')

    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo = 'Admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (usuario, senha, tipo, empresa_vinculada, cpf) VALUES (?, ?, ?, ?, ?)",
                       ("admin", hash_senha("Disc@5232"), "Admin", "Todas", "00000000000"))
    else:
        cursor.execute("UPDATE usuarios SET senha = ? WHERE tipo = 'Admin' AND usuario = 'admin'", (hash_senha("Disc@5232"),))

    conn.commit()
    conn.close()

def importar_planilhas_iniciais():
    conn = sqlite3.connect('cassilab_gestao.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM empresas")
    count = cursor.fetchone()[0]
    
    if count == 0:
        try:
            if os.path.exists("Empresas.xlsx"):
                df = pd.read_excel("Empresas.xlsx")
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[1]):
                        cursor.execute("INSERT INTO empresas (nome, contato, cnpj, qtd_funcionarios, grau_risco, endereco, bairro, cep, cidade_uf, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                      (str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[4]), row.iloc[5], row.iloc[6], str(row.iloc[7]), str(row.iloc[8]), str(row.iloc[9]), str(row.iloc[10]), str(row.iloc[11])))
            
            if os.path.exists("cadastro de funcionarios por empresa.xlsx"):
                df = pd.read_excel("cadastro de funcionarios por empresa.xlsx", skiprows=2)
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[3]):
                        cargo_lido = str(row.iloc[4])
                        cursor.execute("SELECT COUNT(*) FROM cargos WHERE cargo = ?", (cargo_lido,))
                        if cursor.fetchone()[0] == 0:
                            cursor.execute("INSERT INTO cargos (cargo) VALUES (?)", (cargo_lido,))
                            
                        cpf_limpo = limpar_cpf(str(row.iloc[6]))
                        cursor.execute("INSERT INTO funcionarios (matricula, nome, cargo, setor, cpf, data_admissao, status, empresa) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                      (str(row.iloc[2]), str(row.iloc[3]), cargo_lido, str(row.iloc[5]), cpf_limpo, str(row.iloc[7]), str(row.iloc[8]), "Xpto Ltda"))

            if os.path.exists("Controle de Treinamentos.xlsx"):
                df = pd.read_excel("Controle de Treinamentos.xlsx")
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[1]):
                        trein_lido = str(row.iloc[2])
                        carga_lida = str(row.iloc[3])
                        cursor.execute("SELECT COUNT(*) FROM tipos_treinamentos WHERE nome_treinamento = ? AND carga_horaria_padrao = ?", (trein_lido, carga_lida))
                        if cursor.fetchone()[0] == 0:
                            cursor.execute("INSERT INTO tipos_treinamentos (nome_treinamento, carga_horaria_padrao) VALUES (?, ?)", (trein_lido, carga_lida))

                        cursor.execute("INSERT INTO treinamentos (empresa, funcionario, treinamento, carga_horaria, data_realizacao, validade, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (str(row.iloc[0]), str(row.iloc[1]), trein_lido, carga_lida, str(row.iloc[5]), str(row.iloc[6]), str(row.iloc[7])))

            if os.path.exists("Controle de Documentos por empresa.xlsx"):
                df = pd.read_excel("Controle de Documentos por empresa.xlsx")
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[0]):
                        cursor.execute("INSERT INTO documentos (empresa, data, servico, vencimento, status) VALUES (?, ?, ?, ?, ?)",
                                      (str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4])))

            if os.path.exists("Exames ocupacionais.xlsx"):
                df = pd.read_excel("Exames ocupacionais.xlsx", skiprows=1)
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[2]):
                        cursor.execute("INSERT INTO exames (matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                      (str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4]), str(row.iloc[5]), str(row.iloc[6]), str(row.iloc[7]), str(row.iloc[8])))

            if os.path.exists("Serviços executados por empresa.xlsx"):
                df = pd.read_excel("Serviços executados por empresa.xlsx")
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[0]):
                        cursor.execute("INSERT INTO servicos (empresa, data, servico, valor, nfes) VALUES (?, ?, ?, ?, ?)",
                                      (str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), float(row.iloc[3]) if pd.notna(row.iloc[3]) else 0.0, str(row.iloc[4])))

            if os.path.exists("Controle de EPI - Equipamentos de Proteção Individual.xlsx"):
                df = pd.read_excel("Controle de EPI - Equipamentos de Proteção Individual.xlsx", skiprows=1)
                for index, row in df.iterrows():
                    if pd.notna(row.iloc[2]):
                        cursor.execute("INSERT INTO epis (data_lancamento, funcionario, cargo, setor, epi, ca) VALUES (?, ?, ?, ?, ?, ?)",
                                      (str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4]), str(row.iloc[5]), str(row.iloc[6])))

            conn.commit()
        except Exception as e:
            print("Erro:", e)
    conn.close()

init_db()
importar_planilhas_iniciais()

if 'logado' not in st.session_state:
    st.session_state['logado'] = False
    st.session_state['usuario'] = ""
    st.session_state['tipo'] = ""
    st.session_state['empresa_vinculada'] = ""

if not st.session_state['logado']:
    if os.path.exists("logo.png"):
        try:
            logo_login = Image.open("logo.png")
            st.image(logo_login, width=150)
        except:
            pass

    st.title("SISTEMA PARA GESTÃO EM SAÚDE E SEGURANÇA DO TRABALHO")
    st.subheader("Cassilab Consultoria e Treinamentos — Área de Acesso")
    st.markdown("---")
    
    aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔑 Entrar no Sistema", "📝 Primeiro Acesso (LGPD)", "🔄 Esqueci minha senha"])
    
    with aba_login:
        st.markdown("### Acesso Restrito")
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário ou CPF (com ou sem pontos/traço)")
            senha_input = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Entrar")
            
            if btn_entrar:
                conn = sqlite3.connect('cassilab_gestao.db')
                cursor = conn.cursor()
                usuario_limpo = limpar_cpf(usuario_input)
                
                cursor.execute("SELECT senha, tipo, empresa_vinculada FROM usuarios WHERE usuario = ? OR cpf = ? OR cpf = ?", 
                               (usuario_input, usuario_input, usuario_limpo))
                res = cursor.fetchone()
                conn.close()
                
                if res and res[0] == hash_senha(senha_input):
                    st.session_state['logado'] = True
                    st.session_state['usuario'] = usuario_input
                    st.session_state['tipo'] = res[1]
                    st.session_state['empresa_vinculada'] = res[2]
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

    with aba_cadastro:
        st.markdown("### Cadastro de Cliente / Funcionário")
        st.info("Informe o nome da empresa, CPF (com ou sem pontos), usuário e nova senha.")
        
        with st.expander("⚖️ Clique aqui para ler as Leis de Proteção de Dados e Termos LGPD (Lei nº 13.709/2018)"):
            st.markdown("""
            **TERMO DE CONSENTIMENTO E CONFORMIDADE COM A LGPD (Lei Geral de Proteção de Dados - Lei nº 13.709/2018):**
            
            Em conformidade com a legislação brasileira de proteção de dados pessoais (LGPD), informamos que o tratamento de seus dados pessoais (como CPF, nome, cargo e registros de saúde e segurança ocupacional - SST) tem como finalidade exclusiva o cumprimento de obrigações legais e regulamentoras aplicáveis à Saúde e Segurança no Trabalho (Normas Regulamentadoras - NRs).
            
            * **Finalidade Estrita:** Os dados coletados serão utilizados exclusivamente para a gestão de exames, treinamentos, EPIs e emissão de documentos de SST pela Cassilab Consultoria.
            * **Direitos do Titular (Art. 18 da LGPD):** O titular dos dados possui o direito de solicitar a confirmação do tratamento, acesso, correção e a exclusão definitiva de seus dados ("direito ao esquecimento") mediante solicitação ao Administrador do Sistema.
            * **Segurança:** Medidas técnicas e administrativas aptas a proteger os dados pessoais de acessos não autorizados e de situações acidentais ou ilícitas são rigorosamente aplicadas.
            """)

        conn_emp = sqlite3.connect('cassilab_gestao.db')
        empresas_disponiveis = pd.read_sql("SELECT nome FROM empresas", conn_emp)['nome'].tolist()
        conn_emp.close()

        with st.form("form_novo_usuario"):
            cad_empresa = st.selectbox("Empresa", empresas_disponiveis if empresas_disponiveis else ["Nenhuma empresa cadastrada"])
            cad_cpf = st.text_input("Digite seu CPF (Ex: 000.000.000-00 ou só números)")
            cad_usuario = st.text_input("Escolha um Nome de Usuário para Login")
            cad_senha = st.text_input("Escolha uma Senha", type="password")
            
            aceite_lgpd = st.checkbox("Declaro que li e concordo com os termos acima e autorizo o tratamento dos meus dados estritamente para os fins de SST (Lei nº 13.709/2018).")
            
            btn_cadastrar = st.form_submit_button("Cadastrar Conta")
            
            if btn_cadastrar:
                if not aceite_lgpd:
                    st.error("Você deve aceitar os termos de conformidade da LGPD para prosseguir com o cadastro.")
                elif cad_cpf and cad_usuario and cad_senha and cad_empresa:
                    cpf_cad_limpo = limpar_cpf(cad_cpf)
                    
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT empresa, nome FROM funcionarios WHERE (cpf = ? OR cpf = ?) AND empresa = ?", 
                                   (cad_cpf, cpf_cad_limpo, cad_empresa))
                    func_res = cursor.fetchone()
                    
                    if func_res:
                        try:
                            cursor.execute("INSERT INTO usuarios (usuario, senha, tipo, empresa_vinculada, cpf) VALUES (?, ?, ?, ?, ?)",
                                          (cad_usuario, hash_senha(cad_senha), "Cliente", cad_empresa, cpf_cad_limpo))
                            conn.commit()
                            st.success(f"Cadastro realizado com sucesso para a empresa {cad_empresa}! Vá na aba 'Entrar no Sistema'.")
                        except:
                            st.error("Este nome de usuário já está em uso. Escolha outro.")
                    else:
                        st.error("CPF não encontrado para esta empresa na base de dados de funcionários.")
                    conn.close()
                else:
                    st.warning("Preencha todos os campos.")

    with aba_recuperar:
        st.markdown("### Recuperação de Senha")
        with st.form("form_recuperar"):
            rec_usuario = st.text_input("Seu Usuário ou CPF cadastrado")
            nova_senha = st.text_input("Nova Senha Desejada", type="password")
            btn_rec = st.form_submit_button("Atualizar Senha")
            
            if btn_rec:
                if rec_usuario and nova_senha:
                    rec_limpo = limpar_cpf(rec_usuario)
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT usuario FROM usuarios WHERE usuario = ? OR cpf = ? OR cpf = ?", (rec_usuario, rec_usuario, rec_limpo))
                    user_exist = cursor.fetchone()
                    if user_exist:
                        cursor.execute("UPDATE usuarios SET senha = ? WHERE usuario = ? OR cpf = ? OR cpf = ?", 
                                       (hash_senha(nova_senha), rec_usuario, rec_usuario, rec_limpo))
                        conn.commit()
                        st.success("Senha alterada com sucesso! Vá na aba 'Entrar no Sistema'.")
                    else:
                        st.error("Usuário ou CPF não encontrado.")
                    conn.close()
                else:
                    st.warning("Preencha todos os campos.")

    st.stop()

tipo_usuario = st.session_state['tipo']
empresa_usuario = st.session_state['empresa_vinculada']

with st.sidebar:
    if os.path.exists("logo.png"):
        try:
            logo = Image.open("logo.png")
            st.image(logo, width=200)
        except:
            st.markdown("## CASSILAB")
    else:
        st.markdown("## CASSILAB")
        
    st.markdown("### Gestão em SST")
    st.markdown(f"👤 **Logado como:** {st.session_state['usuario']}")
    if tipo_usuario == "Cliente":
        st.markdown(f"🏢 **Empresa:** {empresa_usuario}")
    st.markdown("---")
    
    if tipo_usuario == "Admin":
        menu = st.selectbox(
            "Menu Principal", 
            [
                "Dashboard Inicial", 
                "Gestão de Empresas", 
                "Funcionários", 
                "Controle de Treinamentos", 
                "Documentos SST", 
                "Exames Ocupacionais", 
                "Serviços Executados", 
                "Controle de EPI", 
                "Relatórios"
            ]
        )
    else:
        menu = st.selectbox(
            "Menu Principal", 
            [
                "Dashboard Inicial", 
                "Funcionários da Empresa", 
                "Treinamentos da Empresa", 
                "Documentos SST", 
                "Exames Ocupacionais", 
                "Controle de EPI"
            ]
        )
    
    st.markdown("---")
    
    if tipo_usuario == "Admin":
        with st.expander("⚙️ Administração"):
            if os.path.exists('cassilab_gestao.db'):
                with open('cassilab_gestao.db', 'rb') as f:
                    st.download_button(
                        label="📥 Baixar Backup",
                        data=f,
                        file_name=f"backup_cassilab_{datetime.datetime.now().strftime('%Y%m%d')}.db",
                        mime="application/octet-stream"
                    )
            else:
                st.warning("Banco de dados não encontrado.")
        st.markdown("---")

    if st.button("🚪 Sair do Sistema"):
        st.session_state['logado'] = False
        st.rerun()

st.title("SISTEMA PARA GESTÃO EM SAÚDE E SEGURANÇA DO TRABALHO")
st.subheader("Cassilab Consultoria e Treinamentos")
st.markdown("---")

if menu == "Dashboard Inicial":
    st.header("Painel Geral de Vencimentos e Alertas")
    conn = sqlite3.connect('cassilab_gestao.db')
    
    if tipo_usuario == "Admin":
        df_emp = pd.read_sql("SELECT * FROM empresas", conn)
        df_trein = pd.read_sql("SELECT * FROM treinamentos", conn)
        df_doc = pd.read_sql("SELECT * FROM documentos", conn)
    else:
        df_emp = pd.read_sql("SELECT * FROM empresas WHERE nome = ?", conn, params=(empresa_usuario,))
        df_trein = pd.read_sql("SELECT * FROM treinamentos WHERE empresa = ?", conn, params=(empresa_usuario,))
        df_doc = pd.read_sql("SELECT * FROM documentos WHERE empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Empresas Vinculadas", len(df_emp))
    with col2:
        st.metric("Treinamentos Registrados", len(df_trein))
    with col3:
        st.metric("Documentos SST Registrados", len(df_doc))
        
    st.markdown("### ⚠️ Alertas de Vencimentos Ativos")
    st.info("Sistema operando com segurança e restrição de acesso por perfil.")

elif menu == "Gestão de Empresas" and tipo_usuario == "Admin":
    st.header("Cadastro e Consulta de Empresas")
    
    with st.expander("➕ Cadastrar Nova Empresa"):
        with st.form("form_empresa"):
            nome = st.text_input("Nome da Empresa")
            contato = st.text_input("Contato (Telefone / Responsável)")
            cnpj = st.text_input("CNPJ")
            qtd_func = st.number_input("Quantidade de Funcionários", min_value=0, step=1)
            grau_risco = st.selectbox("Grau de Risco", [1, 2, 3, 4])
            endereco = st.text_input("Endereço")
            bairro = st.text_input("Bairro")
            cep = st.text_input("CEP")
            cidade_uf = st.text_input("Cidade/UF")
            email = st.text_input("E-mail")
            
            submit_emp = st.form_submit_button("Salvar Empresa")
            if submit_emp:
                if nome:
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO empresas (nome, contato, cnpj, qtd_funcionarios, grau_risco, endereco, bairro, cep, cidade_uf, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (nome, contato, cnpj, qtd_func, grau_risco, endereco, bairro, cep, cidade_uf, email))
                    conn.commit()
                    conn.close()
                    st.success("Empresa cadastrada com sucesso!")
                    st.rerun()
                else:
                    st.error("O nome da empresa é obrigatório.")

    st.markdown("### Empresas Cadastradas")
    conn = sqlite3.connect('cassilab_gestao.db')
    df_emp = pd.read_sql("SELECT * FROM empresas", conn)
    conn.close()
    
    edited_df_emp = st.data_editor(df_emp, use_container_width=True, key="editor_empresas")
    if st.button("Salvar Alterações em Empresas"):
        conn = sqlite3.connect('cassilab_gestao.db')
        edited_df_emp.to_sql('empresas', conn, if_exists='replace', index=False)
        conn.close()
        st.success("Alterações salvas com sucesso!")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🗑️ Excluir Empresa do Sistema")
    conn = sqlite3.connect('cassilab_gestao.db')
    lista_empresas_exc = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    conn.close()

    if lista_empresas_exc:
        empresa_para_excluir = st.selectbox("Selecione a empresa que deseja remover completamente:", lista_empresas_exc, key="select_del_empresa")
        if st.button("🗑️ Excluir Empresa Selecionada Definitivamente", type="primary"):
            conn = sqlite3.connect('cassilab_gestao.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM empresas WHERE nome = ?", (empresa_para_excluir,))
            cursor.execute("DELETE FROM funcionarios WHERE empresa = ?", (empresa_para_excluir,))
            cursor.execute("DELETE FROM treinamentos WHERE empresa = ?", (empresa_para_excluir,))
            conn.commit()
            conn.close()
            st.success(f"Empresa '{empresa_para_excluir}' e seus dados vinculados foram removidos com sucesso!")
            st.rerun()
    else:
        st.info("Nenhuma empresa cadastrada para excluir.")

elif menu in ["Funcionários", "Funcionários da Empresa"]:
    st.header("Cadastro e Controle de Funcionários")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    cargos_list = pd.read_sql("SELECT cargo FROM cargos", conn)['cargo'].tolist()
    conn.close()
    
    if tipo_usuario == "Admin":
        with st.expander("➕ Cadastrar Novo Cargo/Função"):
            with st.form("form_novo_cargo"):
                novo_cargo = st.text_input("Nome da Nova Função / Cargo")
                submit_cargo = st.form_submit_button("Salvar Cargo")
                if submit_cargo:
                    if novo_cargo:
                        conn = sqlite3.connect('cassilab_gestao.db')
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO cargos (cargo) VALUES (?)", (novo_cargo,))
                        conn.commit()
                        conn.close()
                        st.success(f"Cargo '{novo_cargo}' cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Digite o nome do cargo.")

        with st.expander("➕ Cadastrar Novo Funcionário"):
            with st.form("form_func"):
                empresa_escolhida = st.selectbox("Empresa", empresas_list if empresas_list else ["Nenhuma empresa cadastrada"])
                matricula = st.text_input("Matrícula")
                nome_func = st.text_input("Nome do Colaborador")
                cargo = st.selectbox("Cargo / Função", cargos_list if cargos_list else ["Nenhum cargo cadastrado"])
                setor = st.text_input("Setor")
                cpf = st.text_input("CPF")
                data_adm = st.text_input("Data de Admissão (AAAA-MM-DD)")
                status_func = st.selectbox("Status", ["Ativo", "Afastado", "Férias", "Demitido"])
                
                submit_func = st.form_submit_button("Salvar Funcionário")
                if submit_func:
                    if nome_func:
                        cpf_limpo = limpar_cpf(cpf)
                        conn = sqlite3.connect('cassilab_gestao.db')
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO funcionarios (matricula, nome, cargo, setor, cpf, data_admissao, status, empresa) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                      (matricula, nome_func, cargo, setor, cpf_limpo, data_adm, status_func, empresa_escolhida))
                        conn.commit()
                        conn.close()
                        st.success("Funcionário cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("O nome do funcionário é obrigatório.")

    st.markdown("### Relação de Funcionários Cadastrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    if tipo_usuario == "Admin":
        if empresas_list:
            empresa_filtro = st.selectbox("🔍 Selecione a Empresa para filtrar:", ["Todas as Empresas"] + empresas_list, key="filtro_empresa_func")
            if empresa_filtro == "Todas as Empresas":
                df_func = pd.read_sql("SELECT * FROM funcionarios", conn)
            else:
                df_func = pd.read_sql("SELECT * FROM funcionarios WHERE empresa = ?", conn, params=(empresa_filtro,))
        else:
            df_func = pd.read_sql("SELECT * FROM funcionarios", conn)
    else:
        df_func = pd.read_sql("SELECT * FROM funcionarios WHERE empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    if tipo_usuario == "Admin":
        edited_df_func = st.data_editor(df_func, use_container_width=True, key="editor_func")
        if st.button("Salvar Alterações em Funcionários"):
            conn = sqlite3.connect('cassilab_gestao.db')
            edited_df_func.to_sql('funcionarios', conn, if_exists='replace', index=False)
            conn.close()
            st.success("Alterações salvas com sucesso!")
            st.rerun()
    else:
        st.dataframe(df_func, use_container_width=True)

elif menu in ["Controle de Treinamentos", "Treinamentos da Empresa"]:
    st.header("Controle e Catálogo de Treinamentos")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    df_cat_completo = pd.read_sql("SELECT * FROM tipos_treinamentos", conn)
    conn.close()
    
    if not df_cat_completo.empty:
        df_cat_completo['opcao_formatada'] = df_cat_completo['nome_treinamento'] + " — (" + df_cat_completo['carga_horaria_padrao'].astype(str) + ")"
        tipos_trein_list = df_cat_completo['opcao_formatada'].tolist()
    else:
        tipos_trein_list = []
    
    if tipo_usuario == "Admin":
        with st.expander("➕ Cadastrar / Gerenciar Catálogo de Treinamentos"):
            with st.form("form_novo_tipo_trein"):
                novo_trein_nome = st.text_input("Nome do Treinamento")
                carga_padrao = st.text_input("Carga Horária Padrão")
                submit_novo_trein = st.form_submit_button("Salvar Treinamento no Catálogo")
                if submit_novo_trein:
                    if novo_trein_nome:
                        conn = sqlite3.connect('cassilab_gestao.db')
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO tipos_treinamentos (nome_treinamento, carga_horaria_padrao) VALUES (?, ?)", (novo_trein_nome, carga_padrao))
                        conn.commit()
                        conn.close()
                        st.success(f"Treinamento '{novo_trein_nome}' adicionado ao catálogo!")
                        st.rerun()
                    else:
                        st.error("O nome do treinamento é obrigatório.")

        with st.expander("➕ Lançar Treinamento para Funcionário"):
            empresa = st.selectbox("Empresa", empresas_list if empresas_list else [""], key="sel_empresa_trein")
            conn = sqlite3.connect('cassilab_gestao.db')
            if empresa:
                funcionarios_list = pd.read_sql("SELECT nome FROM funcionarios WHERE empresa = ?", conn, params=(empresa,))['nome'].tolist()
            else:
                funcionarios_list = []
            conn.close()

            funcionario = st.selectbox("Nome do Funcionário", funcionarios_list if funcionarios_list else ["Nenhum funcionário"])
            treinamento_selecionado = st.selectbox("Tipo de Treinamento", tipos_trein_list if tipos_trein_list else ["Nenhum treinamento"], key="trein_selectbox")
            
            carga_sugerida = ""
            treinamento_nome_real = ""
            if tipos_trein_list and treinamento_selecionado and " — (" in treinamento_selecionado:
                partes = treinamento_selecionado.split(" — (")
                treinamento_nome_real = partes[0]
                carga_sugerida = partes[1].replace(")", "")

            carga = st.text_input("Carga Horária", value=carga_sugerida, key="input_carga_dinamica")
            data_real = st.text_input("Data da Realização (AAAA-MM-DD)", key="input_data_real")
            validade = st.text_input("Validade", key="input_validade")
            status = st.selectbox("Status", ["em dia", "vencido"], key="input_status_trein")
            
            if st.button("Salvar Lançamento de Treinamento", type="primary"):
                if treinamento_nome_real and funcionario and funcionario != "Nenhum funcionário":
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO treinamentos (empresa, funcionario, treinamento, carga_horaria, data_realizacao, validade, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (empresa, funcionario, treinamento_nome_real, carga, data_real, validade, status))
                    conn.commit()
                    conn.close()
                    st.success("Treinamento lançado com sucesso!")
                    st.rerun()
                else:
                    st.error("Selecione uma empresa e um funcionário válido.")

    st.markdown("### Treinamentos Registrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    if tipo_usuario == "Admin":
        if empresas_list:
            empresa_filtro_trein = st.selectbox("🔍 Selecione a Empresa:", ["Todas as Empresas"] + empresas_list, key="filtro_empresa_trein")
            if empresa_filtro_trein == "Todas as Empresas":
                df_trein = pd.read_sql("SELECT * FROM treinamentos", conn)
            else:
                df_trein = pd.read_sql("SELECT * FROM treinamentos WHERE empresa = ?", conn, params=(empresa_filtro_trein,))
        else:
            df_trein = pd.read_sql("SELECT * FROM treinamentos", conn)
    else:
        df_trein = pd.read_sql("SELECT * FROM treinamentos WHERE empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    if tipo_usuario == "Admin":
        nomes_puros_trein = df_cat_completo['nome_treinamento'].unique().tolist() if not df_cat_completo.empty else []
        edited_df_trein = st.data_editor(
            df_trein, use_container_width=True, key="editor_trein",
            column_config={
                "treinamento": st.column_config.SelectboxColumn("Treinamento", options=nomes_puros_trein if nomes_puros_trein else [""], required=True)
            }
        )
        if st.button("Salvar Alterações em Treinamentos Registrados"):
            conn = sqlite3.connect('cassilab_gestao.db')
            edited_df_trein.to_sql('treinamentos', conn, if_exists='replace', index=False)
            conn.close()
            st.success("Alterações salvas com sucesso!")
            st.rerun()
    else:
        st.dataframe(df_trein, use_container_width=True)

elif menu == "Documentos SST":
    st.header("Controle de Documentos de SST")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    conn.close()
    
    if tipo_usuario == "Admin":
        with st.expander("➕ Adicionar Novo Documento"):
            with st.form("form_doc"):
                empresa = st.selectbox("Empresa", empresas_list if empresas_list else [""])
                data = st.text_input("Data (AAAA-MM-DD)")
                servico = st.text_input("Serviço Executado")
                vencimento = st.text_input("Vencimento (AAAA-MM-DD)")
                status = st.selectbox("Status", ["em dia", "vencido"])
                
                if st.form_submit_button("Salvar Documento"):
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO documentos (empresa, data, servico, vencimento, status) VALUES (?, ?, ?, ?, ?)",
                                  (empresa, data, servico, vencimento, status))
                    conn.commit()
                    conn.close()
                    st.success("Documento salvo com sucesso!")
                    st.rerun()

    st.markdown("### Documentos Registrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    if tipo_usuario == "Admin":
        if empresas_list:
            empresa_filtro_doc = st.selectbox("🔍 Selecione a Empresa:", ["Todas as Empresas"] + empresas_list, key="filtro_empresa_doc")
            if empresa_filtro_doc == "Todas as Empresas":
                df_doc = pd.read_sql("SELECT * FROM documentos", conn)
            else:
                df_doc = pd.read_sql("SELECT * FROM documentos WHERE empresa = ?", conn, params=(empresa_filtro_doc,))
        else:
            df_doc = pd.read_sql("SELECT * FROM documentos", conn)
    else:
        df_doc = pd.read_sql("SELECT * FROM documentos WHERE empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    if tipo_usuario == "Admin":
        edited_df_doc = st.data_editor(df_doc, use_container_width=True, key="editor_doc")
        if st.button("Salvar Alterações em Documentos"):
            conn = sqlite3.connect('cassilab_gestao.db')
            edited_df_doc.to_sql('documentos', conn, if_exists='replace', index=False)
            conn.close()
            st.success("Alterações salvas com sucesso!")
            st.rerun()
    else:
        st.dataframe(df_doc, use_container_width=True)

elif menu == "Exames Ocupacionais":
    st.header("Controle de Exames Ocupacionais e Periódicos")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    if tipo_usuario == "Admin":
        funcionarios_list = pd.read_sql("SELECT nome FROM funcionarios", conn)['nome'].tolist()
    else:
        funcionarios_list = pd.read_sql("SELECT nome FROM funcionarios WHERE empresa = ?", conn, params=(empresa_usuario,))['nome'].tolist()
    conn.close()
    
    if tipo_usuario == "Admin":
        with st.expander("➕ Adicionar Novo Exame"):
            with st.form("form_ex"):
                matricula = st.text_input("Matrícula")
                funcionario = st.selectbox("Nome do Colaborador", funcionarios_list if funcionarios_list else [""])
                cargo = st.text_input("Cargo")
                setor = st.text_input("Setor")
                ultimo_exame = st.text_input("Data do Último Exame (AAAA-MM-DD)")
                tipo_exame = st.selectbox("Tipo de Exame", ["Periodico", "Admissional", "Demissional", "De retorno", "Mudança de função"])
                proximo_exame = st.text_input("Data do Próximo Exame (AAAA-MM-DD)")
                status = st.selectbox("Status", ["Válido", "Vencido"])
                
                if st.form_submit_button("Salvar Exame"):
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO exames (matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status))
                    conn.commit()
                    conn.close()
                    st.success("Exame salvo com sucesso!")
                    st.rerun()

    st.markdown("### Exames Registrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    if tipo_usuario == "Admin":
        if empresas_list:
            empresa_filtro_exames = st.selectbox("🔍 Selecione a Empresa:", ["Todas as Empresas"] + empresas_list, key="filtro_empresa_exames")
            if empresa_filtro_exames == "Todas as Empresas":
                df_ex = pd.read_sql("SELECT * FROM exames", conn)
            else:
                df_ex = pd.read_sql("SELECT e.* FROM exames e JOIN funcionarios f ON e.funcionario = f.nome WHERE f.empresa = ?", conn, params=(empresa_filtro_exames,))
        else:
            df_ex = pd.read_sql("SELECT * FROM exames", conn)
    else:
        df_ex = pd.read_sql("SELECT e.* FROM exames e JOIN funcionarios f ON e.funcionario = f.nome WHERE f.empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    if tipo_usuario == "Admin":
        edited_df_ex = st.data_editor(df_ex, use_container_width=True, key="editor_exames")
        if st.button("Salvar Alterações em Exames"):
            conn = sqlite3.connect('cassilab_gestao.db')
            edited_df_ex.to_sql('exames', conn, if_exists='replace', index=False)
            conn.close()
            st.success("Alterações salvas com sucesso!")
            st.rerun()
    else:
        st.dataframe(df_ex, use_container_width=True)

elif menu == "Serviços Executados" and tipo_usuario == "Admin":
    st.header("Controle de Serviços Executados por Empresa")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    conn.close()
    
    with st.expander("➕ Lançar Novo Serviço"):
        with st.form("form_serv"):
            empresa = st.selectbox("Empresa", empresas_list if empresas_list else [""])
            data = st.text_input("Data (AAAA-MM-DD)")
            servico = st.text_input("Serviço Executado")
            valor = st.number_input("Valor do Serviço (R$)", min_value=0.0, format="%.2f")
            nfes = st.text_input("Número da NF (NFES)")
            
            if st.form_submit_button("Salvar Serviço"):
                conn = sqlite3.connect('cassilab_gestao.db')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO servicos (empresa, data, servico, valor, nfes) VALUES (?, ?, ?, ?, ?)",
                              (empresa, data, servico, valor, nfes))
                conn.commit()
                conn.close()
                st.success("Serviço registrado com sucesso!")
                st.rerun()

    st.markdown("### Serviços Registrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    df_serv = pd.read_sql("SELECT * FROM servicos", conn)
    conn.close()
    
    edited_df_serv = st.data_editor(df_serv, use_container_width=True, key="editor_serv")
    if st.button("Salvar Alterações em Serviços"):
        conn = sqlite3.connect('cassilab_gestao.db')
        edited_df_serv.to_sql('servicos', conn, if_exists='replace', index=False)
        conn.close()
        st.success("Alterações salvas com sucesso!")
        st.rerun()

elif menu == "Controle de EPI":
    st.header("Controle de Equipamentos de Proteção Individual (EPI)")
    
    conn = sqlite3.connect('cassilab_gestao.db')
    empresas_list = pd.read_sql("SELECT nome FROM empresas", conn)['nome'].tolist()
    if tipo_usuario == "Admin":
        funcionarios_list = pd.read_sql("SELECT nome FROM funcionarios", conn)['nome'].tolist()
    else:
        funcionarios_list = pd.read_sql("SELECT nome FROM funcionarios WHERE empresa = ?", conn, params=(empresa_usuario,))['nome'].tolist()
    conn.close()
    
    if tipo_usuario == "Admin":
        with st.expander("➕ Entregar Novo EPI"):
            with st.form("form_epi"):
                data_lanc = st.text_input("Data de Lançamento (AAAA-MM-DD)")
                funcionario = st.selectbox("Nome do Colaborador", funcionarios_list if funcionarios_list else [""])
                cargo = st.text_input("Cargo")
                setor = st.text_input("Setor")
                epi = st.text_input("EPI")
                ca = st.text_input("CA")
                
                if st.form_submit_button("Salvar Entrega de EPI"):
                    conn = sqlite3.connect('cassilab_gestao.db')
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO epis (data_lancamento, funcionario, cargo, setor, epi, ca) VALUES (?, ?, ?, ?, ?, ?)",
                                  (data_lanc, funcionario, cargo, setor, epi, ca))
                    conn.commit()
                    conn.close()
                    st.success("EPI registrado com sucesso!")
                    st.rerun()

    st.markdown("### EPIs Registrados")
    conn = sqlite3.connect('cassilab_gestao.db')
    if tipo_usuario == "Admin":
        if empresas_list:
            empresa_filtro_epi = st.selectbox("🔍 Selecione a Empresa:", ["Todas as Empresas"] + empresas_list, key="filtro_empresa_epi")
            if empresa_filtro_epi == "Todas as Empresas":
                df_epi = pd.read_sql("SELECT * FROM epis", conn)
            else:
                df_epi = pd.read_sql("SELECT e.* FROM epis e JOIN funcionarios f ON e.funcionario = f.nome WHERE f.empresa = ?", conn, params=(empresa_filtro_epi,))
        else:
            df_epi = pd.read_sql("SELECT * FROM epis", conn)
    else:
        df_epi = pd.read_sql("SELECT e.* FROM epis e JOIN funcionarios f ON e.funcionario = f.nome WHERE f.empresa = ?", conn, params=(empresa_usuario,))
    conn.close()
    
    if tipo_usuario == "Admin":
        edited_df_epi = st.data_editor(df_epi, use_container_width=True, key="editor_epi")
        if st.button("Salvar Alterações em EPIs"):
            conn = sqlite3.connect('cassilab_gestao.db')
            edited_df_epi.to_sql('epis', conn, if_exists='replace', index=False)
            conn.close()
            st.success("Alterações salvas com sucesso!")
            st.rerun()
    else:
        st.dataframe(df_epi, use_container_width=True)

elif menu == "Relatórios" and tipo_usuario == "Admin":
    st.header("Gerador de Relatórios Personalizados")
    st.write("Marque abaixo os módulos que deseja visualizar no relatório:")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        r_emp = st.checkbox("Empresas")
        r_func = st.checkbox("Funcionários")
    with col2:
        r_trein = st.checkbox("Treinamentos")
        r_doc = st.checkbox("Documentos SST")
    with col3:
        r_ex = st.checkbox("Exames Ocupacionais")
        r_epi = st.checkbox("Controle de EPI")
        
    if st.button("Gerar Relatório na Tela"):
        conn = sqlite3.connect('cassilab_gestao.db')
        if r_emp:
            st.subheader("Relatório de Empresas")
            st.dataframe(pd.read_sql("SELECT * FROM empresas", conn), use_container_width=True)
        if r_func:
            st.subheader("Relatório de Funcionários")
            st.dataframe(pd.read_sql("SELECT * FROM funcionarios", conn), use_container_width=True)
        if r_trein:
            st.subheader("Relatório de Treinamentos")
            st.dataframe(pd.read_sql("SELECT * FROM treinamentos", conn), use_container_width=True)
        if r_doc:
            st.subheader("Relatório de Documentos")
            st.dataframe(pd.read_sql("SELECT * FROM documentos", conn), use_container_width=True)
        if r_ex:
            st.subheader("Relatório de Exames")
            st.dataframe(pd.read_sql("SELECT * FROM exames", conn), use_container_width=True)
        if r_epi:
            st.subheader("Relatório de EPIs")
            st.dataframe(pd.read_sql("SELECT * FROM epis", conn), use_container_width=True)
        conn.close()