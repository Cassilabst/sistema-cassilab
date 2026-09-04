import streamlit as st
import sqlite3
import os
from datetime import datetime, timedelta
import re
import pandas as pd
import requests
import csv
import shutil
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração da Página
st.set_page_config(page_title="Cassilab - Gestão em SST", page_icon="🛡️", layout="wide")

# --- BANCO DE DADOS LOCAL ---
DB_NAME = "cassilab_gestao.db"

def conectar_db():
    """Cria uma conexão com o banco de dados definindo um timeout para evitar travamentos."""
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    return conn

def fazer_backup_automatico():
    """Cria uma cópia de segurança do banco de dados automaticamente e limpa os antigos."""
    if os.path.exists(DB_NAME):
        pasta_backup = "backups_automaticos"
        if not os.path.exists(pasta_backup):
            os.makedirs(pasta_backup)
        
        data_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome_arquivo_backup = os.path.join(pasta_backup, f"cassilab_backup_{data_hora}.db")
        
        try:
            shutil.copy(DB_NAME, nome_arquivo_backup)
            dias_para_guardar = 7
            agora = datetime.now()
            
            for arquivo in os.listdir(pasta_backup):
                caminho_arquivo = os.path.join(pasta_backup, arquivo)
                if os.path.isfile(caminho_arquivo) and arquivo.endswith(".db"):
                    data_arquivo = datetime.fromtimestamp(os.path.getmtime(caminho_arquivo))
                    if agora - data_arquivo > timedelta(days=dias_para_guardar):
                        os.remove(caminho_arquivo)
        except:
            pass

def formatar_titulo(texto):
    if not texto or pd.isna(texto):
        return ""
    excecoes = {"e", "da", "de", "do", "das", "dos", "em", "para", "com", "S.A."}
    siglas_maiusculas = {
        "ltda", "nr", "me", "mei", "epp", "epi", "cnae", "pgr", "pcmso", 
        "pgrs", "pca", "ppr", "npt", "ccb", "aet", "aep", "arp", "ltcat", 
        "apr", "ppp", "cipa", "epc", "aso", "sst", "sesmt", "ca", "nfes"
    }
    
    palavras = str(texto).strip().split()
    palavras_formatadas = []
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r'[^a-zA-Z0-9]', '', p).lower()
        if p_limpa in siglas_maiusculas:
            palavras_formatadas.append(p.upper())
        else:
            p_lower = p.lower()
            if i > 0 and p_lower in excecoes:
                palavras_formatadas.append(p_lower)
            else:
                if "-" in p:
                    partes = [sub.upper() if sub.lower() in siglas_maiusculas else sub.capitalize() for sub in p.split("-")]
                    palavras_formatadas.append("-".join(partes))
                else:
                    palavras_formatadas.append(p.capitalize())
    return " ".join(palavras_formatadas)

def adicionar_numeracao(df):
    """Adiciona uma coluna de numeração sequencial (1, 2, 3...) no início da tabela."""
    if df is None or df.empty:
        return df
    df = df.copy()
    if "Nº" in df.columns:
        df = df.drop(columns=["Nº"])
    df.insert(0, "Nº", range(1, len(df) + 1))
    return df

def registrar_log(usuario, empresa, acao):
    """Registra uma ação ou acesso no log do sistema."""
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        dt_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("INSERT INTO logs_sistema (data_hora, usuario, empresa, acao) VALUES (?, ?, ?, ?)", 
                       (dt_atual, str(usuario), str(empresa), str(acao)))
        conn.commit()
        conn.close()
    except:
        pass

def verificar_cargo_isento_exame(cargo_str):
    """Verifica se o cargo corresponde a sócio, proprietário ou diretor para isentar de exames."""
    if not cargo_str or pd.isna(cargo_str):
        return False
    c_low = str(cargo_str).lower()
    termos_isentos = ["sócio", "socio", "proprietário", "proprietario", "diretor", "titular", "sócia", "socia", "proprietária", "proprietaria"]
    return any(termo in c_low for termo in termos_isentos)

def sincronizar_status_exames():
    """Atualiza automaticamente o status dos exames com base na data de hoje e se é sócio/proprietário."""
    try:
        conn = conectar_db()
        df = pd.read_sql("SELECT id, cargo, proximo_exame FROM exames", conn)
        if not df.empty:
            cursor = conn.cursor()
            hoje = datetime.today().date()
            for _, row in df.iterrows():
                prox = row["proximo_exame"]
                cargo = row["cargo"]
                
                if verificar_cargo_isento_exame(cargo):
                    novo_st = "Válido"
                else:
                    novo_st = "Válido"
                    if prox and not pd.isna(prox):
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                            try:
                                dt = datetime.strptime(str(prox).strip(), fmt).date()
                                diff = (dt - hoje).days
                                if diff < 0:
                                    novo_st = "Vencido"
                                elif diff <= 30:
                                    novo_st = "A Vencer"
                                else:
                                    novo_st = "Válido"
                                break
                            except ValueError:
                                continue
                cursor.execute("UPDATE exames SET status = ? WHERE id = ?", (novo_st, row["id"]))
            conn.commit()
        conn.close()
    except:
        pass

def init_db():
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grau_risco_nr04 (
            cnae TEXT PRIMARY KEY,
            descricao TEXT,
            grau_risco TEXT
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM grau_risco_nr04;")
    if cursor.fetchone()[0] == 0:
        try:
            if os.path.exists("anexo_i_nr04.csv"):
                with open("anexo_i_nr04.csv", "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 3:
                            cnae = row[0].strip()
                            grau = row[-1].strip()
                            desc = ",".join(row[1:-1]).strip()
                            cursor.execute("INSERT OR REPLACE INTO grau_risco_nr04 (cnae, descricao, grau_risco) VALUES (?, ?, ?)", (cnae, desc, grau))
        except:
            pass

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
            cnae TEXT,
            grau_risco TEXT,
            qtd_funcionarios INTEGER
        )
    """)
    
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_empresas_cnpj ON empresas(cnpj) WHERE cnpj IS NOT NULL AND cnpj != '';")
    except:
        pass
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            cpf TEXT UNIQUE,
            empresa TEXT,
            email TEXT,
            celular TEXT,
            senha TEXT,
            status TEXT DEFAULT 'Pendente',
            nivel_permissao TEXT DEFAULT 'Somente Visualizar'
        )
    """)

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
            pessoas_treinadas TEXT,
            data_realizacao TEXT,
            validade TEXT,
            status TEXT
        )
    """)
    
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos_realizados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            servico TEXT,
            data_realizacao TEXT,
            responsavel TEXT,
            observacoes TEXT,
            valor REAL DEFAULT 0,
            status TEXT,
            nfes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            documento TEXT,
            data_emissao TEXT,
            validade TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            usuario TEXT,
            empresa TEXT,
            acao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_cargos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            cargo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_setores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            setor TEXT
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_treinamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            treinamento TEXT UNIQUE,
            carga_horaria TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico TEXT UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_alertas_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            tipo_item TEXT,
            id_item INTEGER,
            data_vencimento TEXT,
            data_envio TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()
fazer_backup_automatico()
sincronizar_status_exames()

# --- FUNÇÕES DE CALLBACK PARA LIMPAR SELEÇÕES AO TROCAR DE FILTRO ---
def reset_emp_selection():
    if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
    st.session_state["sel_id_emp"] = None
    st.session_state["modal_detalhes_emp_id"] = None

def reset_func_selection():
    if "editor_selecao_funcionarios" in st.session_state: del st.session_state["editor_selecao_funcionarios"]
    st.session_state["sel_id_func"] = None
    st.session_state["modal_edit_func_id"] = None

def reset_tr_selection():
    if "editor_selecao_treinamentos" in st.session_state: del st.session_state["editor_selecao_treinamentos"]
    st.session_state["sel_id_tr"] = None
    st.session_state["modal_edit_trein_id"] = None

def reset_ex_selection():
    if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
    st.session_state["sel_id_ex"] = None
    st.session_state["modal_edit_exame_id"] = None

def reset_epi_selection():
    if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
    st.session_state["sel_id_epi"] = None
    st.session_state["modal_edit_epi_id"] = None

def reset_serv_selection():
    if "editor_selecao_servicos" in st.session_state: del st.session_state["editor_selecao_servicos"]
    st.session_state["sel_id_serv"] = None
    st.session_state["modal_edit_serv_id"] = None

# --- JANELAS POP-UP (MODAIS) GERENCIADAS POR ESTADO ---

@st.dialog("⚠️ Confirmar Exclusão")
def dialog_excluir(tabela, id_registro, editor_key):
    st.write("Tem certeza de que deseja excluir este registro permanentemente?")
    col_d1, col_d2 = st.columns(2)
    if col_d1.button("Sim, Excluir", use_container_width=True):
        conn = conectar_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"SELECT * FROM {tabela} WHERE id = ?", (id_registro,))
            colunas = [col[0] for col in cursor.description]
            dados_linha = cursor.fetchone()
            if dados_linha:
                dict_dados = dict(zip(colunas, dados_linha))
                st.session_state["ultimo_excluido"] = {
                    "tabela": tabela,
                    "dados": dict_dados
                }
        except:
            pass

        cursor.execute(f"DELETE FROM {tabela} WHERE id = ?", (id_registro,))
        conn.commit()
        conn.close()
        
        if editor_key in st.session_state:
            del st.session_state[editor_key]
        st.session_state["modal_excluir_ativo"] = False
        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso! (Você pode desfazer a exclusão na barra lateral)."
        registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), st.session_state.get("empresa_usuario", "Todas"), f"Exclusão de registro na tabela {tabela}")
        st.rerun()
    if col_d2.button("Cancelar", use_container_width=True):
        st.session_state["modal_excluir_ativo"] = False
        st.rerun()

@st.dialog("🏢 Detalhes Completos da Empresa")
def dialog_detalhes_empresa(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, cnae, grau_risco, qtd_funcionarios FROM empresas WHERE id = ?", (id_alvo,))
    reg = cursor.fetchone()
    conn.close()

    if reg:
        d_reg, d_nome, d_cnpj, d_cep, d_cid, d_bair, d_end, d_tel, d_email, d_resp, d_cnae, d_risco, d_qtd = reg
        st.markdown(f"### 🏢 {d_nome or 'Sem Nome'}")
        st.markdown("---")
        
        c_m1, c_m2 = st.columns(2)
        c_m1.markdown(f"**📅 Data de Registro:** {formatar_data_br(d_reg)}")
        c_m1.markdown(f"**📄 CNPJ:** {formatar_cnpj(d_cnpj)}")
        c_m1.markdown(f"**📞 Telefone:** {d_tel or '-'}")
        c_m1.markdown(f"**✉️ E-mail:** {d_email or '-'}")
        c_m1.markdown(f"**👤 Responsável:** {d_resp or '-'}")
        
        c_m2.markdown(f"**📍 Endereço:** {d_end or '-'}")
        c_m2.markdown(f"**🏘️ Bairro:** {d_bair or '-'}")
        c_m2.markdown(f"**📮 CEP:** {d_cep or '-'}")
        c_m2.markdown(f"**🌆 Cidade/UF:** {d_cid or '-'}")
        c_m2.markdown(f"**📋 CNAE:** {d_cnae or '-'}")
        c_m2.markdown(f"**⚠️ Grau de Risco:** {d_risco or '-'}")
        c_m2.markdown(f"**👥 Qtd de Funcionários:** {d_qtd if d_qtd is not None else 0}")
        
        st.markdown("")
        if st.button("✖️ Fechar Janela", use_container_width=True):
            st.session_state["modal_detalhes_emp_id"] = None
            st.rerun()

@st.dialog("✏️ Editar Funcionário")
def dialog_editar_funcionario(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios WHERE id = ?", (id_alvo,))
    reg_func = cursor.fetchone()
    conn.close()

    if reg_func:
        f_emp, f_mat, f_nome, f_cargo, f_setor, f_cpf, f_dt, f_st = reg_func
        with st.form(f"form_edicao_func_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {f_emp}")
            novo_mat = st.text_input("Matrícula", value=str(f_mat) if f_mat else "")
            novo_nome = st.text_input("Nome do Funcionário", value=str(f_nome))
            
            cargos_emp_ed = get_cargos_por_empresa(f_emp)
            if f_cargo in cargos_emp_ed:
                idx_c_ed = cargos_emp_ed.index(f_cargo)
                novo_cargo = st.selectbox("Cargo", cargos_emp_ed, index=idx_c_ed)
            else:
                novo_cargo = st.text_input("Cargo", value=str(f_cargo))

            setores_emp_ed = get_setores_por_empresa(f_emp)
            if f_setor in setores_emp_ed:
                idx_s_ed = setores_emp_ed.index(f_setor)
                novo_setor = st.selectbox("Setor", setores_emp_ed, index=idx_s_ed)
            else:
                novo_setor = st.text_input("Setor", value=str(f_setor) if f_setor else "")

            novo_cpf = st.text_input("CPF", value=str(f_cpf) if f_cpf else "")
            nova_data_adm = st.text_input("Data Admissão", value=str(f_dt) if f_dt else "")
            
            st_limpo_f = limpar_status_banco(f_st)
            opcoes_st_f = ["Ativo", "Afastado", "Desligado"]
            try: idx_st_f = opcoes_st_f.index(st_limpo_f)
            except: idx_st_f = 0
            novo_status_f = st.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"], index=idx_st_f)

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                conn = conectar_db()
                conn.execute("""
                    UPDATE base_funcionarios 
                    SET matricula = ?, funcionario = ?, cargo = ?, setor = ?, cpf = ?, data_admissao = ?, status = ?
                    WHERE id = ?
                """, (
                    str(novo_mat).strip(),
                    formatar_titulo(novo_nome),
                    formatar_titulo(novo_cargo),
                    formatar_titulo(novo_setor),
                    formatar_cpf(novo_cpf),
                    validar_e_formatar_data_input(nova_data_adm),
                    limpar_status_banco(novo_status_f),
                    id_alvo
                ))
                conn.commit()
                conn.execute("UPDATE exames SET cargo = ? WHERE empresa = ? AND funcionario = ?", (formatar_titulo(novo_cargo), f_emp, formatar_titulo(novo_nome)))
                conn.commit()
                conn.close()
                sincronizar_status_exames()

                st.session_state["modal_edit_func_id"] = None
                st.session_state["sel_id_func"] = None
                if "editor_selecao_funcionarios" in st.session_state: del st.session_state["editor_selecao_funcionarios"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), f_emp, f"Edição do funcionário: {formatar_titulo(novo_nome)}")
                st.rerun()

@st.dialog("✏️ Editar Treinamento")
def dialog_editar_treinamento(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT empresa, funcionario, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, status, matricula, cargo, setor FROM treinamentos WHERE id = ?", (id_alvo,))
    reg_tr = cursor.fetchone()
    conn.close()

    if reg_tr:
        t_emp, t_func, t_trein, t_carga, t_pessoas, t_data, t_val, t_status, t_mat, t_cargo, t_setor = reg_tr
        with st.form(f"form_edicao_trein_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {t_emp}")
            
            conn = conectar_db()
            df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(t_emp,))
            conn.close()
            
            lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [t_func]
            if t_func not in lista_funcs:
                lista_funcs.insert(0, t_func)
            try: idx_f = lista_funcs.index(t_func)
            except: idx_f = 0
            
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)

            conn = conectar_db()
            df_cad_tr_ed = pd.read_sql("SELECT treinamento FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            lista_tr_ed = df_cad_tr_ed["treinamento"].tolist() if not df_cad_tr_ed.empty else []
            
            if t_trein in lista_tr_ed:
                idx_tr_sel = lista_tr_ed.index(t_trein)
                novo_trein_val = st.selectbox("Treinamento", lista_tr_ed, index=idx_tr_sel)
            else:
                novo_trein_val = st.text_input("Treinamento", value=str(t_trein))

            nova_carga_val = st.text_input("Carga Horária", value=str(t_carga) if t_carga else "16 horas")
            novas_pessoas = st.text_input("Pessoas Treinadas", value=str(t_pessoas) if t_pessoas else "1")
            nova_data_real = st.text_input("Data da Realização", value=str(t_data))
            nova_validade = st.text_input("Validade", value=str(t_val) if t_val else "1 ano")
            
            st_limpo_tr = limpar_status_banco(t_status)
            opcoes_st_tr = ["em dia", "vencido"]
            try: idx_st_tr = opcoes_st_tr.index(st_limpo_tr.lower())
            except: idx_st_tr = 0
            novo_status_tr = st.selectbox("Status", ["🟢 em dia", "🔴 vencido"], index=idx_st_tr)

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                novo_mat = t_mat
                novo_c = t_cargo
                novo_s = t_setor
                if not df_funcs_emp.empty:
                    match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                    if not match_f.empty:
                        novo_mat = match_f.iloc[0]["matricula"]
                        novo_c = match_f.iloc[0]["cargo"]
                        novo_s = match_f.iloc[0]["setor"]

                conn = conectar_db()
                conn.execute("""
                    UPDATE treinamentos 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, treinamento = ?, carga_horaria = ?, pessoas_treinadas = ?, data_realizacao = ?, validade = ?, status = ?
                    WHERE id = ?
                """, (
                    novo_func_sel,
                    str(novo_mat or ""),
                    str(novo_c or ""),
                    str(novo_s or ""),
                    formatar_titulo(novo_trein_val),
                    str(nova_carga_val).strip(),
                    str(novas_pessoas).strip(),
                    validar_e_formatar_data_input(nova_data_real),
                    str(nova_validade).strip(),
                    limpar_status_banco(novo_status_tr),
                    id_alvo
                ))
                conn.commit()
                conn.close()
                st.session_state["modal_edit_trein_id"] = None
                st.session_state["sel_id_tr"] = None
                if "editor_selecao_treinamentos" in st.session_state: del st.session_state["editor_selecao_treinamentos"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), t_emp, f"Edição de treinamento ({novo_trein_val}) para {novo_func_sel}")
                st.rerun()

@st.dialog("✏️ Editar Exame Ocupacional")
def dialog_editar_exame(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT empresa, funcionario, tipo_exame, ultimo_exame, proximo_exame, status, matricula, cargo, setor FROM exames WHERE id = ?", (id_alvo,))
    reg_ex = cursor.fetchone()
    conn.close()

    if reg_ex:
        ex_emp, ex_func, ex_tipo, ex_ultimo, ex_proximo, ex_status, ex_mat, ex_cargo, ex_setor = reg_ex
        with st.form(f"form_edicao_exame_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {ex_emp}")
            
            conn = conectar_db()
            df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(ex_emp,))
            conn.close()
            
            lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ex_func]
            if ex_func not in lista_funcs:
                lista_funcs.insert(0, ex_func)
            try: idx_f = lista_funcs.index(ex_func)
            except: idx_f = 0
            
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
            
            opcoes_tipos_ex = ["Admissional", "Periódico", "Retorno ao Trabalho", "Mudança de Riscos", "Demissional"]
            try: idx_tipo_ex = opcoes_tipos_ex.index(ex_tipo)
            except: idx_tipo_ex = 0
            
            novo_tipo_ex = st.selectbox("Tipo de Exame", opcoes_tipos_ex, index=idx_tipo_ex)
            
            novo_ultimo_ex = st.text_input("Data Último Exame", value=str(ex_ultimo))
            novo_proximo_ex = st.text_input("Data Próximo Exame", value=str(ex_proximo))
            
            st_limpo_ex = limpar_status_banco(ex_status)
            opcoes_st_ex = ["Válido", "A Vencer", "Vencido"]
            try: idx_st_ex = opcoes_st_ex.index(st_limpo_ex)
            except: idx_st_ex = 0
            novo_status_ex = st.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"], index=idx_st_ex)

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                novo_mat = ex_mat
                novo_c = ex_cargo
                novo_s = ex_setor
                if not df_funcs_emp.empty:
                    match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                    if not match_f.empty:
                        novo_mat = match_f.iloc[0]["matricula"]
                        novo_c = match_f.iloc[0]["cargo"]
                        novo_s = match_f.iloc[0]["setor"]

                conn = conectar_db()
                conn.execute("""
                    UPDATE exames 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, tipo_exame = ?, ultimo_exame = ?, proximo_exame = ?, status = ?
                    WHERE id = ?
                """, (
                    novo_func_sel,
                    str(novo_mat or ""),
                    str(novo_c or ""),
                    str(novo_s or ""),
                    novo_tipo_ex,
                    validar_e_formatar_data_input(novo_ultimo_ex),
                    validar_e_formatar_data_input(novo_proximo_ex),
                    limpar_status_banco(novo_status_ex),
                    id_alvo
                ))
                conn.commit()
                conn.close()
                sincronizar_status_exames()
                st.session_state["modal_edit_exame_id"] = None
                st.session_state["sel_id_ex"] = None
                if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), ex_emp, f"Edição de exame ({novo_tipo_ex}) para {novo_func_sel}")
                st.rerun()

@st.dialog("✏️ Editar Registro de EPI")
def dialog_editar_epi(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT empresa, funcionario, epi, ca, data_entrega, quantidade, status, matricula, cargo, setor FROM epis WHERE id = ?", (id_alvo,))
    reg_ep = cursor.fetchone()
    conn.close()

    if reg_ep:
        ep_emp, ep_func, ep_epi, ep_ca, ep_dt, ep_qtd, ep_st, ep_mat, ep_cargo, ep_setor = reg_ep
        with st.form(f"form_edicao_epi_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {ep_emp}")
            
            conn = conectar_db()
            df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(ep_emp,))
            conn.close()
            
            lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ep_func]
            if ep_func not in lista_funcs:
                lista_funcs.insert(0, ep_func)
            try: idx_f = lista_funcs.index(ep_func)
            except: idx_f = 0
            
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
            
            novo_epi_nome = st.text_input("EPI", value=str(ep_epi))
            novo_ca = st.text_input("Número do CA", value=str(ep_ca) if ep_ca else "")
            nova_data_ent = st.text_input("Data Entrega", value=str(ep_dt))
            
            try: qtd_val = int(ep_qtd)
            except: qtd_val = 1
            nova_qtd = st.number_input("Quantidade", min_value=1, value=qtd_val)
            
            st_limpo_ep = limpar_status_banco(ep_st)
            opcoes_st_ep = ["Entregue", "Devolvido", "Substituído"]
            try: idx_st_ep = opcoes_st_ep.index(st_limpo_ep)
            except: idx_st_ep = 0
            novo_status_ep = st.selectbox("Status", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"], index=idx_st_ep)

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                novo_mat = ep_mat
                novo_c = ep_cargo
                novo_s = ep_setor
                if not df_funcs_emp.empty:
                    match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                    if not match_f.empty:
                        novo_mat = match_f.iloc[0]["matricula"]
                        novo_c = match_f.iloc[0]["cargo"]
                        novo_s = match_f.iloc[0]["setor"]

                conn = conectar_db()
                conn.execute("""
                    UPDATE epis 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, epi = ?, ca = ?, data_entrega = ?, quantidade = ?, status = ?
                    WHERE id = ?
                """, (
                    novo_func_sel,
                    str(novo_mat or ""),
                    str(novo_c or ""),
                    str(novo_s or ""),
                    formatar_titulo(novo_epi_nome),
                    str(novo_ca).strip(),
                    validar_e_formatar_data_input(nova_data_ent),
                    int(nova_qtd),
                    limpar_status_banco(novo_status_ep),
                    id_alvo
                ))
                conn.commit()
                conn.close()
                st.session_state["modal_edit_epi_id"] = None
                st.session_state["sel_id_epi"] = None
                if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), ep_emp, f"Edição de EPI ({novo_epi_nome}) para {novo_func_sel}")
                st.rerun()

@st.dialog("✏️ Editar Serviço Realizado")
def dialog_editar_servico(id_alvo):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes FROM servicos_realizados WHERE id = ?", (id_alvo,))
    reg_alvo = cursor.fetchone()
    conn.close()

    if reg_alvo:
        e_emp, e_serv, e_data, e_resp, e_obs, e_val, e_status, e_nfes = reg_alvo
        with st.form(f"form_edicao_servico_modal_{id_alvo}"):
            empresas_cad = get_empresas()
            try: idx_emp = empresas_cad.index(e_emp)
            except: idx_emp = 0
            
            nova_empresa = st.selectbox("Empresa Cliente", empresas_cad, index=idx_emp)
            nova_data = st.text_input("Data da Realização (DD/MM/AAAA)", value=str(e_data))
            
            conn = conectar_db()
            df_cad_serv_ed = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            lista_serv_ed = df_cad_serv_ed["servico"].tolist() if not df_cad_serv_ed.empty else []
            
            if e_serv in lista_serv_ed:
                idx_serv = lista_serv_ed.index(e_serv)
                novo_servico = st.selectbox("Serviço Executado", lista_serv_ed, index=idx_serv)
            else:
                novo_servico = st.text_input("Serviço Executado", value=str(e_serv))

            try: float_val = float(e_val)
            except: float_val = 0.0
            
            novo_valor = st.number_input("Valor do Serviço (R$)", min_value=0.0, value=float_val, step=50.0, format="%.2f")
            novo_resp = st.text_input("Responsável Técnico", value=str(e_resp))
            
            status_limpo_atual = limpar_status_banco(e_status)
            opcoes_status = ["Concluído", "Em Andamento", "Agendado", "Cancelado"]
            try: idx_st = opcoes_status.index(status_limpo_atual)
            except: idx_st = 0
            
            novo_status_sel = st.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"], index=idx_st)
            nova_nfes = st.text_input("NFES / Nº da Nota", value=str(e_nfes) if e_nfes else "")
            novas_obs = st.text_input("Observações", value=str(e_obs) if e_obs else "")

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                conn = conectar_db()
                conn.execute("""
                    UPDATE servicos_realizados 
                    SET empresa = ?, servico = ?, data_realizacao = ?, responsavel = ?, observacoes = ?, valor = ?, status = ?, nfes = ?
                    WHERE id = ?
                """, (
                    nova_empresa,
                    formatar_titulo(novo_servico),
                    validar_e_formatar_data_input(nova_data),
                    formatar_titulo(novo_resp),
                    novas_obs,
                    float(novo_valor),
                    limpar_status_banco(novo_status_sel),
                    str(nova_nfes).strip(),
                    id_alvo
                ))
                conn.commit()
                conn.close()
                st.session_state["modal_edit_serv_id"] = None
                st.session_state["sel_id_serv"] = None
                if "editor_selecao_servicos" in st.session_state: del st.session_state["editor_selecao_servicos"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), nova_empresa, f"Edição de serviço ({novo_servico})")
                st.rerun()

def formatar_colunas_tabela(df):
    if df is None or df.empty:
        return df
    
    colunas_texto = [
        "funcionario", "cargo", "setor", "treinamento", "epi", "servico", 
        "observacoes", "responsavel", "nome_empresa", "cidade", "bairro", "endereco", "empresa", "cnae", "documento",
        "Funcionário", "Cargo", "Setor", "Treinamento", "EPI", "Serviço Executado", 
        "Observações", "Responsável", "Nome Empresa", "Cidade", "Bairro", "Endereço", "Empresa", "CNAE", "Documento"
    ]
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: formatar_titulo(x) if isinstance(x, str) else x)

    rename_dict = {
        "id": "ID",
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
        "cnae": "CNAE",
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
        "pessoas_treinadas": "Pessoas Treinadas",
        "data_realizacao": "Data da Realização",
        "validade": "Validade",
        "ultimo_exame": "Último Exame",
        "tipo_exame": "Tipo Exame",
        "proximo_exame": "Próximo Exame",
        "epi": "EPI",
        "ca": "CA",
        "data_entrega": "Data Entrega",
        "quantidade": "Quantidade",
        "servico": "Serviço Executado",
        "observacoes": "Observações",
        "valor": "Valor do Serviço (R$)",
        "nfes": "NFES",
        "documento": "Documento",
        "data_emissao": "Data Emissão"
    }
    return df.rename(columns=rename_dict)

def get_empresas():
    conn = conectar_db()
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

def get_cargos_por_empresa(empresa_nome):
    if not empresa_nome or empresa_nome == "Nenhuma":
        return []
    conn = conectar_db()
    try:
        df_c = pd.read_sql("SELECT DISTINCT cargo FROM cad_cargos WHERE empresa = ? ORDER BY cargo ASC", conn, params=(empresa_nome,))
        conn.close()
        if not df_c.empty:
            return [str(c).strip() for c in df_c["cargo"].tolist() if str(c).strip()]
    except:
        pass
    conn.close()
    return []

def get_setores_por_empresa(empresa_nome):
    if not empresa_nome or empresa_nome == "Nenhuma":
        return []
    conn = conectar_db()
    try:
        df_s = pd.read_sql("SELECT DISTINCT setor FROM cad_setores WHERE empresa = ? ORDER BY setor ASC", conn, params=(empresa_nome,))
        conn.close()
        if not df_s.empty:
            return [str(s).strip() for s in df_s["setor"].tolist() if str(s).strip()]
    except:
        pass
    conn.close()
    return []

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

def normalizar_cnae(cnae_input):
    if not cnae_input:
        return ""
    digitos = "".join(filter(str.isdigit, str(cnae_input)))
    if len(digitos) >= 5:
        return f"{digitos[0:2]}.{digitos[2:4]}-{digitos[4]}"
    return str(cnae_input)

def consultar_grau_risco_por_cnae(cnae_str):
    cnae_fmt = normalizar_cnae(cnae_str)
    if not cnae_fmt:
        return "1"
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT grau_risco FROM grau_risco_nr04 WHERE cnae = ?", (cnae_fmt,))
    res = cursor.fetchone()
    conn.close()
    if res:
        return str(res[0]).strip()
    return "1"

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

def consultar_cnpj(cnpj_str):
    cnpj_limpo = re.sub(r"\D", "", str(cnpj_str))
    if len(cnpj_limpo) == 14:
        lista_cnaes = []
        cnae_principal = ""
        
        try:
            url = f"https://minhareceita.org/{cnpj_limpo}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados = response.json()
                cidade_uf = f"{formatar_titulo(dados.get('municipio', ''))} - {dados.get('uf', '').upper()}" if dados.get('uf') else formatar_titulo(dados.get('municipio', ''))
                
                logradouro = dados.get("logradouro", "")
                numero = dados.get("numero", "")
                complemento = dados.get("complemento", "")
                
                end_completo = formatar_titulo(logradouro)
                if numero: end_completo += f", {numero}"
                if complemento: end_completo += f" - {complemento}"

                cnae_fiscal = dados.get("cnae_fiscal", "")
                cnae_principal = normalizar_cnae(cnae_fiscal)
                if cnae_principal:
                    lista_cnaes.append(f"{cnae_principal} - {dados.get('cnae_fiscal_descricao', '')} (Principal)")

                for sec in dados.get("cnaes_secundarios", []):
                    c_sec = normalizar_cnae(str(sec.get("codigo", "")))
                    if c_sec:
                        lista_cnaes.append(f"{c_sec} - {sec.get('descricao', '')} (Secundário)")

                grau_risco = consultar_grau_risco_por_cnae(cnae_fiscal)

                return {
                    "razao_social": formatar_titulo(dados.get("razao_social", "")),
                    "cep": str(dados.get("cep", "")).zfill(8),
                    "logradouro": end_completo,
                    "bairro": formatar_titulo(dados.get("bairro", "")),
                    "cidade": cidade_uf,
                    "telefone": dados.get("ddd_telefone_1", "") or dados.get("telefone", ""),
                    "email": dados.get("email", ""),
                    "grau_risco": grau_risco,
                    "cnae_principal": cnae_principal,
                    "lista_cnaes": lista_cnaes
                }
        except:
            pass

        try:
            url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados = response.json()
                cidade_uf = f"{formatar_titulo(dados.get('municipio', ''))} - {dados.get('uf', '').upper()}" if dados.get('uf') else formatar_titulo(dados.get('municipio', ''))
                
                logradouro = dados.get("logradouro", "")
                numero = dados.get("numero", "")
                complemento = dados.get("complemento", "")
                
                end_completo = formatar_titulo(logradouro)
                if numero: end_completo += f", {numero}"
                if complemento: end_completo += f" - {complemento}"

                cnae_fiscal = dados.get("cnae_fiscal", "")
                cnae_principal = normalizar_cnae(cnae_fiscal)
                if cnae_principal:
                    lista_cnaes.append(f"{cnae_principal} - {dados.get('cnae_fiscal_descricao', '')} (Principal)")

                for sec in dados.get("cnaes_secundarios", []):
                    c_sec = normalizar_cnae(str(sec.get("codigo", "")))
                    if c_sec:
                        lista_cnaes.append(f"{c_sec} - {sec.get('descricao', '')} (Secundário)")

                grau_risco = consultar_grau_risco_por_cnae(cnae_fiscal)

                return {
                    "razao_social": formatar_titulo(dados.get("razao_social", "")),
                    "cep": str(dados.get("cep", "")).zfill(8),
                    "logradouro": end_completo,
                    "bairro": formatar_titulo(dados.get("bairro", "")),
                    "cidade": cidade_uf,
                    "telefone": dados.get("ddd_telefone_1", ""),
                    "email": dados.get("email", ""),
                    "grau_risco": grau_risco,
                    "cnae_principal": cnae_principal,
                    "lista_cnaes": lista_cnaes
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

def formatar_valor_brasileiro(valor):
    try:
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return "0,00"
        texto = str(valor).strip().replace("R$", "").replace(" ", "")
        if not texto or texto.lower() in ("nan", "none"):
            return "0,00"
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        numero = float(texto)
        return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

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

def filtrar_vencidos_e_proximos(df, coluna_data, coluna_status):
    if df.empty:
        return pd.DataFrame()
    
    hoje = datetime.today()
    indices_validos = []
    
    for idx, row in df.iterrows():
        if "proximo_exame" in df.columns and verificar_cargo_isento_exame(row.get("cargo", "")):
            continue

        st_val = str(row.get(coluna_status, "")).lower()
        dt_val = row.get(coluna_data, "")
        
        if "vencido" in st_val or "vencer" in st_val or "a vencer" in st_val:
            indices_validos.append(idx)
            continue
            
        if dt_val:
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(str(dt_val).strip(), fmt)
                    diff = (dt - hoje).days
                    if diff <= 30:
                        indices_validos.append(idx)
                    break
                except ValueError:
                    continue
    return df.loc[indices_validos] if indices_validos else pd.DataFrame()

# --- CONTROLE DE SESSÃO COM TELA DE LOGIN CENTRALIZADA ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False
if "empresa_usuario" not in st.session_state: st.session_state["empresa_usuario"] = ""
if "nome_usuario" not in st.session_state: st.session_state["nome_usuario"] = ""
if "nivel_permissao" not in st.session_state: st.session_state["nivel_permissao"] = "Somente Visualizar"
if "msg_sucesso" not in st.session_state: st.session_state["msg_sucesso"] = ""
if "ultimo_excluido" not in st.session_state: st.session_state["ultimo_excluido"] = None

if not st.session_state["autenticado"]:
    col_esq, col_centro, col_dir = st.columns([1, 1.4, 1])
    
    with col_centro:
        st.write("")
        st.write("")
        try: st.image("logo.png", width=140)
        except: pass
        
        st.markdown("<h1 style='font-size: 22px; margin-bottom: 0px;'>Cassilab Consultoria e Treinamentos</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: gray; font-size: 14px; margin-top: 0px;'>Sistema de Gestão Integrada em SST</p>", unsafe_allow_html=True)
        st.write("")

        aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔑 Entrar", "📝 Cadastrar", "🔄 Recuperar"])

        with aba_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário ou CPF", value="", autocomplete="username")
                senha_input = st.text_input("Senha", value="", type="password", autocomplete="current-password")
                btn_login = st.form_submit_button("Acessar Sistema", use_container_width=True)
                
                if btn_login:
                    if usuario_input == "admin" and senha_input == "Disc@5232":
                        st.session_state["autenticado"] = True
                        st.session_state["is_admin"] = True
                        st.session_state["empresa_usuario"] = "Todas"
                        st.session_state["nome_usuario"] = "Administrador"
                        st.session_state["nivel_permissao"] = "Fazer Tudo"
                        registrar_log("Administrador", "Todas", "Login no Sistema")
                        st.success("Login efetuado com sucesso!")
                        st.rerun()
                    else:
                        conn = conectar_db()
                        cursor = conn.cursor()
                        cursor.execute("SELECT id, nome, cpf, empresa, email, celular, senha, status, nivel_permissao FROM usuarios_sistema WHERE (nome = ? OR cpf = ?) AND senha = ?", (usuario_input, usuario_input, senha_input))
                        user_db = cursor.fetchone()
                        conn.close()
                        
                        if user_db:
                            status_cad = user_db[7] if len(user_db) > 7 and user_db[7] else 'Ativo'
                            if status_cad == 'Pendente':
                                st.warning("⏳ Seu cadastro ainda está aguardando aprovação do administrador.")
                            elif status_cad == 'Bloqueado':
                                st.error("🚫 Este acesso foi bloqueado pelo administrador.")
                            else:
                                st.session_state["autenticado"] = True
                                st.session_state["is_admin"] = False
                                st.session_state["empresa_usuario"] = user_db[3]
                                st.session_state["nome_usuario"] = user_db[1]
                                st.session_state["nivel_permissao"] = user_db[8] if len(user_db) > 8 and user_db[8] else "Somente Visualizar"
                                registrar_log(user_db[1], user_db[3], "Login no Sistema")
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
                        conn = conectar_db()
                        cursor = conn.cursor()
                        cursor.execute("SELECT nome_empresa FROM empresas WHERE nome_empresa LIKE ? LIMIT 1", (f"%{cad_empresa_busca.strip()}%",))
                        emp_encontrada = cursor.fetchone()
                        
                        if emp_encontrada:
                            empresa_final = emp_encontrada[0]
                            try:
                                cursor.execute("INSERT INTO usuarios_sistema (nome, cpf, empresa, email, celular, senha, status, nivel_permissao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                               (formatar_titulo(cad_nome), cpf_formatado, empresa_final, cad_email.strip(), cad_celular.strip(), cad_senha, 'Pendente', 'Somente Visualizar'))
                                conn.commit()
                                st.success(f"Cadastro realizado com sucesso! Aguardando liberação do administrador.")
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
                        conn = conectar_db()
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
    st.sidebar.info(f"👤 **Perfil:** Colaborador\n🏢 **Empresa:** {st.session_state['empresa_usuario']}\n🔑 **Acesso:** {st.session_state['nivel_permissao']}")

if st.session_state["is_admin"]:
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
else:
    menu = st.sidebar.selectbox("Menu Principal", [
        "Dashboard / Visão Geral",
        "Cadastro de Empresas",
        "Gestão de Funcionários", 
        "Treinamentos", 
        "Exames Ocupacionais", 
        "Controle de EPIs", 
        "Relatórios Consolidados"
    ])

st.sidebar.markdown("---")

if st.session_state.get("ultimo_excluido") is not None:
    if st.sidebar.button("↩️ Desfazer Última Exclusão", use_container_width=True):
        item_ex = st.session_state["ultimo_excluido"]
        tab = item_ex["tabela"]
        dados = item_ex["dados"]
        
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            
            if "id" in dados:
                dados_inserir = {k: v for k, v in dados.items() if k != "id"}
            else:
                dados_inserir = dados
                
            colunas_str = ", ".join(dados_inserir.keys())
            placeholders = ", ".join(["?"] * len(dados_inserir))
            valores = list(dados_inserir.values())
            
            cursor.execute(f"INSERT INTO {tab} ({colunas_str}) VALUES ({placeholders})", valores)
            conn.commit()
            conn.close()
            
            st.session_state["ultimo_excluido"] = None
            st.session_state["msg_sucesso"] = "✅ Registro restaurado com sucesso!"
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Erro ao restaurar: {e}")
else:
    st.sidebar.markdown("<p style='font-size: 11px; color: gray; text-align: center;'>Nenhum item para desfazer</p>", unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("💾 Salvar tudo e Sair"):
    registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), st.session_state.get("empresa_usuario", "Todas"), "Encerrou Sessão / Sair")
    st.session_state["autenticado"] = False
    st.session_state["is_admin"] = False
    st.session_state["empresa_usuario"] = ""
    st.session_state["nome_usuario"] = ""
    st.session_state["nivel_permissao"] = "Somente Visualizar"
    st.sidebar.success("✅ Sessão encerrada com segurança!")
    st.rerun()

is_admin = st.session_state["is_admin"]
emp_usuario = st.session_state["empresa_usuario"]
nivel_permissao = st.session_state["nivel_permissao"]

pode_lancar = is_admin or nivel_permissao in ["Lançar", "Editar", "Fazer Tudo"]
pode_editar = is_admin or nivel_permissao in ["Editar", "Fazer Tudo"]
pode_excluir = is_admin or nivel_permissao == "Fazer Tudo"

if st.session_state.get("msg_sucesso"):
    st.markdown(f"""
        <div style="background-color: #d4edda; color: #155724; padding: 15px 25px; border-radius: 10px; border: 2px solid #28a745; text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.15);">
            {st.session_state["msg_sucesso"]}
        </div>
    """, unsafe_allow_html=True)
    st.session_state["msg_sucesso"] = ""

# ==========================================
# 0. DASHBOARD
# ==========================================
if menu == "Dashboard / Visão Geral":
    col_t1, col_t2 = st.columns([0.8, 0.2])
    with col_t1: st.title("📊 Dashboard - Visão Geral Cassilab SST")
    with col_t2:
        st.write("")
        if st.button("🔄 Atualizar Esta Tela"): st.rerun()
    
    conn = conectar_db()
    try:
        total_empresas = pd.read_sql("SELECT COUNT(DISTINCT nome_empresa) as qtd FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''", conn).iloc[0]["qtd"] if is_admin else (1 if emp_usuario else 0)
        df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios", conn)
        df_ex_all = pd.read_sql("SELECT * FROM exames", conn)
        df_tr_all = pd.read_sql("SELECT * FROM treinamentos", conn)
        df_docs_all = pd.read_sql("SELECT * FROM documentos", conn)
    except:
        total_empresas = 0
        df_funcs_all, df_ex_all, df_tr_all, df_docs_all = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    conn.close()

    if not is_admin and emp_usuario:
        if not df_funcs_all.empty:
            df_funcs_all = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_ex_all.empty:
            df_ex_all = df_ex_all[df_ex_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_tr_all.empty:
            df_tr_all = df_tr_all[df_tr_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_docs_all.empty:
            df_docs_all = df_docs_all[df_docs_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🏢 Empresas Clientes", total_empresas)
    c2.metric("👥 Funcionários", len(df_funcs_all))
    c3.metric("🩺 Exames", len(df_ex_all))
    c4.metric("📚 Treinamentos", len(df_tr_all))
    c5.metric("📄 Documentos", len(df_docs_all))
    st.markdown("---")

    if is_admin:
        st.markdown("### ⚠️ Painel de Alertas (Vencidos e a vencer em até 30 dias) - Acesso Restrito Admin")
        
        # Botão oficial de disparo em massa com trava de envio único para exames, treinamentos e documentos
        if st.button("📧 Disparar Alertas para os Clientes", key="btn_disparar_alertas_producao"):
            remetente = st.session_state.get("email_remetente", "")
            senha = st.session_state.get("senha_remetente", "")
            
            if not remetente or not senha:
                st.error("Configure o e-mail e a senha na aba Administração antes de disparar.")
            else:
                conn = conectar_db()
                df_empresas_cad = pd.read_sql("SELECT nome_empresa, email FROM empresas WHERE email IS NOT NULL AND email != ''", conn)
                conn.close()
                
                if df_empresas_cad.empty:
                    st.warning("Nenhuma empresa cadastrada possui e-mail de contato preenchido.")
                else:
                    enviados_contador = 0
                    hoje_str = datetime.now().strftime("%d/%m/%Y")
                    
                    for _, emp_row in df_empresas_cad.iterrows():
                        nome_emp = emp_row["nome_empresa"]
                        email_dest = emp_row["email"].strip()
                        
                        df_ex_emp = df_ex_all[df_ex_all["empresa"].astype(str).str.strip().str.lower() == str(nome_emp).strip().lower()]
                        df_tr_emp = df_tr_all[df_tr_all["empresa"].astype(str).str.strip().str.lower() == str(nome_emp).strip().lower()]
                        df_docs_emp = df_docs_all[df_docs_all["empresa"].astype(str).str.strip().str.lower() == str(nome_emp).strip().lower()]
                        
                        df_ex_alert = filtrar_vencidos_e_proximos(df_ex_emp, "proximo_exame", "status")
                        df_tr_alert = filtrar_vencidos_e_proximos(df_tr_emp, "validade", "status")
                        df_docs_alert = filtrar_vencidos_e_proximos(df_docs_emp, "validade", "status")
                        
                        novos_itens_para_enviar = []
                        
                        conn = conectar_db()
                        cursor = conn.cursor()
                        
                        # Verifica exames
                        for _, r in df_ex_alert.iterrows():
                            item_id = r["id"]
                            dt_venc = r["proximo_exame"]
                            cursor.execute("""
                                SELECT id FROM historico_alertas_enviados 
                                WHERE empresa = ? AND tipo_item = 'exame' AND id_item = ? AND data_vencimento = ?
                            """, (nome_emp, item_id, dt_venc))
                            if not cursor.fetchone():
                                novos_itens_para_enviar.append(("exame", r))
                                
                        # Verifica treinamentos
                        for _, r in df_tr_alert.iterrows():
                            item_id = r["id"]
                            dt_venc = r["validade"]
                            cursor.execute("""
                                SELECT id FROM historico_alertas_enviados 
                                WHERE empresa = ? AND tipo_item = 'treinamento' AND id_item = ? AND data_vencimento = ?
                            """, (nome_emp, item_id, dt_venc))
                            if not cursor.fetchone():
                                novos_itens_para_enviar.append(("treinamento", r))

                        # Verifica documentos
                        for _, r in df_docs_alert.iterrows():
                            item_id = r["id"]
                            dt_venc = r["validade"]
                            cursor.execute("""
                                SELECT id FROM historico_alertas_enviados 
                                WHERE empresa = ? AND tipo_item = 'documento' AND id_item = ? AND data_vencimento = ?
                            """, (nome_emp, item_id, dt_venc))
                            if not cursor.fetchone():
                                novos_itens_para_enviar.append(("documento", r))
                                
                        conn.close()
                        
                        if novos_itens_para_enviar:
                            texto_alerta = f"Prezada empresa {nome_emp},\n\nO sistema Cassilab SST identificou novas pendências ou vencimentos para a sua equipe:\n\n"
                            
                            exames_novos = [item[1] for item in novos_itens_para_enviar if item[0] == 'exame']
                            treins_novos = [item[1] for item in novos_itens_para_enviar if item[0] == 'treinamento']
                            docs_novos = [item[1] for item in novos_itens_para_enviar if item[0] == 'documento']
                            
                            if exames_novos:
                                texto_alerta += "--- EXAMES OCUPACIONAIS ---\n"
                                for r in exames_novos:
                                    texto_alerta += f"- Funcionário: {r['funcionario']} | Exame: {r['tipo_exame']} | Vencimento: {r['proximo_exame']}\n"
                                texto_alerta += "\n"
                                
                            if treins_novos:
                                texto_alerta += "--- TREINAMENTOS ---\n"
                                for r in treins_novos:
                                    texto_alerta += f"- Funcionário: {r['funcionario']} | Treinamento: {r['treinamento']} | Validade: {r['validade']}\n"
                                texto_alerta += "\n"

                            if docs_novos:
                                texto_alerta += "--- DOCUMENTOS ---\n"
                                for r in docs_novos:
                                    texto_alerta += f"- Documento: {r['documento']} | Validade: {r['validade']}\n"
                                texto_alerta += "\n"
                                
                            texto_alerta += "Atenciosamente,\nCassilab Consultoria e Treinamentos em SST\n\n---\nEste é um e-mail automático enviado pelo sistema de gestão SST. Por favor, não responda a esta mensagem."
                            
                            try:
                                msg = MIMEMultipart()
                                msg['From'] = remetente
                                msg['To'] = email_dest
                                msg['Subject'] = f"⚠️ Alerta de Vencimentos SST - {nome_emp}"
                                msg.attach(MIMEText(texto_alerta, 'plain'))
                                
                                servidor = smtplib.SMTP('smtp.gmail.com', 587)
                                servidor.starttls()
                                servidor.login(remetente, senha)
                                servidor.sendmail(remetente, email_dest, msg.as_string())
                                servidor.quit()
                                
                                conn = conectar_db()
                                cursor = conn.cursor()
                                for tipo_t, r in novos_itens_para_enviar:
                                    dt_val_reg = r["proximo_exame"] if tipo_t == 'exame' else r["validade"]
                                    cursor.execute("""
                                        INSERT INTO historico_alertas_enviados (empresa, tipo_item, id_item, data_vencimento, data_envio)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (nome_emp, tipo_t, r["id"], dt_val_reg, hoje_str))
                                conn.commit()
                                conn.close()
                                
                                enviados_contador += 1
                            except Exception as err_env:
                                pass
                                
                    st.success(f"✅ Disparo concluído! E-mails enviados apenas para {enviados_contador} empresa(s) que possuíam **novos** vencimentos não notificados.")

        col_v1, col_v2, col_v3 = st.columns(3)
        
        with col_v1:
            st.markdown("#### 🩺 Exames (Vencidos / 30 dias)")
            df_ex_alertas = filtrar_vencidos_e_proximos(df_ex_all, "proximo_exame", "status")
            if not df_ex_alertas.empty:
                res_ex = df_ex_alertas[["empresa", "funcionario", "tipo_exame", "proximo_exame"]].drop_duplicates()
                for _, row in res_ex.iterrows():
                    st.warning(f"**{row['empresa']}**\n- {row['funcionario']} ({row['tipo_exame']}) - Vencimento: {row['proximo_exame']}")
            else:
                st.success("Nenhum exame vencido ou próximo.")
                
        with col_v2:
            st.markdown("#### 📚 Treinamentos (Vencidos / 30 dias)")
            df_tr_alertas = filtrar_vencidos_e_proximos(df_tr_all, "validade", "status")
            if not df_tr_alertas.empty:
                res_tr = df_tr_alertas[["empresa", "funcionario", "treinamento"]].drop_duplicates()
                for _, row in res_tr.iterrows():
                    st.error(f"**{row['empresa']}**\n- {row['funcionario']} ({row['treinamento']})")
            else:
                st.success("Nenhum treinamento vencido ou próximo.")
                
        with col_v3:
            st.markdown("#### 📄 Documentos (Vencidos / 30 dias)")
            df_docs_alertas = filtrar_vencidos_e_proximos(df_docs_all, "validade", "status")
            if not df_docs_alertas.empty:
                res_doc = df_docs_alertas[["empresa", "documento"]].drop_duplicates()
                for _, row in res_doc.iterrows():
                    st.error(f"**{row['empresa']}**\n- {row['documento']}")
            else:
                st.success("Nenhum documento vencido ou próximo.")
        st.markdown("---")
    else:
        st.markdown("### ⚠️ Alertas de Vencimentos da sua Empresa")
        
        col_cv1, col_cv2, col_cv3 = st.columns(3)
        
        with col_cv1:
            st.markdown("#### 🩺 Exames (Vencidos / 15 dias)")
            df_ex_alertas_cli = filtrar_vencidos_e_proximos(df_ex_all, "proximo_exame", "status")
            if not df_ex_alertas_cli.empty:
                res_ex_cli = df_ex_alertas_cli[["funcionario", "tipo_exame", "proximo_exame"]].drop_duplicates()
                for _, row in res_ex_cli.iterrows():
                    st.warning(f"- **{row['funcionario']}** ({row['tipo_exame']}) - Vencimento: {row['proximo_exame']}")
            else:
                st.success("Nenhum exame vencido ou próximo.")
                
        with col_cv2:
            st.markdown("#### 📚 Treinamentos (Vencidos / 15 dias)")
            df_tr_alertas_cli = filtrar_vencidos_e_proximos(df_tr_all, "validade", "status")
            if not df_tr_alertas_cli.empty:
                res_tr_cli = df_tr_alertas_cli[["funcionario", "treinamento"]].drop_duplicates()
                for _, row in res_tr_cli.iterrows():
                    st.error(f"- **{row['funcionario']}** ({row['treinamento']})")
            else:
                st.success("Nenhum treinamento vencido ou próximo.")
                
        with col_cv3:
            st.markdown("#### 📄 Documentos (Vencidos / 15 dias)")
            df_docs_alertas_cli = filtrar_vencidos_e_proximos(df_docs_all, "validade", "status")
            if not df_docs_alertas_cli.empty:
                res_doc_cli = df_docs_alertas_cli[["documento"]].drop_duplicates()
                for _, row in res_doc_cli.iterrows():
                    st.error(f"- {row['documento']}")
            else:
                st.success("Nenhum documento vencido ou próximo.")
        st.markdown("---")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🏢 Cadastro de Empresas Clientes")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

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
                        st.session_state["form_grau_risco"] = consultar_grau_risco_por_cnae(codigo_extraido)
                else:
                    st.session_state["form_cnae_consulta"] = st.text_input("CNAE", value=st.session_state["form_cnae_consulta"])

                col_r5_1, col_r5_2 = st.columns(2)
                opcoes_risco = ["1", "2", "3", "4"]
                try: idx_risco = opcoes_risco.index(str(st.session_state["form_grau_risco"]))
                except: idx_risco = 0
                
                grau_risco = col_r5_1.selectbox("Grau de Risco", opcoes_risco, index=idx_risco)
                qtd_funcionarios = col_r5_2.number_input("Qtd de Funcionários", min_value=0, value=0, step=1)
                
                btn_salvar_empresa = st.form_submit_button("💾 Salvar Empresa", use_container_width=False)

                if btn_buscar_cnpj:
                    if cnpj.strip():
                        res_cnpj = consultar_cnpj(cnpj)
                        if res_cnpj:
                            st.session_state["form_emp_nome"] = res_cnpj.get("razao_social", "")
                            st.session_state["form_emp_cnpj"] = formatar_cnpj(cnpj)
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
                        res_cep = consultar_cep(cep_input)
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
                        nome_fmt = formatar_titulo(nome_empresa)
                        cnpj_formatado = formatar_cnpj(cnpj)
                        data_registro_atual = datetime.now().strftime("%d/%m/%Y")
                        
                        conn = conectar_db()
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
                                formatar_titulo(cidade_input), 
                                formatar_titulo(bairro_input), 
                                formatar_titulo(endereco_input), 
                                str(telefone or "").strip(), 
                                str(email or "").strip(), 
                                formatar_titulo(responsavel), 
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
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), nome_fmt, "Cadastro de nova empresa")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esta empresa já está cadastrada (nome ou CNPJ já existente no sistema).")
                        finally:
                            conn.close()
                    else:
                        st.error("O campo 'Nome da Empresa' é obrigatório.")

    st.subheader("Empresas Cadastradas")
    conn = conectar_db()
    df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, cnae, grau_risco, qtd_funcionarios FROM empresas ORDER BY nome_empresa ASC", conn)
    conn.close()

    if not is_admin and not df_emp.empty:
        df_emp = df_emp[df_emp["nome_empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_emp.empty:
        if "data_registro" in df_emp.columns: df_emp["data_registro"] = df_emp["data_registro"].apply(formatar_data_br)
        if "cnpj" in df_emp.columns: df_emp["cnpj"] = df_emp["cnpj"].apply(formatar_cnpj)

        df_emp["_id_banco"] = df_emp["id"]
        
        if "sel_id_emp" not in st.session_state: st.session_state["sel_id_emp"] = None
        df_emp["Selecionar"] = df_emp["_id_banco"] == st.session_state["sel_id_emp"]
        
        cols_emp_ord = ["Selecionar", "_id_banco", "nome_empresa", "cnpj", "cidade", "telefone", "email", "responsavel"]
        df_emp_sel = df_emp[[c for c in cols_emp_ord if c in df_emp.columns]]

        if is_admin:
            df_emp_exibicao = formatar_colunas_tabela(df_emp_sel)
            df_emp_exibicao = adicionar_numeracao(df_emp_exibicao)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha da empresa desejada para visualizar todos os dados completos em pop-up.")
            
            editado_emp = st.data_editor(
                df_emp_exibicao, 
                hide_index=True,
                num_rows="fixed", 
                key="editor_emp", 
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_e = editado_emp[editado_emp["Selecionar"] == True]["_id_banco"].tolist()
            new_e = [uid for uid in curr_e if uid != st.session_state["sel_id_emp"]]
            if new_e:
                st.session_state["sel_id_emp"] = new_e[-1]
                st.rerun()
            elif not curr_e and st.session_state["sel_id_emp"] is not None:
                st.session_state["sel_id_emp"] = None
                st.rerun()

            linhas_sel_emp = editado_emp[editado_emp["Selecionar"] == True]

            if st.button("💾 Salvar Alterações na Tabela de Empresas", use_container_width=True):
                conn = conectar_db()
                cursor = conn.cursor()
                for _, row in editado_emp.iterrows():
                    e_id = row.get("_id_banco", row.get("id"))
                    n_nome = row.get("Nome Empresa", row.get("nome_empresa"))
                    n_cnpj = row.get("CNPJ", row.get("cnpj"))
                    n_cid = row.get("Cidade", row.get("cidade"))
                    n_tel = row.get("Telefone", row.get("telefone"))
                    n_email = row.get("E-mail", row.get("email"))
                    n_resp = row.get("Responsável", row.get("responsavel"))
                    
                    if pd.notna(e_id) and str(e_id).strip() not in ("", "nan", "None"):
                        cursor.execute("""
                            UPDATE empresas 
                            SET nome_empresa = ?, cnpj = ?, cidade = ?, telefone = ?, email = ?, responsavel = ?
                            WHERE id = ?
                        """, (
                            formatar_titulo(n_nome),
                            formatar_cnpj(n_cnpj),
                            formatar_titulo(n_cid),
                            str(n_tel or "").strip(),
                            str(n_email or "").strip(),
                            formatar_titulo(n_resp),
                            int(e_id)
                        ))
                conn.commit()
                conn.close()
                if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de empresas")
                st.rerun()

            if st.button("👁️ Ver Dados Completos da Empresa Selecionada", use_container_width=True):
                if len(linhas_sel_emp) == 1:
                    st.session_state["modal_detalhes_emp_id"] = int(linhas_sel_emp.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione uma empresa marcando o quadradinho.")

            if st.session_state.get("modal_detalhes_emp_id"):
                dialog_detalhes_empresa(st.session_state["modal_detalhes_emp_id"])
                st.session_state["modal_detalhes_emp_id"] = None

            st.markdown("---")
            st.subheader("🗑️ Excluir Empresa Definitivamente")
            with st.form("form_excluir_empresa"):
                lista_nomes_empresas = sorted(df_emp["nome_empresa"].tolist() if "nome_empresa" in df_emp.columns else df_emp["Nome Empresa"].tolist())
                empresa_para_excluir = st.selectbox("Selecione a empresa que deseja excluir:", lista_nomes_empresas)
                chk_excluir_emp = st.checkbox("⚠️ Confirmo que desejo excluir esta empresa e todos os seus dados vinculados permanentemente")
                btn_executar_exclusao = st.form_submit_button("🗑️ Excluir Empresa e Dados Relacionados")

                if btn_executar_exclusao:
                    if chk_excluir_emp and empresa_para_excluir:
                        conn = conectar_db()
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
                        conn.commit()
                        conn.close()
                        if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_para_excluir, "Exclusão definitiva da empresa e dados")
                        st.rerun()
                    else:
                        st.error("Selecione a empresa e marque a caixa de confirmação para autorizar a exclusão.")
        else:
            df_exib_sem_banco = df_emp.drop(columns=["_id_banco"])
            df_exib_sem_banco = adicionar_numeracao(df_exib_sem_banco)
            st.dataframe(formatar_colunas_tabela(df_exib_sem_banco), use_container_width=True, hide_index=True)

# ==========================================
# 2. CADASTROS GERAIS (Apenas Admin)
# ==========================================
elif menu == "Cadastros Gerais":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("⚙️ Gerenciamento de Cadastros Gerais")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador.")
    else:
        empresas_cadastradas = get_empresas()
        aba_g1, aba_g_setores, aba_g2, aba_g3, aba_g4 = st.tabs(["Cargos", "Setores", "Serviços", "Treinamentos", "EPIs"])

        with aba_g1:
            st.subheader("Gerenciar Cargos por Empresa")
            with st.form("form_cad_cargo_unico"):
                empresa_cargo_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_cargo")
                novo_cargo = st.text_input("Novo Cargo")
                btn_add_salvar_cargo = st.form_submit_button("Adicionar e Salvar Cargo")
                
                if btn_add_salvar_cargo:
                    if empresa_cargo_sel != "Nenhuma" and novo_cargo.strip():
                        conn = conectar_db()
                        cursor = conn.cursor()
                        cargo_fmt = formatar_titulo(novo_cargo)
                        
                        cursor.execute("SELECT id FROM cad_cargos WHERE empresa = ? AND cargo = ?", (empresa_cargo_sel, cargo_fmt))
                        existe = cursor.fetchone()
                        
                        if existe:
                            st.error(f"Este cargo já está cadastrado para a empresa {empresa_cargo_sel}.")
                        else:
                            cursor.execute("INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (empresa_cargo_sel, cargo_fmt))
                            conn.commit()
                            if "edit_cargos_tbl" in st.session_state: del st.session_state["edit_cargos_tbl"]
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_cargo_sel, f"Adicionou cargo: {cargo_fmt}")
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do cargo.")

            st.markdown("---")
            filtro_cargo_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_cargo_emp_view")
            
            conn = conectar_db()
            df_cargos_geral = pd.read_sql("SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC", conn)
            conn.close()
            
            if filtro_cargo_emp != "Todas as Empresas" and not df_cargos_geral.empty:
                df_cargos_geral = df_cargos_geral[df_cargos_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_cargo_emp).strip().lower()]

            if not df_cargos_geral.empty:
                if "sel_id_cargo_geral" not in st.session_state: st.session_state["sel_id_cargo_geral"] = None
                df_cargos_geral["_id_banco"] = df_cargos_geral["id"]
                df_cargos_geral["Selecionar"] = df_cargos_geral["_id_banco"] == st.session_state["sel_id_cargo_geral"]
                df_cargos_geral = df_cargos_geral[["Selecionar", "_id_banco", "empresa", "cargo"]]

                df_cargos_ex = formatar_colunas_tabela(df_cargos_geral)
                df_cargos_ex = adicionar_numeracao(df_cargos_ex)
                
                edit_cargos = st.data_editor(
                    df_cargos_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_cargos_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )

                curr_c_geral = edit_cargos[edit_cargos["Selecionar"] == True]["_id_banco"].tolist()
                new_c_geral = [uid for uid in curr_c_geral if uid != st.session_state["sel_id_cargo_geral"]]
                if new_c_geral:
                    st.session_state["sel_id_cargo_geral"] = new_c_geral[-1]
                    st.rerun()
                elif not curr_c_geral and st.session_state["sel_id_cargo_geral"] is not None:
                    st.session_state["sel_id_cargo_geral"] = None
                    st.rerun()

                linhas_sel_cargo = edit_cargos[edit_cargos["Selecionar"] == True]

                col_cg_1, col_cg_2 = st.columns(2)
                if col_cg_1.button("💾 Salvar Alterações na Tabela de Cargos", use_container_width=True):
                    conn = conectar_db()
                    cursor = conn.cursor()
                    for _, row in edit_cargos.iterrows():
                        c_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        c_val = row.get("Cargo", row.get("cargo"))
                        if pd.notna(e_val) and pd.notna(c_val) and str(c_val).strip():
                            if pd.notna(c_id) and str(c_id).strip() not in ("", "nan", "None"):
                                cursor.execute("UPDATE cad_cargos SET empresa=?, cargo=? WHERE id=?", (str(e_val).strip(), formatar_titulo(c_val), int(c_id)))
                    conn.commit()
                    conn.close()
                    if "edit_cargos_tbl" in st.session_state: del st.session_state["edit_cargos_tbl"]
                    st.session_state["sel_id_cargo_geral"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de cargos")
                    st.rerun()

                if col_cg_2.button("🗑️ Excluir Cargo Selecionado", use_container_width=True):
                    if len(linhas_sel_cargo) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "cad_cargos"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_cargo.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "edit_cargos_tbl"
                        st.session_state["sel_id_cargo_geral"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um cargo marcando o quadradinho.")

        with aba_g_setores:
            st.subheader("Gerenciar Setores por Empresa")
            with st.form("form_cad_setor_unico"):
                empresa_setor_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_setor")
                novo_setor = st.text_input("Novo Setor")
                btn_add_salvar_setor = st.form_submit_button("Adicionar e Salvar Setor")
                
                if btn_add_salvar_setor:
                    if empresa_setor_sel != "Nenhuma" and novo_setor.strip():
                        conn = conectar_db()
                        cursor = conn.cursor()
                        setor_fmt = formatar_titulo(novo_setor)
                        
                        cursor.execute("SELECT id FROM cad_setores WHERE empresa = ? AND setor = ?", (empresa_setor_sel, setor_fmt))
                        existe = cursor.fetchone()
                        
                        if existe:
                            st.error(f"Este setor já está cadastrado para a empresa {empresa_setor_sel}.")
                        else:
                            cursor.execute("INSERT INTO cad_setores (empresa, setor) VALUES (?, ?)", (empresa_setor_sel, setor_fmt))
                            conn.commit()
                            if "edit_setores_tbl" in st.session_state: del st.session_state["edit_setores_tbl"]
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_setor_sel, f"Adicionou setor: {setor_fmt}")
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do setor.")

            st.markdown("---")
            filtro_setor_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_setor_emp_view")
            
            conn = conectar_db()
            df_setores_geral = pd.read_sql("SELECT id, empresa, setor FROM cad_setores ORDER BY empresa, setor ASC", conn)
            conn.close()
            
            if filtro_setor_emp != "Todas as Empresas" and not df_setores_geral.empty:
                df_setores_geral = df_setores_geral[df_setores_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_setor_emp).strip().lower()]

            if not df_setores_geral.empty:
                if "sel_id_setor_geral" not in st.session_state: st.session_state["sel_id_setor_geral"] = None
                df_setores_geral["_id_banco"] = df_setores_geral["id"]
                df_setores_geral["Selecionar"] = df_setores_geral["_id_banco"] == st.session_state["sel_id_setor_geral"]
                df_setores_geral = df_setores_geral[["Selecionar", "_id_banco", "empresa", "setor"]]

                df_setores_ex = formatar_colunas_tabela(df_setores_geral)
                df_setores_ex = adicionar_numeracao(df_setores_ex)
                
                edit_setores = st.data_editor(
                    df_setores_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_setores_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )

                curr_s_geral = edit_setores[edit_setores["Selecionar"] == True]["_id_banco"].tolist()
                new_s_geral = [uid for uid in curr_s_geral if uid != st.session_state["sel_id_setor_geral"]]
                if new_s_geral:
                    st.session_state["sel_id_setor_geral"] = new_s_geral[-1]
                    st.rerun()
                elif not curr_s_geral and st.session_state["sel_id_setor_geral"] is not None:
                    st.session_state["sel_id_setor_geral"] = None
                    st.rerun()

                linhas_sel_setor = edit_setores[edit_setores["Selecionar"] == True]

                col_st_1, col_st_2 = st.columns(2)
                if col_st_1.button("💾 Salvar Alterações na Tabela de Setores", use_container_width=True):
                    conn = conectar_db()
                    cursor = conn.cursor()
                    for _, row in edit_setores.iterrows():
                        s_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        st_val = row.get("Setor", row.get("setor"))
                        if pd.notna(e_val) and pd.notna(st_val) and str(st_val).strip():
                            if pd.notna(s_id) and str(s_id).strip() not in ("", "nan", "None"):
                                cursor.execute("UPDATE cad_setores SET empresa=?, setor=? WHERE id=?", (str(e_val).strip(), formatar_titulo(st_val), int(s_id)))
                    conn.commit()
                    conn.close()
                    if "edit_setores_tbl" in st.session_state: del st.session_state["edit_setores_tbl"]
                    st.session_state["sel_id_setor_geral"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de setores")
                    st.rerun()

                if col_st_2.button("🗑️ Excluir Setor Selecionado", use_container_width=True):
                    if len(linhas_sel_setor) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "cad_setores"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_setor.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "edit_setores_tbl"
                        st.session_state["sel_id_setor_geral"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um setor marcando o quadradinho.")

        with aba_g2:
            st.subheader("Gerenciar Tipos de Serviços")
            with st.form("form_cad_servico_unico"):
                novo_serv = st.text_input("Novo Tipo de Serviço")
                btn_add_salvar_serv = st.form_submit_button("Adicionar e Salvar Serviço")
                
                if btn_add_salvar_serv:
                    if novo_serv.strip():
                        conn = conectar_db()
                        try:
                            serv_fmt = formatar_titulo(novo_serv)
                            conn.execute("INSERT INTO cad_servicos (servico) VALUES (?)", (serv_fmt,))
                            conn.commit()
                            if "edit_serv_tbl" in st.session_state: del st.session_state["edit_serv_tbl"]
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", f"Adicionou serviço: {serv_fmt}")
                            st.rerun()
                        except:
                            st.error("Este serviço já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do serviço.")

            st.markdown("---")
            conn = conectar_db()
            df_serv_geral = pd.read_sql("SELECT id, servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            if not df_serv_geral.empty:
                if "sel_id_serv_geral" not in st.session_state: st.session_state["sel_id_serv_geral"] = None
                df_serv_geral["_id_banco"] = df_serv_geral["id"]
                df_serv_geral["Selecionar"] = df_serv_geral["_id_banco"] == st.session_state["sel_id_serv_geral"]
                df_serv_geral = df_serv_geral[["Selecionar", "_id_banco", "servico"]]

                df_serv_ex = formatar_colunas_tabela(df_serv_geral)
                df_serv_ex = adicionar_numeracao(df_serv_ex)
                
                edit_serv = st.data_editor(
                    df_serv_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_serv_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )

                curr_sv_geral = edit_serv[edit_serv["Selecionar"] == True]["_id_banco"].tolist()
                new_sv_geral = [uid for uid in curr_sv_geral if uid != st.session_state["sel_id_serv_geral"]]
                if new_sv_geral:
                    st.session_state["sel_id_serv_geral"] = new_sv_geral[-1]
                    st.rerun()
                elif not curr_sv_geral and st.session_state["sel_id_serv_geral"] is not None:
                    st.session_state["sel_id_serv_geral"] = None
                    st.rerun()

                linhas_sel_serv = edit_serv[edit_serv["Selecionar"] == True]

                col_sv_1, col_sv_2 = st.columns(2)
                if col_sv_1.button("💾 Salvar Alterações na Tabela de Serviços", use_container_width=True):
                    conn = conectar_db()
                    cursor = conn.cursor()
                    for _, row in edit_serv.iterrows():
                        s_id = row.get("_id_banco", row.get("id"))
                        s_val = row.get("Serviço Executado", row.get("servico"))
                        if pd.notna(s_val) and str(s_val).strip():
                            if pd.notna(s_id) and str(s_id).strip() not in ("", "nan", "None"):
                                cursor.execute("UPDATE cad_servicos SET servico=? WHERE id=?", (formatar_titulo(s_val), int(s_id)))
                    conn.commit()
                    conn.close()
                    if "edit_serv_tbl" in st.session_state: del st.session_state["edit_serv_tbl"]
                    st.session_state["sel_id_serv_geral"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de tipos de serviços")
                    st.rerun()

                if col_sv_2.button("🗑️ Excluir Serviço Selecionado", use_container_width=True):
                    if len(linhas_sel_serv) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "cad_servicos"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_serv.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "edit_serv_tbl"
                        st.session_state["sel_id_serv_geral"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

        with aba_g3:
            st.subheader("Gerenciar Tipos de Treinamentos e Carga Horária")
            with st.form("form_cad_treinamento_unico"):
                c_tr_1, c_tr_2 = st.columns(2)
                novo_trein = c_tr_1.text_input("Novo Treinamento")
                nova_carga = c_tr_2.text_input("Carga Horária (ex: 16 horas, 8 horas)")
                btn_add_salvar_trein = st.form_submit_button("Adicionar e Salvar Treinamento")
                
                if btn_add_salvar_trein:
                    if novo_trein.strip():
                        conn = conectar_db()
                        try:
                            trein_fmt = formatar_titulo(novo_trein)
                            conn.execute("INSERT INTO cad_treinamentos (treinamento, carga_horaria) VALUES (?, ?)", (trein_fmt, nova_carga.strip()))
                            conn.commit()
                            if "edit_trein_tbl" in st.session_state: del st.session_state["edit_trein_tbl"]
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", f"Adicionou treinamento: {trein_fmt}")
                            st.rerun()
                        except:
                            st.error("Este treinamento já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do treinamento.")

            st.markdown("---")
            conn = conectar_db()
            df_trein_geral = pd.read_sql("SELECT id, treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            if not df_trein_geral.empty:
                if "sel_id_tr_geral" not in st.session_state: st.session_state["sel_id_tr_geral"] = None
                df_trein_geral["_id_banco"] = df_trein_geral["id"]
                df_trein_geral["Selecionar"] = df_trein_geral["_id_banco"] == st.session_state["sel_id_tr_geral"]
                df_trein_geral = df_trein_geral[["Selecionar", "_id_banco", "treinamento", "carga_horaria"]]

                df_trein_ex = formatar_colunas_tabela(df_trein_geral)
                df_trein_ex = adicionar_numeracao(df_trein_ex)
                
                edit_trein = st.data_editor(
                    df_trein_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_trein_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )

                curr_tr_geral = edit_trein[edit_trein["Selecionar"] == True]["_id_banco"].tolist()
                new_tr_geral = [uid for uid in curr_tr_geral if uid != st.session_state["sel_id_tr_geral"]]
                if new_tr_geral:
                    st.session_state["sel_id_tr_geral"] = new_tr_geral[-1]
                    st.rerun()
                elif not curr_tr_geral and st.session_state["sel_id_tr_geral"] is not None:
                    st.session_state["sel_id_tr_geral"] = None
                    st.rerun()

                linhas_sel_tr_geral = edit_trein[edit_trein["Selecionar"] == True]

                col_tr_1, col_tr_2 = st.columns(2)
                if col_tr_1.button("💾 Salvar Alterações na Tabela de Treinamentos", use_container_width=True):
                    conn = conectar_db()
                    cursor = conn.cursor()
                    for _, row in edit_trein.iterrows():
                        t_id = row.get("_id_banco", row.get("id"))
                        t_val = row.get("Treinamento", row.get("treinamento"))
                        ch_val = row.get("Carga Horária", row.get("carga_horaria", ""))
                        if pd.notna(t_val) and str(t_val).strip():
                            if pd.notna(t_id) and str(t_id).strip() not in ("", "nan", "None"):
                                cursor.execute("UPDATE cad_treinamentos SET treinamento=?, carga_horaria=? WHERE id=?", (formatar_titulo(t_val), str(ch_val).strip(), int(t_id)))
                    conn.commit()
                    conn.close()
                    if "edit_trein_tbl" in st.session_state: del st.session_state["edit_trein_tbl"]
                    st.session_state["sel_id_tr_geral"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de tipos de treinamentos")
                    st.rerun()

                if col_tr_2.button("🗑️ Excluir Treinamento Selecionado", use_container_width=True):
                    if len(linhas_sel_tr_geral) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "cad_treinamentos"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_tr_geral.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "edit_trein_tbl"
                        st.session_state["sel_id_tr_geral"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")

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
                        conn = conectar_db()
                        try:
                            epi_fmt = formatar_titulo(novo_epi_nome)
                            conn.execute("INSERT INTO cad_epis (empresa, epi, ca) VALUES (?, ?, ?)", (empresa_epi_sel, epi_fmt, novo_epi_ca.strip()))
                            conn.commit()
                            if "edit_epis_tbl" in st.session_state: del st.session_state["edit_epis_tbl"]
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_epi_sel, f"Adicionou EPI: {epi_fmt} (CA: {novo_epi_ca})")
                            st.rerun()
                        except:
                            st.error("Este EPI já está cadastrado para esta empresa.")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do EPI.")

            st.markdown("---")
            filtro_epi_geral_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_epi_geral_emp_view")
            
            conn = conectar_db()
            df_epis_geral = pd.read_sql("SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC", conn)
            conn.close()
            
            if filtro_epi_geral_emp != "Todas as Empresas" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[df_epis_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_epi_geral_emp).strip().lower()]

            if not df_epis_geral.empty:
                if "sel_id_epi_geral" not in st.session_state: st.session_state["sel_id_epi_geral"] = None
                df_epis_geral["_id_banco"] = df_epis_geral["id"]
                df_epis_geral["Selecionar"] = df_epis_geral["_id_banco"] == st.session_state["sel_id_epi_geral"]
                df_epis_geral = df_epis_geral[["Selecionar", "_id_banco", "empresa", "epi", "ca"]]

                df_epis_ex = formatar_colunas_tabela(df_epis_geral)
                df_epis_ex = adicionar_numeracao(df_epis_ex)
                
                edit_epis = st.data_editor(
                    df_epis_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_epis_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                    }
                )

                curr_ep_geral = edit_epis[edit_epis["Selecionar"] == True]["_id_banco"].tolist()
                new_ep_geral = [uid for uid in curr_ep_geral if uid != st.session_state["sel_id_epi_geral"]]
                if new_ep_geral:
                    st.session_state["sel_id_epi_geral"] = new_ep_geral[-1]
                    st.rerun()
                elif not curr_ep_geral and st.session_state["sel_id_epi_geral"] is not None:
                    st.session_state["sel_id_epi_geral"] = None
                    st.rerun()

                linhas_sel_epi_geral = edit_epis[edit_epis["Selecionar"] == True]

                col_ep_1, col_ep_2 = st.columns(2)
                if col_ep_1.button("💾 Salvar Alterações na Tabela de EPIs", use_container_width=True):
                    conn = conectar_db()
                    cursor = conn.cursor()
                    for _, row in edit_epis.iterrows():
                        epi_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        epi_val = row.get("EPI", row.get("epi"))
                        ca_val = row.get("CA", row.get("ca"))
                        if pd.notna(e_val) and pd.notna(epi_val) and str(epi_val).strip():
                            if pd.notna(epi_id) and str(epi_id).strip() not in ("", "nan", "None"):
                                cursor.execute("UPDATE cad_epis SET empresa=?, epi=?, ca=? WHERE id=?", (str(e_val).strip(), formatar_titulo(epi_val), str(ca_val).strip(), int(epi_id)))
                    conn.commit()
                    conn.close()
                    if "edit_epis_tbl" in st.session_state: del st.session_state["edit_epis_tbl"]
                    st.session_state["sel_id_epi_geral"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de EPIs cadastrados")
                    st.rerun()

                if col_ep_2.button("🗑️ Excluir EPI Selecionado", use_container_width=True):
                    if len(linhas_sel_epi_geral) == 1:
                        st.session_state["modal_excluir_ativo"] = True
                        st.session_state["modal_excluir_tabela"] = "cad_epis"
                        st.session_state["modal_excluir_id"] = int(linhas_sel_epi_geral.iloc[0]["_id_banco"])
                        st.session_state["modal_excluir_editor_key"] = "edit_epis_tbl"
                        st.session_state["sel_id_epi_geral"] = None
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um EPI marcando o quadradinho.")

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================
elif menu == "Gestão de Funcionários":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("👥 Cadastro de Funcionários")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas_cadastradas = get_empresas()

    if pode_lancar:
        with st.expander("➕ Adicionar Novo Funcionário", expanded=False):
            empresa = st.selectbox("Empresa Cliente", options=empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="func_emp_sel_form") if is_admin else emp_usuario
            if not is_admin:
                st.markdown(f"**Empresa:** {emp_usuario}")
            
            cargos_empresa_lista = get_cargos_por_empresa(empresa)
            setores_empresa_lista = get_setores_por_empresa(empresa)

            c1, c2 = st.columns(2)
            matricula = c1.text_input("Matrícula")
            nome = c1.text_input("Nome do Funcionário")
            
            opcoes_cargo = ["-- Selecionar da lista --", "➕ Digitar novo cargo manualmente..."] + cargos_empresa_lista
            escolha_cargo = c2.selectbox("Cargo", options=opcoes_cargo, key="select_cargo_func")
            
            if escolha_cargo == "➕ Digitar novo cargo manualmente...":
                cargo = c2.text_input("Digite o novo Cargo aqui", key="input_cargo_manual")
            elif escolha_cargo != "-- Selecionar da lista --":
                cargo = escolha_cargo
            else:
                cargo = ""

            opcoes_setor = ["-- Selecionar da lista --", "➕ Digitar novo setor manualmente..."] + setores_empresa_lista
            escolha_setor = c2.selectbox("Setor", options=opcoes_setor, key="select_setor_func")
            
            if escolha_setor == "➕ Digitar novo setor manualmente...":
                setor = c2.text_input("Digite o novo Setor aqui", key="input_setor_manual")
            elif escolha_setor != "-- Selecionar da lista --":
                setor = escolha_setor
            else:
                setor = ""

            cpf = c1.text_input("CPF")
            data_admissao_input = c2.text_input("Data Admissão (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
            status_func = c1.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"])
            
            if st.button("Salvar Funcionário", key="btn_salvar_func_novo"):
                if empresa != "Nenhuma" and nome.strip() and cargo.strip():
                    conn = conectar_db()
                    cursor = conn.cursor()
                    nome_f_fmt = formatar_titulo(nome)
                    cursor.execute("""
                        INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (matricula, nome_f_fmt, formatar_titulo(cargo), formatar_titulo(setor), formatar_cpf(cpf), validar_e_formatar_data_input(data_admissao_input), limpar_status_banco(status_func), empresa))
                    
                    if escolha_cargo == "➕ Digitar novo cargo manualmente..." and cargo.strip():
                        try:
                            cursor.execute("INSERT OR IGNORE INTO cad_cargos (empresa, cargo) VALUES (?, ?)", (empresa, formatar_titulo(cargo)))
                        except:
                            pass
                            
                    if escolha_setor == "➕ Digitar novo setor manualmente..." and setor.strip():
                        try:
                            cursor.execute("INSERT OR IGNORE INTO cad_setores (empresa, setor) VALUES (?, ?)", (empresa, formatar_titulo(setor)))
                        except:
                            pass

                    conn.commit()
                    conn.close()
                    if "editor_selecao_funcionarios" in st.session_state: del st.session_state["editor_selecao_funcionarios"]
                    st.session_state["sel_id_func"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), empresa, f"Cadastrou funcionário: {nome_f_fmt}")
                    st.rerun()
                else:
                    st.error("Preencha a empresa, o nome e o cargo do funcionário.")

    st.subheader("Funcionários Cadastrados")
    filtro_empresa_func = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_func_emp", on_change=reset_func_selection) if is_admin else emp_usuario
    
    conn = conectar_db()
    df = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_empresa_func != "Todas as Empresas" and not df.empty:
        df = df[df["empresa"].astype(str).str.strip().str.lower() == str(filtro_empresa_func).strip().lower()]
    elif not is_admin and not df.empty:
        df = df[df["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
    
    if not df.empty:
        df["data_admissao"] = df["data_admissao"].apply(formatar_data_br)
        df["cpf"] = df["cpf"].apply(formatar_cpf)
        df["status"] = df["status"].apply(lambda x: formatar_status_visual(x, "func"))
        
        df["_id_banco"] = df["id"]

        if is_admin or pode_editar:
            if "sel_id_func" not in st.session_state: st.session_state["sel_id_func"] = None
            df["Selecionar"] = df["_id_banco"] == st.session_state["sel_id_func"]
            cols_func_ord = ["Selecionar", "_id_banco", "empresa", "matricula", "funcionario", "cargo", "setor", "cpf", "data_admissao", "status"]
            df_func_sel = df[[c for c in cols_func_ord if c in df.columns]]
            
            df_func_exib = formatar_colunas_tabela(df_func_sel)
            df_func_exib = adicionar_numeracao(df_func_exib)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do funcionário desejado (ao marcar um, o anterior desmarca sozinho).")
            
            editado_func = st.data_editor(
                df_func_exib, 
                hide_index=True,
                num_rows="fixed", 
                key="editor_selecao_funcionarios", 
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_f = editado_func[editado_func["Selecionar"] == True]["_id_banco"].tolist()
            new_f = [uid for uid in curr_f if uid != st.session_state["sel_id_func"]]
            if new_f:
                st.session_state["sel_id_func"] = new_f[-1]
                st.rerun()
            elif not curr_f and st.session_state["sel_id_func"] is not None:
                st.session_state["sel_id_func"] = None
                st.rerun()

            linhas_sel_func = editado_func[editado_func["Selecionar"] == True]

            col_fb1, col_fb2 = st.columns(2)
            if pode_editar and col_fb1.button("✏️ Editar Funcionário Selecionado", key="btn_editar_func", use_container_width=True):
                if len(linhas_sel_func) == 1:
                    st.session_state["modal_edit_func_id"] = int(linhas_sel_func.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um funcionário marcando o quadradinho.")

            if pode_excluir and col_fb2.button("🗑️ Excluir Funcionário Selecionado", key="btn_excluir_func", use_container_width=True):
                if len(linhas_sel_func) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "base_funcionarios"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_func.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_funcionarios"
                    st.session_state["sel_id_func"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um funcionário marcando o quadradinho.")

            if st.session_state.get("modal_edit_func_id"):
                dialog_editar_funcionario(st.session_state["modal_edit_func_id"])
                st.session_state["modal_edit_func_id"] = None
        else:
            df_exib_sem_banco = df.drop(columns=["_id_banco"])
            df_exib_sem_banco = adicionar_numeracao(df_exib_sem_banco)
            st.dataframe(formatar_colunas_tabela(df_exib_sem_banco), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum funcionário encontrado.")

# ==========================================
# 4. TREINAMENTOS
# ==========================================
elif menu == "Treinamentos":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("📚 Controle de Treinamentos")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas = get_empresas()
    
    if pode_lancar:
        with st.expander("➕ Inserção de Treinamento", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_trein") if is_admin else emp_usuario
            conn = conectar_db()
            df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
            df_cad_trein = pd.read_sql("SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            
            if not df_funcs_all.empty:
                df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()]
            else:
                df_funcs = pd.DataFrame()

            lista_trein_geral = df_cad_trein["treinamento"].tolist() if not df_cad_trein.empty else []
            mapa_carga_trein = dict(zip(df_cad_trein["treinamento"], df_cad_trein["carga_horaria"])) if not df_cad_trein.empty else {}

            if not df_funcs.empty and lista_trein_geral:
                with st.form("form_trein"):
                    c1, c2 = st.columns(2)
                    func_sel = c1.selectbox("Nome do Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == func_sel].iloc[0]
                    
                    trein_sel = c2.selectbox("Treinamento", lista_trein_geral)
                    carga_sugerida = mapa_carga_trein.get(trein_sel, "16 horas")
                    carga_v = c1.text_input("Carga Horária", value=str(carga_sugerida if carga_sugerida else "16 horas"))
                    
                    pessoas_treinadas_v = c2.text_input("Pessoas treinadas (ex: 5, todas)", value="1")
                    dt_real = c1.text_input("Data da Realização", value=datetime.today().strftime("%d/%m/%Y"))
                    val_v = c2.text_input("Validade (ex: 1 ano, 2 anos)", value="1 ano")
                    status_tr = c1.selectbox("Status", ["🟢 em dia", "🔴 vencido"])
                    
                    if st.form_submit_button("Salvar Treinamento"):
                        conn = conectar_db()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO treinamentos (empresa, matricula, funcionario, cargo, setor, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, status) 
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel, str(colab['matricula']), func_sel, str(colab['cargo']), str(colab['setor']), 
                            trein_sel, carga_v, pessoas_treinadas_v, validar_e_formatar_data_input(dt_real), val_v, limpar_status_banco(status_tr)
                        ))
                        conn.commit()
                        conn.close()
                        if "editor_selecao_treinamentos" in st.session_state: del st.session_state["editor_selecao_treinamentos"]
                        st.session_state["sel_id_tr"] = None
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Lançou treinamento ({trein_sel}) para {func_sel}")
                        st.rerun()

    st.subheader("Treinamentos Registrados")
    filtro_tr = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_tr_emp", on_change=reset_tr_selection) if is_admin else emp_usuario
    conn = conectar_db()
    df_tr = pd.read_sql("SELECT * FROM treinamentos ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_tr != "Todas as Empresas" and not df_tr.empty:
        df_tr = df_tr[df_tr["empresa"].astype(str).str.strip().str.lower() == str(filtro_tr).strip().lower()]
    elif not is_admin and not df_tr.empty:
        df_tr = df_tr[df_tr["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_tr.empty:
        df_tr["data_realizacao"] = df_tr["data_realizacao"].apply(formatar_data_br)
        df_tr["status"] = df_tr["status"].apply(lambda x: formatar_status_visual(x, "trein"))
        
        df_tr["_id_banco"] = df_tr["id"]
        
        if is_admin or pode_editar:
            if "sel_id_tr" not in st.session_state: st.session_state["sel_id_tr"] = None
            df_tr["Selecionar"] = df_tr["_id_banco"] == st.session_state["sel_id_tr"]
            cols_tr_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "status"]
            df_tr_sel = df_tr[[c for c in cols_tr_ord if c in df_tr.columns]]
            
            df_tr_exib = formatar_colunas_tabela(df_tr_sel)
            df_tr_exib = adicionar_numeracao(df_tr_exib)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do treinamento desejado (ao marcar um, o anterior desmarca sozinho).")
            
            editado_trein = st.data_editor(
                df_tr_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_treinamentos",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_tr = editado_trein[editado_trein["Selecionar"] == True]["_id_banco"].tolist()
            new_tr = [uid for uid in curr_tr if uid != st.session_state["sel_id_tr"]]
            if new_tr:
                st.session_state["sel_id_tr"] = new_tr[-1]
                st.rerun()
            elif not curr_tr and st.session_state["sel_id_tr"] is not None:
                st.session_state["sel_id_tr"] = None
                st.rerun()

            linhas_sel_tr = editado_trein[editado_trein["Selecionar"] == True]

            col_tb1, col_tb2 = st.columns(2)
            if pode_editar and col_tb1.button("✏️ Editar Treinamento Selecionado", key="btn_editar_trein", use_container_width=True):
                if len(linhas_sel_tr) == 1:
                    st.session_state["modal_edit_trein_id"] = int(linhas_sel_tr.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")

            if pode_excluir and col_tb2.button("🗑️ Excluir Treinamento Selecionado", key="btn_excluir_trein", use_container_width=True):
                if len(linhas_sel_tr) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "treinamentos"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_tr.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_treinamentos"
                    st.session_state["sel_id_tr"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")

            if st.session_state.get("modal_edit_trein_id"):
                dialog_editar_treinamento(st.session_state["modal_edit_trein_id"])
                st.session_state["modal_edit_trein_id"] = None
        else:
            df_tr_exib = df_tr[["empresa", "funcionario", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "status"]]
            df_tr_exib = adicionar_numeracao(df_tr_exib)
            st.dataframe(formatar_colunas_tabela(df_tr_exib), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum treinamento encontrado.")

# ==========================================
# 5. EXAMES OCUPACIONAIS
# ==========================================
elif menu == "Exames Ocupacionais":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🩺 Controle de Exames Ocupacionais")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas = get_empresas()
    
    if pode_lancar:
        with st.expander("➕ Adicionar Novo Exame", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="ex_emp") if is_admin else emp_usuario
            conn = conectar_db()
            df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn)
            conn.close()
            
            if not df_funcs_all.empty:
                df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()]
            else:
                df_funcs = pd.DataFrame()

            if not df_funcs.empty:
                with st.form("form_exame"):
                    nome_sel = st.selectbox("Funcionário", df_funcs["funcionario"].tolist())
                    colab = df_funcs[df_funcs["funcionario"] == nome_sel].iloc[0]
                    c1, c2 = st.columns(2)
                    ultimo = c1.text_input("Data Último Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    tipo_ex = c1.selectbox("Tipo", ["Admissional", "Periódico", "Retorno ao Trabalho", "Mudança de Riscos", "Demissional"])
                    proximo = c2.text_input("Data Próximo Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    status_ex = c2.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"])
                    if st.form_submit_button("Salvar Exame"):
                        conn = conectar_db()
                        conn.execute("INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) VALUES (?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], validar_e_formatar_data_input(ultimo), tipo_ex, validar_e_formatar_data_input(proximo), limpar_status_banco(status_ex)))
                        conn.commit()
                        conn.close()
                        sincronizar_status_exames()
                        if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
                        st.session_state["sel_id_ex"] = None
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Lançou exame ({tipo_ex}) para {nome_sel}")
                        st.rerun()

    st.subheader("Exames Registrados")
    
    col_fx1, col_fx2 = st.columns(2)
    filtro_ex = col_fx1.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ex_emp", on_change=reset_ex_selection) if is_admin else emp_usuario

    conn = conectar_db()
    df_ex = pd.read_sql("SELECT * FROM exames ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_ex != "Todas as Empresas" and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(filtro_ex).strip().lower()]
    elif not is_admin and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_ex.empty:
        df_ex["_dt_prox_temp"] = pd.to_datetime(df_ex["proximo_exame"], dayfirst=True, errors="coerce")
        meses_vencimento_disponiveis = ["Todos os Meses"]
        if df_ex["_dt_prox_temp"].notna().any():
            m_unicos_ex = df_ex["_dt_prox_temp"].dropna().dt.strftime("%m/%Y").unique()
            m_unicos_ex = sorted(m_unicos_ex, key=lambda x: datetime.strptime(x, "%m/%Y"))
            meses_vencimento_disponiveis.extend(m_unicos_ex)

        filtro_mes_vencimento = col_fx2.selectbox("📅 Filtrar por Mês de Vencimento (Passado, Presente ou Futuro)", meses_vencimento_disponiveis, key="filtro_ex_mes_venc", on_change=reset_ex_selection)

        if filtro_mes_vencimento != "Todos os Meses":
            df_ex["_mes_ano_prox"] = df_ex["_dt_prox_temp"].dt.strftime("%m/%Y")
            df_ex = df_ex[df_ex["_mes_ano_prox"] == filtro_mes_vencimento]
            df_ex = df_ex.drop(columns=["_mes_ano_prox"])

        df_ex = df_ex.drop(columns=["_dt_prox_temp"])

    if not df_ex.empty:
        df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br)
        df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br)
        df_ex["status"] = df_ex["status"].apply(lambda x: formatar_status_visual(x, "ex"))
        
        df_ex["_id_banco"] = df_ex["id"]

        if is_admin or pode_editar:
            if "sel_id_ex" not in st.session_state: st.session_state["sel_id_ex"] = None
            df_ex["Selecionar"] = df_ex["_id_banco"] == st.session_state["sel_id_ex"]
            cols_ex_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "proximo_exame", "status"]
            df_ex_sel = df_ex[[c for c in cols_ex_ord if c in df_ex.columns]]
            
            df_ex_exib = formatar_colunas_tabela(df_ex_sel)
            df_ex_exib = adicionar_numeracao(df_ex_exib)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do exame desejado (ao marcar um, o anterior desmarca sozinho).")
            
            editado_ex = st.data_editor(
                df_ex_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_exames",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_ex = editado_ex[editado_ex["Selecionar"] == True]["_id_banco"].tolist()
            new_ex = [uid for uid in curr_ex if uid != st.session_state["sel_id_ex"]]
            if new_ex:
                st.session_state["sel_id_ex"] = new_ex[-1]
                st.rerun()
            elif not curr_ex and st.session_state["sel_id_ex"] is not None:
                st.session_state["sel_id_ex"] = None
                st.rerun()

            linhas_sel_ex = editado_ex[editado_ex["Selecionar"] == True]

            col_ex_b1, col_ex_b2 = st.columns(2)
            if pode_editar and col_ex_b1.button("✏️ Editar Exame Selecionado", key="btn_editar_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    st.session_state["modal_edit_exame_id"] = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um exame marcando o quadradinho.")

            if pode_excluir and col_ex_b2.button("🗑️ Excluir Exame Selecionado", key="btn_excluir_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "exames"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_exames"
                    st.session_state["sel_id_ex"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um exame marcando o quadradinho.")

            if st.session_state.get("modal_edit_exame_id"):
                dialog_editar_exame(st.session_state["modal_edit_exame_id"])
                st.session_state["modal_edit_exame_id"] = None
        else:
            df_ex_exib = df_ex[["empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "proximo_exame", "status"]]
            df_ex_exib = adicionar_numeracao(df_ex_exib)
            st.dataframe(formatar_colunas_tabela(df_ex_exib), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum exame encontrado para este filtro.")

# ==========================================
# 6. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🦺 Controle de Equipamentos de Proteção Individual (EPI)")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas = get_empresas()

    if pode_lancar:
        with st.expander("➕ Registrar Entrega de EPI", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_epi") if is_admin else emp_usuario
            conn_e = conectar_db()
            df_e_all = pd.read_sql("SELECT epi, ca, empresa FROM cad_epis ORDER BY epi ASC", conn_e)
            df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios ORDER BY funcionario ASC", conn_e)
            conn_e.close()
            
            df_e_emp = df_e_all[df_e_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()] if not df_e_all.empty else pd.DataFrame()
            df_funcs = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(empresa_sel).strip().lower()] if not df_funcs_all.empty else pd.DataFrame()

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
                        conn = conectar_db()
                        conn.execute("INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], epi_sel, ca_epi, validar_e_formatar_data_input(data_entrega), int(qtd), limpar_status_banco(status_epi)))
                        conn.commit()
                        conn.close()
                        if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
                        st.session_state["sel_id_epi"] = None
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Desconhecido"), empresa_sel, f"Registrou entrega de EPI ({epi_sel}) para {nome_sel}")
                        st.rerun()

    st.subheader("EPIs Registrados")
    filtro_ep = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ep_emp", on_change=reset_epi_selection) if is_admin else emp_usuario
    conn = conectar_db()
    df_ep = pd.read_sql("SELECT * FROM epis ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_ep != "Todas as Empresas" and not df_ep.empty:
        df_ep = df_ep[df_ep["empresa"].astype(str).str.strip().str.lower() == str(filtro_ep).strip().lower()]
    elif not is_admin and not df_ep.empty:
        df_ep = df_ep[df_ep["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_ep.empty:
        df_ep["data_entrega"] = df_ep["data_entrega"].apply(formatar_data_br)
        df_ep["status"] = df_ep["status"].apply(lambda x: formatar_status_visual(x, "epi"))
        
        df_ep["_id_banco"] = df_ep["id"]

        if is_admin or pode_editar:
            if "sel_id_epi" not in st.session_state: st.session_state["sel_id_epi"] = None
            df_ep["Selecionar"] = df_ep["_id_banco"] == st.session_state["sel_id_epi"]
            cols_ep_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]
            df_ep_sel = df_ep[[c for c in cols_ep_ord if c in df_ep.columns]]
            
            df_ep_exib = formatar_colunas_tabela(df_ep_sel)
            df_ep_exib = adicionar_numeracao(df_ep_exib)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do EPI desejado (ao marcar um, o anterior desmarca sozinho).")
            
            editado_ep = st.data_editor(
                df_ep_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_epis",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_ep = editado_ep[editado_ep["Selecionar"] == True]["_id_banco"].tolist()
            new_ep = [uid for uid in curr_ep if uid != st.session_state["sel_id_epi"]]
            if new_ep:
                st.session_state["sel_id_epi"] = new_ep[-1]
                st.rerun()
            elif not curr_ep and st.session_state["sel_id_epi"] is not None:
                st.session_state["sel_id_epi"] = None
                st.rerun()

            linhas_sel_ep = editado_ep[editado_ep["Selecionar"] == True]

            col_ep_b1, col_ep_b2 = st.columns(2)
            if pode_editar and col_ep_b1.button("✏️ Editar EPI Selecionado", key="btn_editar_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    st.session_state["modal_edit_epi_id"] = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um EPI marcando o quadradinho.")

            if pode_excluir and col_ep_b2.button("🗑️ Excluir EPI Selecionado", key="btn_excluir_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "epis"
                    st.session_state["modal_excluir_id"] = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_epis"
                    st.session_state["sel_id_epi"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um EPI marcando o quadradinho.")

            if st.session_state.get("modal_edit_epi_id"):
                dialog_editar_epi(st.session_state["modal_edit_epi_id"])
                st.session_state["modal_edit_epi_id"] = None
        else:
            df_ep_exib = df_ep[["empresa", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]]
            df_ep_exib = adicionar_numeracao(df_ep_exib)
            st.dataframe(formatar_colunas_tabela(df_ep_exib), use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Nenhum EPI encontrado.")

# ==========================================
# 7. SERVIÇOS REALIZADOS (Exclusivo Admin)
# ==========================================
elif menu == "Serviços Realizados":
    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador.")
    else:
        col_h1, col_h2 = st.columns([0.8, 0.2])
        with col_h1: st.title("🛠️ Controle de Serviços Realizados")
        with col_h2:
            st.write("")
            if st.button("🔄 Atualizar Aba"): st.rerun()

        empresas = get_empresas()
        
        with st.expander("➕ Registrar Novo Serviço Realizado", expanded=False):
            conn = conectar_db()
            df_cad_serv = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
            conn.close()
            lista_serv_cad = df_cad_serv["servico"].tolist() if not df_cad_serv.empty else []
            
            if empresas:
                with st.form("form_servico_tradicional"):
                    c1, c2 = st.columns(2)
                    empresa_sel_srv = c1.selectbox("Empresa Cliente", empresas)
                    data_realizacao_input = c1.text_input("Data da Realização (DD/MM/AAAA)", value=datetime.today().strftime("%d/%m/%Y"))
                    
                    if lista_serv_cad:
                        servico_sel = c1.selectbox("Serviço Executado", lista_serv_cad)
                    else:
                        servico_sel = c1.text_input("Serviço Executado")
                        
                    valor_input = c1.number_input("Valor do Serviço (R$)", min_value=0.0, value=0.0, step=50.0, format="%.2f")
                    
                    responsavel_srv = c2.text_input("Responsável Técnico", value="Luiz Marcelo Fontana")
                    status_srv = c2.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"])
                    nfes_input = c2.text_input("NFES / Nº da Nota")
                    observacoes_srv = c2.text_input("Observações")
                    
                    if st.form_submit_button("Salvar Serviço"):
                        conn = conectar_db()
                        serv_fmt = formatar_titulo(servico_sel)
                        conn.execute("""
                            INSERT INTO servicos_realizados 
                            (empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel_srv, 
                            serv_fmt, 
                            validar_e_formatar_data_input(data_realizacao_input), 
                            formatar_titulo(responsavel_srv), 
                            observacoes_srv, 
                            float(valor_input),
                            limpar_status_banco(status_srv),
                            str(nfes_input).strip()
                        ))
                        conn.commit()
                        conn.close()
                        if "editor_selecao_servicos" in st.session_state: del st.session_state["editor_selecao_servicos"]
                        st.session_state["sel_id_serv"] = None
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_sel_srv, f"Registrou serviço ({serv_fmt})")
                        st.rerun()

        st.subheader("Serviços Registrados")
        
        col_f1, col_f2 = st.columns(2)
        filtro_srv = col_f1.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_srv_emp_trad", on_change=reset_serv_selection)

        conn = conectar_db()
        df_serv = pd.read_sql("SELECT id, empresa, servico, data_realizacao, responsavel, observacoes, status, valor, nfes FROM servicos_realizados", conn)
        conn.close()

        if filtro_srv != "Todas as Empresas" and not df_serv.empty:
            df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == str(filtro_srv).strip().lower()]

        if not df_serv.empty:
            df_serv["_dt_temp"] = pd.to_datetime(df_serv["data_realizacao"], dayfirst=True, errors="coerce")
            
            meses_disponiveis = ["Todos os Meses"]
            if df_serv["_dt_temp"].notna().any():
                m_unicos = df_serv["_dt_temp"].dropna().dt.strftime("%m/%Y").unique()
                m_unicos = sorted(m_unicos, key=lambda x: datetime.strptime(x, "%m/%Y"), reverse=True)
                meses_disponiveis.extend(m_unicos)

            filtro_mes = col_f2.selectbox("Filtrar por Mês", meses_disponiveis, key="filtro_srv_mes", on_change=reset_serv_selection)

            if filtro_mes != "Todos os Meses":
                df_serv["_mes_ano"] = df_serv["_dt_temp"].dt.strftime("%m/%Y")
                df_serv = df_serv[df_serv["_mes_ano"] == filtro_mes]
                df_serv = df_serv.drop(columns=["_mes_ano"])

            df_serv = df_serv.sort_values(by="_dt_temp", ascending=False, na_position="last").drop(columns=["_dt_temp"])

            valor_total_soma = pd.to_numeric(df_serv["valor"], errors="coerce").fillna(0.0).sum()
            st.markdown(f"<p style='font-size: 13px; color: #555; margin-bottom: 8px;'>Total: <b>R$ {formatar_valor_brasileiro(valor_total_soma)}</b></p>", unsafe_allow_html=True)

            if "sel_id_serv" not in st.session_state: st.session_state["sel_id_serv"] = None
            df_serv["_id_banco"] = df_serv["id"]

            df_serv["Selecionar"] = df_serv["_id_banco"] == st.session_state["sel_id_serv"]
            
            df_tabela_sel = df_serv[["Selecionar", "_id_banco", "empresa", "data_realizacao", "servico", "responsavel", "observacoes", "status", "valor", "nfes"]].copy()
            df_tabela_sel["status"] = df_tabela_sel["status"].apply(lambda x: formatar_status_visual(x, "serv"))
            df_tabela_sel["valor_fmt"] = pd.to_numeric(df_tabela_sel["valor"], errors="coerce").fillna(0.0).apply(formatar_valor_brasileiro)
            
            df_tabela_exib = df_tabela_sel[["Selecionar", "_id_banco", "empresa", "data_realizacao", "servico", "responsavel", "observacoes", "status", "valor_fmt", "nfes"]].rename(columns={
                "empresa": "Empresa",
                "data_realizacao": "Data da Realização",
                "servico": "Serviço Executado",
                "responsavel": "Responsável",
                "observacoes": "Observações",
                "status": "Status",
                "valor_fmt": "Valor do Serviço (R$)",
                "nfes": "NFES"
            })
            df_tabela_exib = adicionar_numeracao(df_tabela_exib)

            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do serviço desejado (ao marcar um, o anterior desmarca sozinho).")

            editado_tabela = st.data_editor(
                df_tabela_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_servicos",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True)
                }
            )

            curr_sv = editado_tabela[editado_tabela["Selecionar"] == True]["_id_banco"].tolist()
            new_sv = [uid for uid in curr_sv if uid != st.session_state["sel_id_serv"]]
            if new_sv:
                st.session_state["sel_id_serv"] = new_sv[-1]
                st.rerun()
            elif not curr_sv and st.session_state["sel_id_serv"] is not None:
                st.session_state["sel_id_serv"] = None
                st.rerun()

            linhas_selecionadas = editado_tabela[editado_tabela["Selecionar"] == True]

            col_b1, col_b2 = st.columns(2)
            
            if col_b1.button("✏️ Editar Linha Selecionada", key="btn_ir_editar", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    st.session_state["modal_edit_serv_id"] = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

            if col_b2.button("🗑️ Excluir Linha Selecionada", key="btn_ir_excluir", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "servicos_realizados"
                    st.session_state["modal_excluir_id"] = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_editor_key"] = "editor_selecao_servicos"
                    st.session_state["sel_id_serv"] = None
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

            if st.session_state.get("modal_edit_serv_id"):
                dialog_editar_servico(st.session_state["modal_edit_serv_id"])
                st.session_state["modal_edit_serv_id"] = None
        else:
            st.info("ℹ️ Nenhum serviço registrado para esta seleção.")

# ==========================================
# 8. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🛠️ Painel Administrativo e Controle de Acessos")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    if not is_admin:
        st.warning("🔒 Área exclusiva para o Administrador.")
    else:
        # Configurações de E-mail para Disparo
        st.subheader("⚙️ Configurações de E-mail para Disparos de Alerta")
        with st.form("form_config_email"):
            remetente_email = st.text_input("E-mail de Disparo (Remetente)", value=st.session_state.get("email_remetente", ""))
            senha_email = st.text_input("Senha do E-mail (Gmail App)", type="password", value=st.session_state.get("senha_remetente", ""))
            btn_salvar_config = st.form_submit_button("Salvar Configurações de E-mail")
            
            if btn_salvar_config:
                st.session_state["email_remetente"] = remetente_email.strip()
                st.session_state["senha_remetente"] = senha_email.strip()
                st.success("✅ Configurações de e-mail salvas com sucesso!")

        st.markdown("---")
        st.subheader("👥 Controle de Acessos e Níveis de Permissão")
        st.markdown("Defina o nível de permissão de cada usuário diretamente na tabela abaixo (**Somente Visualizar**, **Lançar**, **Editar** ou **Fazer Tudo**) e clique em salvar.")
        
        conn = conectar_db()
        df_users = pd.read_sql("SELECT id, nome, cpf, empresa, email, celular, status, nivel_permissao FROM usuarios_sistema", conn)
        conn.close()

        if not df_users.empty:
            if "sel_id_user" not in st.session_state: st.session_state["sel_id_user"] = None
            df_users["_id_banco"] = df_users["id"]
            df_users["Selecionar"] = df_users["_id_banco"] == st.session_state["sel_id_user"]

            df_users_exib = df_users[["Selecionar", "_id_banco", "nome", "cpf", "empresa", "email", "celular", "nivel_permissao", "status"]].rename(columns={
                "nome": "Nome", "cpf": "CPF", "empresa": "Empresa", "email": "E-mail", "celular": "Celular", "nivel_permissao": "Nível de Acesso", "status": "Status"
            })
            df_users_exib = adicionar_numeracao(df_users_exib)

            edit_users = st.data_editor(
                df_users_exib,
                hide_index=True,
                num_rows="fixed",
                key="edit_users_acesso",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    "Nível de Acesso": st.column_config.SelectboxColumn(
                        "Nível de Acesso",
                        options=["Somente Visualizar", "Lançar", "Editar", "Fazer Tudo"],
                        required=True
                    )
                }
            )

            curr_u = edit_users[edit_users["Selecionar"] == True]["_id_banco"].tolist()
            new_u = [uid for uid in curr_u if uid != st.session_state["sel_id_user"]]
            if new_u:
                st.session_state["sel_id_user"] = new_u[-1]
                st.rerun()
            elif not curr_u and st.session_state["sel_id_user"] is not None:
                st.session_state["sel_id_user"] = None
                st.rerun()

            sel_users = edit_users[edit_users["Selecionar"] == True]

            col_salvar_niveis, col_esp = st.columns([1, 1])
            if col_salvar_niveis.button("💾 Salvar Alterações de Níveis de Acesso", use_container_width=True):
                conn = conectar_db()
                cursor = conn.cursor()
                for _, row in edit_users.iterrows():
                    u_id = row.get("_id_banco")
                    novo_nivel = row.get("Nível de Acesso")
                    if pd.notna(u_id) and pd.notna(novo_nivel):
                        cursor.execute("UPDATE usuarios_sistema SET nivel_permissao = ? WHERE id = ?", (str(novo_nivel), int(u_id)))
                conn.commit()
                conn.close()
                if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                st.session_state["sel_id_user"] = None
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log("Administrador", "Todas", "Atualização de níveis de permissão de usuários")
                st.rerun()

            st.markdown("")
            cu1, cu2, cu3 = st.columns(3)
            if cu1.button("✅ Aprovar Acesso Selecionado", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    conn = conectar_db()
                    conn.execute("UPDATE usuarios_sistema SET status = 'Ativo' WHERE id = ?", (uid,))
                    conn.commit()
                    conn.close()
                    if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                    st.session_state["sel_id_user"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log("Administrador", "Todas", f"Aprovou acesso do usuário ID {uid}")
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")

            if cu2.button("🚫 Bloquear Acesso Selecionado", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    conn = conectar_db()
                    conn.execute("UPDATE usuarios_sistema SET status = 'Bloqueado' WHERE id = ?", (uid,))
                    conn.commit()
                    conn.close()
                    if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                    st.session_state["sel_id_user"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log("Administrador", "Todas", f"Bloqueou acesso do usuário ID {uid}")
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")

            if cu3.button("🗑️ Excluir Usuário", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "usuarios_sistema"
                    st.session_state["modal_excluir_id"] = uid
                    st.session_state["modal_excluir_editor_key"] = "edit_users_acesso"
                    st.session_state["sel_id_user"] = None
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")
        else:
            st.info("Nenhum usuário cadastrado pendente.")

        st.markdown("---")
        st.subheader("📋 Histórico de Logs e Acessos ao Sistema")
        conn = conectar_db()
        df_logs = pd.read_sql("SELECT data_hora, usuario, empresa, acao FROM logs_sistema ORDER BY id DESC LIMIT 100", conn)
        conn.close()

        if not df_logs.empty:
            df_logs_exib = df_logs.rename(columns={
                "data_hora": "Data / Hora",
                "usuario": "Nome do Usuário",
                "empresa": "Empresa",
                "acao": "Ação / Evento"
            })
            df_logs_exib = adicionar_numeracao(df_logs_exib)
            st.dataframe(df_logs_exib, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum log registrado até o momento.")

        st.markdown("---")
        st.subheader("💾 Backup do Banco de Dados")
        with open(DB_NAME, "rb") as f:
            st.download_button("📥 Baixar Backup (.db)", f, file_name="cassilab_gestao.db", mime="application/octet-stream")

# ==========================================
# 9. RELATÓRIOS CONSOLIDADOS
# ==========================================
elif menu == "Relatórios Consolidados":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("📑 Relatórios Consolidados")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas = get_empresas()
    empresa_filtro = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas) if is_admin else emp_usuario
    
    nome_empresa_arquivo = empresa_filtro if empresa_filtro != "Todas as Empresas" else "Geral"
    titulo_personalizado = f"Relatorio Consolidado - {nome_empresa_arquivo}"

    st.markdown("""
        <style>
        [data-testid="stDataFrame"] div, [data-testid="stDataEditor"] div, th, td {
            color: #000000 !important;
        }
        
        @media print {
            header, footer, [data-testid="stSidebar"], .stButton, .stSelectbox, .stCheckbox, div.row-widget {
                display: none !important;
            }
            
            body, .stApp {
                background-color: white !important;
                color: black !important;
            }

            [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
                border: 1px solid #000000 !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    components.html(
        f"""
        <div style="margin-bottom: 15px;">
            <button onclick="
                parent.document.title = '{titulo_personalizado}';
                parent.window.print();
            " style="
                background-color: #28a745; 
                color: white; 
                border: none; 
                padding: 10px 20px; 
                text-align: center; 
                display: inline-block; 
                font-size: 16px; 
                border-radius: 6px; 
                cursor: pointer; 
                font-weight: bold;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            ">
                🖨️ Imprimir / Salvar Relatório em Alta Nitidez
            </button>
        </div>
        """,
        height=55
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    inc_func = c1.checkbox("👥 Funcionários", value=True)
    inc_ex = c2.checkbox("🩺 Exames", value=True)
    inc_tr = c3.checkbox("📚 Treinamentos", value=True)
    inc_ep = c4.checkbox("🦺 EPIs", value=True)
    inc_srv = c5.checkbox("🛠️ Serviços", value=True) if is_admin else False
    
    conn = conectar_db()
    
    def exibir_tabela_ajustavel(df_input, chave_editor):
        if df_input is not None and not df_input.empty:
            st.data_editor(
                df_input,
                hide_index=True,
                disabled=True,
                use_container_width=True,
                key=chave_editor
            )

    if inc_func:
        st.subheader("Funcionários")
        df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_f.empty:
            df_f = df_f[df_f["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_f.empty:
            df_f = df_f[df_f["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_f.empty: 
            df_f_ex = formatar_colunas_tabela(df_f)
            df_f_ex = adicionar_numeracao(df_f_ex)
            exibir_tabela_ajustavel(df_f_ex, "tabela_rel_func")

    if inc_ex:
        st.subheader("Exames")
        df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_e.empty:
            df_e = df_e[df_e["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_e.empty:
            df_e = df_e[df_e["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_e.empty: 
            df_e_ex = formatar_colunas_tabela(df_e)
            df_e_ex = adicionar_numeracao(df_e_ex)
            exibir_tabela_ajustavel(df_e_ex, "tabela_rel_ex")

    if inc_tr:
        st.subheader("Treinamentos")
        df_t = pd.read_sql("SELECT empresa, funcionario, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, status FROM treinamentos", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_t.empty:
            df_t = df_t[df_t["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_t.empty:
            df_t = df_t[df_t["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_t.empty: 
            df_t_ex = formatar_colunas_tabela(df_t)
            df_t_ex = adicionar_numeracao(df_t_ex)
            exibir_tabela_ajustavel(df_t_ex, "tabela_rel_tr")

    if inc_ep:
        st.subheader("EPIs")
        df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_p.empty:
            df_p = df_p[df_p["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_p.empty:
            df_p = df_p[df_p["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_p.empty: 
            df_p_ex = formatar_colunas_tabela(df_p)
            df_p_ex = adicionar_numeracao(df_p_ex)
            exibir_tabela_ajustavel(df_p_ex, "tabela_rel_ep")

    if inc_srv and is_admin:
        st.subheader("Serviços")
        df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes FROM servicos_realizados", conn)
        if empresa_filtro != "Todas as Empresas" and not df_s.empty:
            df_s = df_s[df_s["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        if not df_s.empty:
            df_s["valor"] = df_s["valor"].apply(formatar_valor_brasileiro)
            df_s["data_realizacao"] = df_s["data_realizacao"].apply(formatar_data_br)
            df_s_ex = formatar_colunas_tabela(df_s)
            df_s_ex = adicionar_numeracao(df_s_ex)
            exibir_tabela_ajustavel(df_s_ex, "tabela_rel_srv")
    conn.close()

# --- CHAMADA GLOBAL DO MODAL DE EXCLUSÃO (PERSISTENTE) ---
if st.session_state.get("modal_excluir_ativo"):
    dialog_excluir(
        st.session_state["modal_excluir_tabela"], 
        st.session_state["modal_excluir_id"], 
        st.session_state["modal_excluir_editor_key"]
    )