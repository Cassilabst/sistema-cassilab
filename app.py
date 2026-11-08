from datetime import datetime, date, timedelta
import re
import sys
import calendar
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
import sqlalchemy
from sqlalchemy import create_engine, text
import sqlite3 as sqlite_original
import pandas as pd

import os
import shutil

# --- CONFIGURAÇÃO PARA RENDER COM SQLITE LOCAL PERSISTENTE ---
if os.path.exists("/data"):
    DB_PATH_PERSISTENT = "/data/cassilab_gestao.db"
    DB_PATH_LOCAL = "cassilab_gestao.db"
    
    # Se o disco persistente ainda estiver vazio, mas o arquivo veio do GitHub, copia para lá automaticamente!
    if not os.path.exists(DB_PATH_PERSISTENT) and os.path.exists(DB_PATH_LOCAL):
        shutil.copy(DB_PATH_LOCAL, DB_PATH_PERSISTENT)
        
    DB_NAME = DB_PATH_PERSISTENT
else:
    DB_NAME = "cassilab_gestao.db"
    
DB_URL = f"sqlite:///{DB_NAME}"

try:
    engine = create_engine(DB_URL, connect_args={"timeout": 30}, pool_pre_ping=True)
except Exception as e:
    st.error(f"❌ Erro ao inicializar o motor do SQLite: {e}")

# --- TRADUTOR PARA O PANDAS ---
if not hasattr(pd, "_original_read_sql"):
    pd._original_read_sql = pd.read_sql

def _patched_read_sql(sql, con, *args, **kwargs):
    # Se 'con' for string ou sqlite3 connection, usa sqlite nativo para máxima performance local
    if isinstance(con, (str, sqlite_original.Connection)):
        return pd._original_read_sql(sql, con, *args, **kwargs)
    return pd._original_read_sql(sql, engine, *args, **kwargs)

pd.read_sql = _patched_read_sql

# --- IMPORTAÇÃO DOS MÓDULOS SEPARADOS ---
from modulo_absenteismo import renderizar_aba_absenteismo
from modulo_admin import renderizar_aba_admin
from modulo_documentos import renderizar_aba_documentos
from modulo_empresas import renderizar_aba_empresas
from modulo_epis import renderizar_aba_epis
from modulo_exames import renderizar_aba_exames
from modulo_funcionarios import renderizar_aba_funcionarios
from modulo_lista_presenca import renderizar_aba_lista_presenca
from modulo_matriz import renderizar_matriz_treinamentos
from modulo_os import renderizar_aba_os
from modulo_relatorios import renderizar_aba_relatorios
from modulo_servicos import renderizar_aba_servicos
from modulo_treinamentos import renderizar_aba_treinamentos
from modulo_senha import renderizar_aba_alterar_senha

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Cassilab - Gestão em SST", page_icon="🛡️", layout="wide"
)

def criar_backup_automatico():
    pass

def formatar_titulo(texto):
    if not texto or pd.isna(texto):
        return ""
    excecoes = {"e", "da", "de", "do", "das", "dos", "em", "para", "com", "S.A."}
    siglas_maiusculas = {
        "ltda", "nr", "me", "mei", "epp", "epi", "cnae", "pgr", "pcmso",
        "pgrs", "pca", "ppr", "npt", "ccb", "aet", "aep", "arp", "ltcat",
        "apr", "ppp", "cipa", "epc", "aso", "sst", "sesmt", "ca", "nfes",
        "dds", "w", "pemt"
    }
    palavras = str(texto).strip().split()
    palavras_formatadas = []
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r"[^a-zA-Z0-9]", "", p).lower()
        if p_limpa in siglas_maiusculas:
            palavras_formatadas.append(p.upper())
        else:
            p_lower = p.lower()
            if i > 0 and p_lower in excecoes:
                palavras_formatadas.append(p_lower)
            else:
                if "-" in p:
                    partes = [
                        sub.upper() if sub.lower() in siglas_maiusculas else sub.capitalize()
                        for sub in p.split("-")
                    ]
                    palavras_formatadas.append("-".join(partes))
                else:
                    palavras_formatadas.append(p.capitalize())
    return " ".join(palavras_formatadas)

def adicionar_numeracao(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    if "Nº" in df.columns:
        df = df.drop(columns=["Nº"])
    df.insert(0, "Nº", range(1, len(df) + 1))
    return df

def registrar_log(usuario, empresa, acao):
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        dt_atual = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute(
            "INSERT INTO logs_sistema (data_hora, usuario, empresa, acao) VALUES (?, ?, ?, ?)",
            (dt_atual, str(usuario), str(empresa), str(acao)),
        )
        conn.commit()
        conn.close()
    except:
        pass

def enviar_email_smtp(destinatario, assunto, corpo):
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("SELECT email, senha_app FROM configuracoes_email LIMIT 1")
        cfg = cursor.fetchone()
        conn.close()
        if not cfg or not cfg[0] or not cfg[1]:
            return False, "Configurações de e-mail não encontradas na aba Administração."
        remetente = cfg[0]
        senha_app = cfg[1]
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo, "plain", "utf-8"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(remetente, senha_app)
        server.sendmail(remetente, destinatario, msg.as_string())
        server.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, str(e)

def calcular_proximo_exame(data_str, meses_str):
    if not data_str or not meses_str:
        return data_str
    try:
        meses_digitos = "".join(filter(str.isdigit, str(meses_str)))
        meses = int(meses_digitos) if meses_digitos else 12
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(data_str).strip(), fmt)
                break
            except ValueError:
                continue
        if not dt:
            return data_str
        mes_novo = dt.month - 1 + meses
        ano_novo = dt.year + mes_novo // 12
        mes_novo = mes_novo % 12 + 1
        ultimo_dia_mes = calendar.monthrange(ano_novo, mes_novo)[1]
        dia_novo = min(dt.day, ultimo_dia_mes)
        dt_futura = dt.replace(year=ano_novo, month=mes_novo, day=dia_novo)
        return dt_futura.strftime("%d/%m/%Y")
    except:
        return data_str

def calcular_proximo_treinamento(data_str, validade_str):
    if not data_str or not validade_str:
        return data_str
    try:
        val_lower = str(validade_str).lower()
        numeros = "".join(filter(str.isdigit, val_lower))
        qtd = int(numeros) if numeros else 12
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(data_str).strip(), fmt)
                break
            except ValueError:
                continue
        if not dt:
            return data_str
        if "ano" in val_lower:
            qtd = qtd * 12
        mes_novo = dt.month - 1 + qtd
        ano_novo = dt.year + mes_novo // 12
        mes_novo = mes_novo % 12 + 1
        ultimo_dia_mes = calendar.monthrange(ano_novo, mes_novo)[1]
        dia_novo = min(dt.day, ultimo_dia_mes)
        dt_futura = dt.replace(year=ano_novo, month=mes_novo, day=dia_novo)
        return dt_futura.strftime("%d/%m/%Y")
    except:
        return data_str

def calcular_proxima_renovacao(data_str, vigencia_str):
    if not data_str or not vigencia_str:
        return data_str
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt_vig = datetime.strptime(str(vigencia_str).strip(), fmt)
            return dt_vig.strftime("%d/%m/%Y")
        except ValueError:
            continue
    try:
        val_lower = str(vigencia_str).lower()
        numeros = "".join(filter(str.isdigit, val_lower))
        qtd = int(numeros) if numeros else 1
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(data_str).strip(), fmt)
                break
            except ValueError:
                continue
        if not dt:
            return data_str
        if "ano" in val_lower:
            ano_novo = dt.year + qtd
            try:
                dt_futura = dt.replace(year=ano_novo)
            except ValueError:
                dt_futura = dt.replace(year=ano_novo, month=2, day=28)
            return dt_futura.strftime("%d/%m/%Y")
        elif "mes" in val_lower or "mês" in val_lower:
            mes_novo = dt.month - 1 + qtd
            ano_novo = dt.year + mes_novo // 12
            mes_novo = mes_novo % 12 + 1
            ultimo_dia_mes = calendar.monthrange(ano_novo, mes_novo)[1]
            dia_novo = min(dt.day, ultimo_dia_mes)
            dt_futura = dt.replace(year=ano_novo, month=mes_novo, day=dia_novo)
            return dt_futura.strftime("%d/%m/%Y")
        elif "dia" in val_lower:
            dt_futura = dt + timedelta(days=qtd)
            return dt_futura.strftime("%d/%m/%Y")
        else:
            ano_novo = dt.year + qtd
            dt_futura = dt.replace(year=ano_novo)
            return dt_futura.strftime("%d/%m/%Y")
    except:
        return data_str

def calcular_status_por_data(data_str):
    if not data_str or pd.isna(data_str):
        return "Válido"
    hoje = datetime.today().date()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(data_str).strip(), fmt).date()
            diff = (dt - hoje).days
            if diff < 0:
                return "Vencido"
            elif diff <= 30:
                return "A Vencer"
            else:
                return "Válido"
        except ValueError:
            continue
    return "Válido"

def calcular_status_exame(data_str):
    if not data_str or pd.isna(data_str):
        return "Válido"
    hoje = datetime.today().date()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(data_str).strip(), fmt).date()
            diff = (dt - hoje).days
            if diff < 0:
                return "Vencido"
            elif diff <= 15:
                return "A Vencer"
            else:
                return "Válido"
        except ValueError:
            continue
    return "Válido"

def sincronizar_status_exames():
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        df = pd.read_sql("SELECT id, proximo_exame FROM exames", conn)
        if not df.empty:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                prox = row["proximo_exame"]
                novo_st = calcular_status_exame(prox)
                cursor.execute("UPDATE exames SET status = ? WHERE id = ?", (novo_st, row["id"]))
            conn.commit()
        conn.close()
    except:
        pass

def sincronizar_status_treinamentos():
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        df = pd.read_sql("SELECT id, proximo_treinamento FROM treinamentos", conn)
        if not df.empty:
            cursor = conn.cursor()
            hoje = datetime.today().date()
            for _, row in df.iterrows():
                prox = row["proximo_treinamento"]
                novo_st = "em dia"
                if prox and not pd.isna(prox):
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                        try:
                            dt = datetime.strptime(str(prox).strip(), fmt).date()
                            diff = (dt - hoje).days
                            if diff < 0:
                                novo_st = "vencido"
                            else:
                                novo_st = "em dia"
                            break
                        except ValueError:
                            continue
                cursor.execute("UPDATE treinamentos SET status = ? WHERE id = ?", (novo_st, row["id"]))
            conn.commit()
        conn.close()
    except:
        pass

def sincronizar_status_documentos():
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        df = pd.read_sql("SELECT id, proxima_renovacao FROM documentos", conn)
        if not df.empty:
            cursor = conn.cursor()
            hoje = datetime.today().date()
            for _, row in df.iterrows():
                prox = row["proxima_renovacao"]
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
                cursor.execute("UPDATE documentos SET status = ? WHERE id = ?", (novo_st, row["id"]))
            conn.commit()
        conn.close()
    except:
        pass

def atualizar_cargo_setor_treinamentos_antigos():
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE treinamentos 
            SET cargo = COALESCE(NULLIF(cargo, ''), (SELECT b.cargo FROM base_funcionarios b WHERE b.funcionario = treinamentos.funcionario AND b.empresa = treinamentos.empresa LIMIT 1)),
                setor = COALESCE(NULLIF(setor, ''), (SELECT b.setor FROM base_funcionarios b WHERE b.funcionario = treinamentos.funcionario AND b.empresa = treinamentos.empresa LIMIT 1))
            WHERE cargo IS NULL OR cargo = '' OR setor IS NULL OR setor = ''
        """)
        conn.commit()
        conn.close()
    except:
        pass

def atualizar_validade_treinamentos_para_meses():
    try:
        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("SELECT id, validade, data_realizacao FROM treinamentos WHERE validade LIKE '%ano%'")
        rows = cursor.fetchall()
        for row in rows:
            rid, val_str, dt_real = row[0], str(row[1]).lower(), row[2]
            numeros = "".join(filter(str.isdigit, val_str))
            anos = int(numeros) if numeros else 1
            meses = anos * 12
            nova_val = f"{meses} meses"
            novo_prox = calcular_proximo_treinamento(dt_real, nova_val)
            cursor.execute("UPDATE treinamentos SET validade = ?, proximo_treinamento = ? WHERE id = ?", (nova_val, novo_prox, rid))
        conn.commit()
        conn.close()
    except:
        pass

def init_db():
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS base_funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grau_risco_nr04 (
            cnae TEXT PRIMARY KEY,
            descricao TEXT,
            grau_risco TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_email (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            senha_app TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_enviados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            tipo_item TEXT,
            item_id INTEGER,
            data_vencimento TEXT,
            data_envio TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matriz_treinamentos_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            treinamento TEXT,
            carga_horaria TEXT,
            validade TEXT,
            modalidade TEXT,
            disponibilidade TEXT,
            valor REAL DEFAULT 0,
            UNIQUE(empresa, treinamento)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matriz_treinamentos_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            funcionario TEXT,
            treinamento TEXT,
            obrigatoriedade TEXT,
            UNIQUE(empresa, funcionario, treinamento)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS absenteismo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            nome TEXT,
            turno TEXT,
            funcao TEXT,
            setor TEXT,
            tipo_atestado TEXT,
            horas_perdidas REAL,
            horas_previstas REAL,
            dias_perdidos REAL,
            inicio_afastamento TEXT,
            fim_afastamento TEXT,
            local_atendimento TEXT,
            cid TEXT,
            conselho TEXT,
            dt_adm TEXT,
            dt_nasc TEXT,
            sexo TEXT,
            mes TEXT
        )
    """)
    
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
            qtd_funcionarios INTEGER,
            porte TEXT
        )
    """)
    
    for sql_alt in [
        "ALTER TABLE empresas ADD COLUMN data_registro TEXT;",
        "ALTER TABLE empresas ADD COLUMN cnae TEXT;",
        "ALTER TABLE empresas ADD COLUMN porte TEXT;",
        
        "CREATE TABLE IF NOT EXISTS base_funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, matricula TEXT, funcionario TEXT, cargo TEXT, setor TEXT, cpf TEXT, data_admissao TEXT, status TEXT, empresa TEXT, data_nascimento TEXT);",
        "ALTER TABLE base_funcionarios ADD COLUMN data_nascimento TEXT;",
        
        "CREATE TABLE IF NOT EXISTS usuarios_sistema (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cpf TEXT, empresa TEXT, email TEXT, celular TEXT, senha TEXT, status TEXT DEFAULT 'Pendente', nivel_permissao TEXT DEFAULT 'Somente Visualizar');",
        "ALTER TABLE usuarios_sistema ADD COLUMN email TEXT;",
        "ALTER TABLE usuarios_sistema ADD COLUMN celular TEXT;",
        "ALTER TABLE usuarios_sistema ADD COLUMN status TEXT;",
        "ALTER TABLE usuarios_sistema ADD COLUMN nivel_permissao TEXT;",
        
        "CREATE TABLE IF NOT EXISTS exames (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, matricula TEXT, funcionario TEXT, cargo TEXT, setor TEXT, ultimo_exame TEXT, periodicidade TEXT, tipo_exame TEXT, proximo_exame TEXT, status TEXT);",
        "ALTER TABLE exames ADD COLUMN periodicidade TEXT;",
        
        "CREATE TABLE IF NOT EXISTS treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, matricula TEXT, funcionario TEXT, cargo TEXT, setor TEXT, treinamento TEXT, carga_horaria TEXT, pessoas_treinadas TEXT, data_realizacao TEXT, validade TEXT, proximo_treinamento TEXT, status TEXT);",
        "ALTER TABLE treinamentos ADD COLUMN pessoas_treinadas TEXT;",
        "ALTER TABLE treinamentos ADD COLUMN validade TEXT;",
        "ALTER TABLE treinamentos ADD COLUMN proximo_treinamento TEXT;",
        
        "CREATE TABLE IF NOT EXISTS epis (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, matricula TEXT, funcionario TEXT, cargo TEXT, setor TEXT, epi TEXT, ca TEXT, data_entrega TEXT, quantidade INTEGER, status TEXT);",
        
        "CREATE TABLE IF NOT EXISTS servicos_realizados (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, servico TEXT, data_realizacao TEXT, responsavel TEXT, observacoes TEXT, valor REAL DEFAULT 0, status TEXT, nfes TEXT);",
        "ALTER TABLE servicos_realizados ADD COLUMN valor REAL DEFAULT 0;",
        "ALTER TABLE servicos_realizados ADD COLUMN nfes TEXT;",
        
        "CREATE TABLE IF NOT EXISTS documentos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, documento TEXT, data_emissao TEXT, vigencia TEXT, proxima_renovacao TEXT, status TEXT);",
        "ALTER TABLE documentos ADD COLUMN proxima_renovacao TEXT;",
        
        "CREATE TABLE IF NOT EXISTS logs_sistema (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT, usuario TEXT, empresa TEXT, acao TEXT);",
        "CREATE TABLE IF NOT EXISTS cad_cargos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, cargo TEXT);",
        "CREATE TABLE IF NOT EXISTS cad_setores (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, setor TEXT);",
        "CREATE TABLE IF NOT EXISTS cad_epis (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, epi TEXT, ca TEXT, UNIQUE(empresa, epi));",
        
        "CREATE TABLE IF NOT EXISTS cad_treinamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, treinamento TEXT, carga_horaria TEXT, UNIQUE(empresa, treinamento));",
    
        "CREATE TABLE IF NOT EXISTS cad_servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, servico TEXT UNIQUE);",
       ]:
        try:
            cursor.execute(sql_alt)
            conn.commit()
        except:
            try:
                conn.rollback()
            except:
                pass

    try:
        cursor.execute("UPDATE usuarios_sistema SET status = 'Ativo' WHERE status IS NULL OR status = '';")
        cursor.execute("UPDATE usuarios_sistema SET nivel_permissao = 'Somente Visualizar' WHERE nivel_permissao IS NULL OR nivel_permissao = '';")
        conn.commit()
    except:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM usuarios_sistema WHERE nivel_permissao = 'Fazer Tudo'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO usuarios_sistema (nome, cpf, empresa, email, celular, senha, status, nivel_permissao)
                VALUES ('Administrador', '000.000.000-00', 'Todas', 'admin@cassilab.com', '', 'admin123', 'Ativo', 'Fazer Tudo')
            """)
            conn.commit()
    except:
        pass

    conn.close()

init_db()
atualizar_cargo_setor_treinamentos_antigos()
atualizar_validade_treinamentos_para_meses()
criar_backup_automatico()
sincronizar_status_exames()
sincronizar_status_treinamentos()
sincronizar_status_documentos()

# --- IMPORTAÇÃO DOS MÓDULOS DE INTERFACE ---
from modulo_absenteismo import renderizar_aba_absenteismo
from modulo_admin import renderizar_aba_admin
from modulo_documentos import renderizar_aba_documentos
from modulo_empresas import renderizar_aba_empresas
from modulo_epis import renderizar_aba_epis
from modulo_exames import renderizar_aba_exames
from modulo_funcionarios import renderizar_aba_funcionarios
from modulo_lista_presenca import renderizar_aba_lista_presenca
from modulo_matriz import renderizar_matriz_treinamentos
from modulo_os import renderizar_aba_os
from modulo_relatorios import renderizar_aba_relatorios
from modulo_servicos import renderizar_aba_servicos
from modulo_treinamentos import renderizar_aba_treinamentos
from modulo_senha import renderizar_aba_alterar_senha

def atualizar_filtro_empresa(empresa_nome):
    # Se a empresa_nome for válida e não vazia, atualiza os filtros normais
    if empresa_nome and str(empresa_nome).strip() != "":
        st.session_state["sel_emp_cargo"] = empresa_nome
        st.session_state["filtro_cargo_emp_view"] = empresa_nome
        st.session_state["sel_emp_epi_geral"] = empresa_nome
        st.session_state["filtro_epi_geral_emp_view"] = empresa_nome
        st.session_state["filtro_treinamento_emp_view"] = empresa_nome
    else:
        # Se estiver vazia ou for "Todas", define os textos padrão seguros
        st.session_state["sel_emp_cargo"] = "Nenhuma"
        st.session_state["filtro_cargo_emp_view"] = "Todas as Empresas"
        st.session_state["sel_emp_epi_geral"] = "Nenhuma"
        st.session_state["filtro_epi_geral_emp_view"] = "Todas as Empresas"
        st.session_state["filtro_treinamento_emp_view"] = "Todas as Empresas"
    
    if empresa_nome and empresa_nome != "Todas":
        st.session_state["sel_emp_cargo"] = empresa_nome
        st.session_state["filtro_cargo_emp_view"] = empresa_nome
        st.session_state["sel_emp_epi_geral"] = empresa_nome
        st.session_state["filtro_epi_geral_emp_view"] = empresa_nome
    else:
        st.session_state["sel_emp_cargo"] = "Nenhuma"
        st.session_state["filtro_cargo_emp_view"] = "Todas as Empresas"
        st.session_state["sel_emp_epi_geral"] = "Nenhuma"
        st.session_state["filtro_epi_geral_emp_view"] = "Todas as Empresas"

def reset_func_selection():
    if "editor_selecao_funcionarios" in st.session_state:
        del st.session_state["editor_selecao_funcionarios"]
    st.session_state["sel_id_func"] = None
    st.session_state["modal_edit_func_id"] = None

def reset_tr_selection():
    if "editor_selecao_treinamentos" in st.session_state:
        del st.session_state["editor_selecao_treinamentos"]
    st.session_state["sel_id_tr"] = None
    st.session_state["modal_edit_trein_id"] = None

def reset_ex_selection():
    if "editor_selecao_exames" in st.session_state:
        del st.session_state["editor_selecao_exames"]
    st.session_state["sel_id_ex"] = None
    st.session_state["modal_edit_exame_id"] = None

def reset_epi_selection():
    if "editor_selecao_epis" in st.session_state:
        del st.session_state["editor_selecao_epis"]
    st.session_state["sel_id_epi"] = None
    st.session_state["modal_edit_epi_id"] = None

def reset_serv_selection():
    if "editor_selecao_servicos" in st.session_state:
        del st.session_state["editor_selecao_servicos"]
    st.session_state["sel_id_serv"] = None
    st.session_state["modal_edit_serv_id"] = None

def reset_doc_selection():
    if "editor_selecao_documentos" in st.session_state:
        del st.session_state["editor_selecao_documentos"]
    st.session_state["sel_id_doc"] = None
    st.session_state["modal_edit_doc_id"] = None

@st.dialog("✏️ Editar Funcionário")
def dialog_editar_funcionario(id_alvo):
    def formatar_data_flexivel_local(texto):
        if not texto:
            return ""
        digitos = "".join(filter(str.isdigit, str(texto)))
        if len(digitos) == 8:
            return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"
        return str(texto).strip()

    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, matricula, funcionario, cargo, setor, cpf,"
        " data_admissao, status, data_nascimento FROM base_funcionarios WHERE id ="
        " ?",
        (id_alvo,),
    )
    reg_func = cursor.fetchone()
    conn.close()
    if reg_func:
        f_emp, f_mat, f_nome, f_cargo, f_setor, f_cpf, f_dt, f_st, f_nasc = reg_func
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
                novo_setor = st.text_input(
                    "Setor", value=str(f_setor) if f_setor else ""
                )
            novo_cpf = st.text_input("CPF", value=str(f_cpf) if f_cpf else "")
            nova_data_adm = st.text_input(
                "Data Admissão", value=str(f_dt) if f_dt else ""
            )
            nova_data_nasc = st.text_input(
                "Data de Nascimento", value=str(f_nasc) if f_nasc else ""
            )
            st_limpo_f = limpar_status_banco(f_st)
            opcoes_st_f = ["Ativo", "Afastado", "Desligado"]
            try:
                idx_st_f = opcoes_st_f.index(st_limpo_f)
            except:
                idx_st_f = 0
            novo_status_f = st.selectbox(
                "Status",
                ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"],
                index=idx_st_f,
            )

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                dt_adm_fmt = formatar_data_flexivel_local(nova_data_adm)
                dt_nasc_fmt = formatar_data_flexivel_local(nova_data_nasc)
                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE base_funcionarios 
                    SET matricula = ?, funcionario = ?, cargo = ?, setor = ?, cpf = ?, data_admissao = ?, status = ?, data_nascimento = ?
                    WHERE id = ?
                """,
                    (
                        str(novo_mat).strip(),
                        formatar_titulo(novo_nome),
                        formatar_titulo(novo_cargo),
                        formatar_titulo(novo_setor),
                        formatar_cpf(novo_cpf),
                        dt_adm_fmt,
                        limpar_status_banco(novo_status_f),
                        dt_nasc_fmt,
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                st.session_state["modal_edit_func_id"] = None
                st.session_state["last_sel_func_id"] = None
                st.session_state["msg_sucesso"] = "✅ Alterações salvas com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    f_emp,
                    f"Edição do funcionário: {formatar_titulo(novo_nome)}",
                )
                st.rerun()

@st.dialog("✏️ Editar Treinamento")
def dialog_editar_treinamento(id_alvo):
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, funcionario, treinamento, carga_horaria,"
        " pessoas_treinadas, data_realizacao, validade, proximo_treinamento,"
        " status, matricula, cargo, setor FROM treinamentos WHERE id = ?",
        (id_alvo,),
    )
    reg_tr = cursor.fetchone()
    df_cad_tr_ed = pd.read_sql(
        "SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY"
        " treinamento ASC",
        conn,
    )
    conn.close()
    if reg_tr:
        (
            t_emp,
            t_func,
            t_trein,
            t_carga,
            t_pessoas,
            t_data,
            t_val,
            t_prox,
            t_status,
            t_mat,
            t_cargo,
            t_setor,
        ) = reg_tr
        with st.form(f"form_edicao_trein_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {t_emp}")
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_funcs_emp = pd.read_sql(
                "SELECT matricula, funcionario, cargo, setor FROM base_funcionarios"
                " WHERE empresa = ? ORDER BY funcionario ASC",
                conn,
                params=(t_emp,),
            )
            conn.close()
            lista_funcs = (
                df_funcs_emp["funcionario"].tolist()
                if not df_funcs_emp.empty
                else [t_func]
            )
            if t_func not in lista_funcs:
                lista_funcs.insert(0, t_func)
            try:
                idx_f = lista_funcs.index(t_func)
            except:
                idx_f = 0
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
            lista_tr_ed = (
                df_cad_tr_ed["treinamento"].tolist()
                if not df_cad_tr_ed.empty
                else []
            )
            lista_cargas_gerais = (
                df_cad_tr_ed["carga_horaria"].dropna().unique().tolist()
            )
            if not lista_cargas_gerais:
                lista_cargas_gerais = ["8 horas", "16 horas", "20 horas", "40 horas"]
            if t_trein in lista_tr_ed:
                idx_tr_sel = lista_tr_ed.index(t_trein)
                novo_trein_val = st.selectbox(
                    "Treinamento", lista_tr_ed, index=idx_tr_sel
                )
            else:
                novo_trein_val = st.text_input("Treinamento", value=str(t_trein))
            try:
                idx_carga = lista_cargas_gerais.index(t_carga)
            except:
                idx_carga = 0
            nova_carga_val = st.selectbox(
                "Carga Horária", lista_cargas_gerais, index=idx_carga
            )
            opcoes_modalidade = ["Presencial", "Semi-presencial", "EaD"]
            try:
                idx_mod = opcoes_modalidade.index(str(t_pessoas))
            except:
                idx_mod = 0
            nova_modalidade = st.selectbox(
                "Modalidade", opcoes_modalidade, index=idx_mod
            )
            nova_data_real = st.text_input("Data da Realização", value=str(t_data))
            nova_validade = st.text_input(
                "Validade (ex: 12 meses)",
                value=str(t_val) if t_val else "12 meses",
            )
            proximo_calc_ed = calcular_proximo_treinamento(
                nova_data_real, nova_validade
            )
            novo_proximo_tr = st.text_input(
                "Data do Próximo Treinamento",
                value=str(t_prox) if t_prox else proximo_calc_ed,
            )
            st_limpo_tr = limpar_status_banco(t_status)
            opcoes_st_tr = ["em dia", "vencido"]
            try:
                idx_st_tr = opcoes_st_tr.index(st_limpo_tr.lower())
            except:
                idx_st_tr = 0
            novo_status_tr = st.selectbox(
                "Status", ["🟢 em dia", "🔴 vencido"], index=idx_st_tr
            )

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
                proximo_final_ed = (
                    calcular_proximo_treinamento(nova_data_real, nova_validade)
                    if not novo_proximo_tr
                    else validar_e_formatar_data_input(novo_proximo_tr)
                )
                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE treinamentos 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, treinamento = ?, carga_horaria = ?, pessoas_treinadas = ?, data_realizacao = ?, validade = ?, proximo_treinamento = ?, status = ?
                    WHERE id = ?
                """,
                    (
                        novo_func_sel,
                        str(novo_mat or ""),
                        str(novo_c or ""),
                        str(novo_s or ""),
                        formatar_titulo(novo_trein_val),
                        str(nova_carga_val).strip(),
                        str(nova_modalidade).strip(),
                        validar_e_formatar_data_input(nova_data_real),
                        str(nova_validade).strip(),
                        proximo_final_ed,
                        limpar_status_banco(novo_status_tr),
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                sincronizar_status_treinamentos()
                st.session_state["modal_edit_trein_id"] = None
                st.session_state["sel_id_tr"] = None
                if "editor_selecao_treinamentos" in st.session_state:
                    del st.session_state["editor_selecao_treinamentos"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    t_emp,
                    f"Edição de treinamento ({novo_trein_val}) para {novo_func_sel}",
                )
                st.rerun()

@st.dialog("✏️ Editar Exame Ocupacional")
def dialog_editar_exame(id_alvo):
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, funcionario, tipo_exame, ultimo_exame, periodicidade, proximo_exame, status, matricula, cargo, setor FROM exames WHERE id = ?",
        (id_alvo,),
    )
    reg_ex = cursor.fetchone()
    conn.close()
    if reg_ex:
        (
            ex_emp,
            ex_func,
            ex_tipo,
            ex_ultimo,
            ex_period,
            ex_proximo,
            ex_status,
            ex_mat,
            ex_cargo,
            ex_setor,
        ) = reg_ex
        with st.form(f"form_edicao_exame_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {ex_emp}")
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_funcs_emp = pd.read_sql(
                "SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC",
                conn,
                params=(ex_emp,),
            )
            conn.close()
            lista_funcs = (
                df_funcs_emp["funcionario"].tolist()
                if not df_funcs_emp.empty
                else [ex_func]
            )
            if ex_func not in lista_funcs:
                lista_funcs.insert(0, ex_func)
            try:
                idx_f = lista_funcs.index(ex_func)
            except:
                idx_f = 0
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
            opcoes_tipos_ex = [
                "Admissional",
                "Periódico",
                "Retorno ao Trabalho",
                "Mudança de Riscos",
                "Demissional",
            ]
            try:
                idx_tipo_ex = opcoes_tipos_ex.index(ex_tipo)
            except:
                idx_tipo_ex = 0
            novo_tipo_ex = st.selectbox(
                "Tipo de Exame", opcoes_tipos_ex, index=idx_tipo_ex
            )
            novo_ultimo_ex = st.text_input(
                "Data Último Exame", value=str(ex_ultimo) if ex_ultimo else ""
            )
            opcoes_periodicidade = [
                "1 mês",
                "3 meses",
                "6 meses",
                "12 meses",
                "18 meses",
                "24 meses",
            ]
            try:
                idx_p = opcoes_periodicidade.index(ex_period)
            except:
                idx_p = 3
            nova_periodicidade = st.selectbox(
                "Periodicidade", opcoes_periodicidade, index=idx_p
            )

            proximo_calc_ed = calcular_proximo_exame(novo_ultimo_ex, nova_periodicidade)
            status_calc_ed = calcular_status_exame(proximo_calc_ed)

            novo_proximo_ex = st.text_input(
                "Data Próximo Exame",
                value=proximo_calc_ed,
            )

            st.info(f"📅 Próximo Exame Calculado: **{proximo_calc_ed}** | Status Automático: **{status_calc_ed}**")

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

                proximo_final_ed = validar_e_formatar_data_input(novo_proximo_ex) if novo_proximo_ex else proximo_calc_ed
                status_final_ed = calcular_status_exame(proximo_final_ed)

                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE exames 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, tipo_exame = ?, ultimo_exame = ?, periodicidade = ?, proximo_exame = ?, status = ?
                    WHERE id = ?
                """,
                    (
                        novo_func_sel,
                        str(novo_mat or ""),
                        str(novo_c or ""),
                        str(novo_s or ""),
                        novo_tipo_ex,
                        validar_e_formatar_data_input(novo_ultimo_ex),
                        nova_periodicidade,
                        proximo_final_ed,
                        status_final_ed,
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                sincronizar_status_exames()
                st.session_state["modal_edit_exame_id"] = None
                st.session_state["sel_id_ex"] = None
                if "editor_selecao_exames" in st.session_state:
                    del st.session_state["editor_selecao_exames"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    ex_emp,
                    f"Edição de exame ({novo_tipo_ex}) para {novo_func_sel}",
                )
                st.rerun()

@st.dialog("✏️ Editar Registro de EPI")
def dialog_editar_epi(id_alvo):
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, funcionario, epi, ca, data_entrega, quantidade, status,"
        " matricula, cargo, setor FROM epis WHERE id = ?",
        (id_alvo,),
    )
    reg_ep = cursor.fetchone()
    conn.close()
    if reg_ep:
        ep_emp, ep_func, ep_epi, ep_ca, ep_dt, ep_qtd, ep_st, ep_mat, ep_cargo, ep_setor = reg_ep
        with st.form(f"form_edicao_epi_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {ep_emp}")
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_funcs_emp = pd.read_sql(
                "SELECT matricula, funcionario, cargo, setor FROM base_funcionarios"
                " WHERE empresa = ? ORDER BY funcionario ASC",
                conn,
                params=(ep_emp,),
            )
            conn.close()
            lista_funcs = (
                df_funcs_emp["funcionario"].tolist()
                if not df_funcs_emp.empty
                else [ep_func]
            )
            if ep_func not in lista_funcs:
                lista_funcs.insert(0, ep_func)
            try:
                idx_f = lista_funcs.index(ep_func)
            except:
                idx_f = 0
            novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
            novo_epi_nome = st.text_input("EPI", value=str(ep_epi))
            novo_ca = st.text_input("Número do CA", value=str(ep_ca) if ep_ca else "")
            nova_data_ent = st.text_input("Data Entrega", value=str(ep_dt))
            try:
                qtd_val = int(ep_qtd)
            except:
                qtd_val = 1
            nova_qtd = st.number_input("Quantidade", min_value=1, value=qtd_val)
            st_limpo_ep = limpar_status_banco(ep_st)
            opcoes_st_ep = ["Entregue", "Devolvido", "Substituído"]
            try:
                idx_st_ep = opcoes_st_ep.index(st_limpo_ep)
            except:
                idx_st_ep = 0
            novo_status_ep = st.selectbox(
                "Status",
                ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"],
                index=idx_st_ep,
            )

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
                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE epis 
                    SET funcionario = ?, matricula = ?, cargo = ?, setor = ?, epi = ?, ca = ?, data_entrega = ?, quantidade = ?, status = ?
                    WHERE id = ?
                """,
                    (
                        novo_func_sel,
                        str(novo_mat or ""),
                        str(novo_c or ""),
                        str(novo_s or ""),
                        formatar_titulo(novo_epi_nome),
                        str(novo_ca).strip(),
                        validar_e_formatar_data_input(nova_data_ent),
                        int(nova_qtd),
                        limpar_status_banco(novo_status_ep),
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                st.session_state["modal_edit_epi_id"] = None
                st.session_state["sel_id_epi"] = None
                if "editor_selecao_epis" in st.session_state:
                    del st.session_state["editor_selecao_epis"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    ep_emp,
                    f"Edição de EPI ({novo_epi_nome}) para {novo_func_sel}",
                )
                st.rerun()

@st.dialog("✏️ Editar Documento")
def dialog_editar_documento(id_alvo):
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, documento, data_emissao, vigencia, proxima_renovacao,"
        " status FROM documentos WHERE id = ?",
        (id_alvo,),
    )
    reg = cursor.fetchone()
    df_cad_serv_ed_doc = pd.read_sql(
        "SELECT servico FROM cad_servicos ORDER BY servico ASC", conn
    )
    conn.close()
    lista_serv_ed_doc = (
        df_cad_serv_ed_doc["servico"].tolist()
        if not df_cad_serv_ed_doc.empty
        else []
    )
    if reg:
        d_emp, d_doc, d_emissao, d_vig, d_prox, d_st = reg
        with st.form(f"form_edicao_doc_modal_{id_alvo}"):
            st.markdown(f"**Empresa:** {d_emp}")
            if lista_serv_ed_doc:
                if d_doc in lista_serv_ed_doc:
                    idx_doc = lista_serv_ed_doc.index(d_doc)
                    novo_doc = st.selectbox(
                        "Documento", lista_serv_ed_doc, index=idx_doc
                    )
                else:
                    lista_serv_ed_doc_opt = [d_doc] + lista_serv_ed_doc
                    novo_doc = st.selectbox(
                        "Documento", lista_serv_ed_doc_opt, index=0
                    )
            else:
                novo_doc = st.text_input("Documento", value=str(d_doc))
            nova_emissao = st.text_input(
                "Data Emissão",
                value=str(d_emissao)
                if d_emissao
                else datetime.today().strftime("%d/%m/%Y"),
            )
            nova_vigencia = st.text_input(
                "Vigência", value=str(d_vig) if d_vig else "1 ano"
            )
            prox_calc_ed = calcular_proxima_renovacao(nova_emissao, nova_vigencia)
            nova_proxima_renovacao = st.text_input(
                "Data da Próxima Renovação/Atualização",
                value=str(d_prox) if d_prox else prox_calc_ed,
            )

            status_calculado_ed = calcular_status_por_data(
                nova_proxima_renovacao
                if nova_proxima_renovacao
                else prox_calc_ed
            )
            st.info(
                f"Status calculado automaticamente: **{status_calculado_ed}**"
            )

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                proxima_final_ed = (
                    calcular_proxima_renovacao(nova_emissao, nova_vigencia)
                    if not nova_proxima_renovacao
                    else validar_e_formatar_data_input(nova_proxima_renovacao)
                )
                status_final_ed = calcular_status_por_data(proxima_final_ed)

                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE documentos 
                    SET documento = ?, data_emissao = ?, vigencia = ?, proxima_renovacao = ?, status = ?
                    WHERE id = ?
                """,
                    (
                        formatar_titulo(novo_doc),
                        validar_e_formatar_data_input(nova_emissao),
                        str(nova_vigencia).strip(),
                        proxima_final_ed,
                        status_final_ed,
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                sincronizar_status_documentos()
                st.session_state["modal_edit_doc_id"] = None
                st.session_state["sel_id_doc"] = None
                if "editor_selecao_documentos" in st.session_state:
                    del st.session_state["editor_selecao_documentos"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    d_emp,
                    f"Edição de documento ({novo_doc})",
                )
                st.rerun()

@st.dialog("✏️ Editar Serviço Realizado")
def dialog_editar_servico(id_alvo):
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT empresa, servico, data_realizacao, responsavel, observacoes,"
        " valor, status, nfes FROM servicos_realizados WHERE id = ?",
        (id_alvo,),
    )
    reg_alvo = cursor.fetchone()
    conn.close()
    if reg_alvo:
        e_emp, e_serv, e_data, e_resp, e_obs, e_val, e_status, e_nfes = reg_alvo
        with st.form(f"form_edicao_servico_modal_{id_alvo}"):
            empresas_cad = get_empresas()
            try:
                idx_emp = empresas_cad.index(e_emp)
            except:
                idx_emp = 0
            nova_empresa = st.selectbox(
                "Empresa Cliente", empresas_cad, index=idx_emp
            )
            nova_data = st.text_input(
                "Data da Realização (DD/MM/AAAA)", value=str(e_data)
            )
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_cad_serv_ed = pd.read_sql(
                "SELECT servico FROM cad_servicos ORDER BY servico ASC", conn
            )
            conn.close()
            lista_serv_ed = (
                df_cad_serv_ed["servico"].tolist()
                if not df_cad_serv_ed.empty
                else []
            )
            if e_serv in lista_serv_ed:
                idx_serv = lista_serv_ed.index(e_serv)
                novo_servico = st.selectbox(
                    "Serviço Executado", lista_serv_ed, index=idx_serv
                )
            else:
                novo_servico = st.text_input("Serviço Executado", value=str(e_serv))
            try:
                float_val = float(e_val)
            except:
                float_val = 0.0
            novo_valor = st.number_input(
                "Valor do Serviço (R$)",
                min_value=0.0,
                value=float_val,
                step=50.0,
                format="%.2f",
            )
            novo_resp = st.text_input("Responsável Técnico", value=str(e_resp))
            status_limpo_atual = limpar_status_banco(e_status)
            opcoes_status = ["Concluído", "Em Andamento", "Agendado", "Cancelado"]
            try:
                idx_st = opcoes_status.index(status_limpo_atual)
            except:
                idx_st = 0
            novo_status_sel = st.selectbox(
                "Status",
                ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"],
                index=idx_st,
            )
            nova_nfes = st.text_input(
                "NFES / Nº da Nota", value=str(e_nfes) if e_nfes else ""
            )
            novas_obs = st.text_input(
                "Observações", value=str(e_obs) if e_obs else ""
            )

            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                conn.execute(
                    """
                    UPDATE servicos_realizados 
                    SET empresa = ?, servico = ?, data_realizacao = ?, responsavel = ?, observacoes = ?, valor = ?, status = ?, nfes = ?
                    WHERE id = ?
                """,
                    (
                        nova_empresa,
                        formatar_titulo(novo_servico),
                        validar_e_formatar_data_input(nova_data),
                        formatar_titulo(novo_resp),
                        novas_obs,
                        float(novo_valor),
                        limpar_status_banco(novo_status_sel),
                        str(nova_nfes).strip(),
                        id_alvo,
                    ),
                )
                conn.commit()
                conn.close()
                st.session_state["modal_edit_serv_id"] = None
                st.session_state["sel_id_serv"] = None
                if "editor_selecao_servicos" in st.session_state:
                    del st.session_state["editor_selecao_servicos"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    nova_empresa,
                    f"Edição de serviço ({novo_servico})",
                )
                st.rerun()

def formatar_colunas_tabela(df):
    if df is None or df.empty:
        return df
    colunas_texto = [
        "funcionario",
        "cargo",
        "setor",
        "treinamento",
        "epi",
        "servico",
        "observacoes",
        "responsavel",
        "nome_empresa",
        "cidade",
        "bairro",
        "endereco",
        "empresa",
        "cnae",
        "documento",
        "Funcionário",
        "Cargo",
        "Setor",
        "Treinamento",
        "EPI",
        "Serviço Executado",
        "Observações",
        "Responsável",
        "Nome Empresa",
        "Cidade",
        "Bairro",
        "Endereço",
        "Empresa",
        "CNAE",
        "Documento",
    ]
    for col in colunas_texto:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: formatar_titulo(x) if isinstance(x, str) else x
            )
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
        "pessoas_treinadas": "Modalidade",
        "data_realizacao": "Data da Realização",
        "validade": "Validade",
        "proximo_treinamento": "Data Próximo Treinamento",
        "ultimo_exame": "Último Exame",
        "periodicidade": "Periodicidade",
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
        "data_emissao": "Data Emissão",
        "vigencia": "Vigência",
        "proxima_renovacao": "Data da Próxima Renovação/Atualização",
        "data_nascimento": "Data de Nascimento",
    }
    return df.rename(columns=rename_dict)

@st.cache_data(ttl=300)
def get_empresas():
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    empresas_set = set()
    try:
        df1 = pd.read_sql(
            "SELECT DISTINCT nome_empresa FROM empresas WHERE nome_empresa IS NOT"
            " NULL AND nome_empresa != '' ORDER BY nome_empresa ASC",
            conn,
        )
        for e in df1["nome_empresa"].tolist():
            if str(e).strip():
                empresas_set.add(formatar_titulo(str(e).strip()))
    except:
        pass
    conn.close()
    return sorted(list(empresas_set))

@st.cache_data(ttl=300)
def get_cargos_por_empresa(empresa_nome):
    if not empresa_nome or empresa_nome == "Nenhuma":
        return []
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    try:
        df_c = pd.read_sql(
            "SELECT DISTINCT cargo FROM cad_cargos WHERE empresa = ? ORDER BY"
            " cargo ASC",
            conn,
            params=(empresa_nome,),
        )
        conn.close()
        if not df_c.empty:
            return [
                str(c).strip() for c in df_c["cargo"].tolist() if str(c).strip()
            ]
    except:
        pass
    conn.close()
    return []

@st.cache_data(ttl=300)
def get_setores_por_empresa(empresa_nome):
    if not empresa_nome or empresa_nome == "Nenhuma":
        return []
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    try:
        df_s = pd.read_sql(
            "SELECT DISTINCT setor FROM cad_setores WHERE empresa = ? ORDER BY"
            " setor ASC",
            conn,
            params=(empresa_nome,),
        )
        conn.close()
        if not df_s.empty:
            return [
                str(s).strip() for s in df_s["setor"].tolist() if str(s).strip()
            ]
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
        return (
            f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"
        )
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
    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT grau_risco FROM grau_risco_nr04 WHERE cnae = ?", (cnae_fmt,)
    )
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
                    localidade_fmt = formatar_titulo(dados.get("localidade", ""))
                    uf_fmt = dados.get("uf", "").upper()
                    cidade_res = f"{localidade_fmt} - {uf_fmt}" if uf_fmt else localidade_fmt
                    return {
                        "logradouro": formatar_titulo(dados.get("logradouro", "")),
                        "bairro": formatar_titulo(dados.get("bairro", "")),
                        "cidade": cidade_res,
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
                mun = formatar_titulo(dados.get('municipio', ''))
                uf_val = dados.get('uf', '').upper()
                cidade_uf = f"{mun} - {uf_val}" if uf_val else mun
                logradouro = dados.get("logradouro", "")
                numero = dados.get("numero", "")
                complemento = dados.get("complemento", "")
                end_completo = formatar_titulo(logradouro)
                if numero:
                    end_completo += f", {numero}"
                if complemento:
                    end_completo += f" - {complemento}"
                cnae_fiscal = dados.get("cnae_fiscal", "")
                cnae_principal = normalizar_cnae(cnae_fiscal)
                
                porte_empresa = str(dados.get("porte", "")).strip().upper()

                if cnae_principal:
                    lista_cnaes.append(
                        f"{cnae_principal} - {dados.get('cnae_fiscal_descricao', '')} (Principal)"
                    )
                for sec in dados.get("cnaes_secundarios", []):
                    c_sec = normalizar_cnae(str(sec.get("codigo", "")))
                    if c_sec:
                        lista_cnaes.append(
                            f"{c_sec} - {sec.get('descricao', '')} (Secundário)"
                        )
                grau_risco = consultar_grau_risco_por_cnae(cnae_fiscal)
                return {
                    "razao_social": formatar_titulo(dados.get("razao_social", "")),
                    "cep": str(dados.get("cep", "")).zfill(8),
                    "logradouro": end_completo,
                    "bairro": formatar_titulo(dados.get("bairro", "")),
                    "cidade": cidade_uf,
                    "telefone": (
                        dados.get("ddd_telefone_1", "") or dados.get("telefone", "")
                    ),
                    "email": dados.get("email", ""),
                    "grau_risco": grau_risco,
                    "cnae_principal": cnae_principal,
                    "lista_cnaes": lista_cnaes,
                    "porte": porte_empresa,
                }
        except:
            pass

        try:
            url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                dados = response.json()
                mun = formatar_titulo(dados.get('municipio', ''))
                uf_val = dados.get('uf', '').upper()
                cidade_uf = f"{mun} - {uf_val}" if uf_val else mun
                logradouro = dados.get("logradouro", "")
                numero = dados.get("numero", "")
                complemento = dados.get("complemento", "")
                end_completo = formatar_titulo(logradouro)
                if numero:
                    end_completo += f", {numero}"
                if complemento:
                    end_completo += f" - {complemento}"
                cnae_fiscal = dados.get("cnae_fiscal", "")
                cnae_principal = normalizar_cnae(cnae_fiscal)
                
                porte_empresa = str(dados.get("porte", "")).strip().upper()

                if cnae_principal:
                    lista_cnaes.append(
                        f"{cnae_principal} - {dados.get('cnae_fiscal_descricao', '')} (Principal)"
                    )
                for sec in dados.get("cnaes_secundarios", []):
                    c_sec = normalizar_cnae(str(sec.get("codigo", "")))
                    if c_sec:
                        lista_cnaes.append(
                            f"{c_sec} - {sec.get('descricao', '')} (Secundário)"
                        )
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
                    "lista_cnaes": lista_cnaes,
                    "porte": porte_empresa,
                }
        except:
            pass
    return None

def validar_e_formatar_data_input(data_str):
    if (
        not data_str
        or pd.isna(data_str)
        or str(data_str).strip() in ("", "nan", "None")
    ):
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
        return (
            f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except (ValueError, TypeError):
        return "0,00"

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
        elif tipo == "doc":
            return "🟢 Válido"
        else:
            return "🟢 Concluído"
    v = str(val).strip()
    if "🟢" in v or "🔴" in v or "🟠" in v or "🟡" in v:
        return v
    v_low = v.lower()
    if tipo == "func":
        if "afastado" in v_low:
            return f"🟠 {v}"
        if "desligado" in v_low:
            return f"🔴 {v}"
        return f"🟢 {v}"
    elif tipo == "trein" or tipo == "ex" or tipo == "doc":
        if "vencido" in v_low:
            return f"🔴 {v}"
        if "a vencer" in v_low or "vencer" in v_low:
            return f"🟠 {v}"
        return f"🟢 {v}"
    elif tipo == "epi":
        if "devolvido" in v_low:
            return f"🟠 {v}"
        if "substituído" in v_low or "substituido" in v_low:
            return f"🟡 {v}"
        return f"🟢 {v}"
    else:
        if "andamento" in v_low:
            return f"🟠 {v}"
        if "agendado" in v_low:
            return f"🟡 {v}"
        if "cancelado" in v_low:
            return f"🔴 {v}"
        return f"🟢 {v}"

def limpar_status_banco(val):
    if pd.isna(val):
        return "Ativo"
    return (
        str(val)
        .replace("🟢", "")
        .replace("🔴", "")
        .replace("🟠", "")
        .replace("🟡", "")
        .strip()
    )

def filtrar_vencidos_e_proximos(df, coluna_data, coluna_status):
    if df.empty:
        return pd.DataFrame()
    hoje = datetime.today()
    indices_validos = []
    for idx, row in df.iterrows():
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

def renderizar_painel_aniversariantes(DB_NAME, is_admin, emp_usuario):
    st.markdown("### 🎂 Aniversariantes do Mês")

    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    try:
        df = pd.read_sql(
            "SELECT DISTINCT funcionario, empresa, data_nascimento, cargo FROM"
            " base_funcionarios",
            conn,
        )
    except:
        df = pd.DataFrame()
    conn.close()

    if df.empty or "data_nascimento" not in df.columns:
        st.info(
            "Nenhum funcionário cadastrado ou coluna de data de nascimento não"
            " encontrada."
        )
        return

    mes_atual = datetime.now().month
    aniversariantes = []

    for _, row in df.iterrows():
        data_str = str(row.get("data_nascimento", "")).strip()
        if not data_str:
            continue
        try:
            partes = data_str.split("/")
            if len(partes) >= 2:
                mes_nasc = int(partes[1])
                if mes_nasc == mes_atual:
                    aniversariantes.append({
                        "funcionario": row.get("funcionario", "Não informado"),
                        "empresa": row.get("empresa", "Geral"),
                        "cargo": row.get("cargo", ""),
                        "data": data_str,
                    })
        except:
            continue

    if not aniversariantes:
        st.info("🎉 Nenhum aniversariante registrado para este mês.")
        return

    df_aniv = pd.DataFrame(aniversariantes)
    if not df_aniv.empty:
        df_aniv = df_aniv.drop_duplicates(subset=['funcionario', 'data'], keep='first')

    if not is_admin:
        df_aniv = df_aniv[
            df_aniv["empresa"].astype(str).str.strip().str.lower()
            == str(emp_usuario).strip().lower()
        ]

    if df_aniv.empty:
        st.info("Nenhum aniversariante neste mês para a sua empresa.")
        return

    empresas_unicas = df_aniv["empresa"].unique()

    for emp in empresas_unicas:
        with st.container():
            st.markdown(f"#### 🏢 {emp}")
            funcs_emp = df_aniv[df_aniv["empresa"] == emp]

            for _, f in funcs_emp.iterrows():
                cargo_txt = f" — *{f['cargo']}*" if f["cargo"] else ""
                st.markdown(f"* **{f['data'][:5]}** — **{f['funcionario']}**{cargo_txt}")
            st.markdown("")

# --- CONTROLE DE SESSÃO COM TELA DE LOGIN CENTRALIZADA ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False
if "empresa_usuario" not in st.session_state:
    st.session_state["empresa_usuario"] = ""
if "nome_usuario" not in st.session_state:
    st.session_state["nome_usuario"] = ""
if "nivel_permissao" not in st.session_state:
    st.session_state["nivel_permissao"] = "Somente Visualizar"
if "msg_sucesso" not in st.session_state:
    st.session_state["msg_sucesso"] = ""

if not st.session_state["autenticado"]:
    col_esq, col_centro, col_dir = st.columns([1, 1.4, 1])
    with col_centro:
        st.write("")
        st.write("")
        try:
            st.image("logo.png", width=140)
        except:
            pass
        st.markdown(
            "<h1 style='font-size: 22px; margin-bottom: 0px;'>Cassilab Consultoria"
            " e Treinamentos</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color: gray; font-size: 14px; margin-top: 0px;'>Sistema de"
            " Gestão Integrada em SST</p>",
            unsafe_allow_html=True,
        )
        st.write("")
        aba_login, aba_cadastro, aba_recuperar = st.tabs(
            ["🔑 Entrar", "📝 Cadastrar", "🔄 Recuperar"]
        )

        with aba_login:
            with st.form("form_login"):
                usuario_input = st.text_input(
                    "Usuário ou CPF (com ou sem pontuação)",
                    value="",
                    autocomplete="username",
                )
                senha_input = st.text_input(
                    "Senha", value="", type="password", autocomplete="current-password"
                )
                btn_login = st.form_submit_button(
                    "Acessar Sistema", use_container_width=True
                )

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
                    cpf_limpo = re.sub(r"\D", "", usuario_input)
                    cpf_fmt = (
                        formatar_cpf(cpf_limpo) if len(cpf_limpo) == 11 else usuario_input
                    )

                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id, nome, cpf, empresa, email, celular, senha, status, nivel_permissao 
                        FROM usuarios_sistema 
                        WHERE (nome = ? OR cpf = ? OR cpf = ?) AND senha = ?
                    """,
                        (usuario_input, cpf_limpo, cpf_fmt, senha_input),
                    )
                    users_db = cursor.fetchall()
                    conn.close()

                    if users_db:
                        users_ativos = [
                            u
                            for u in users_db
                            if u[7] != "Bloqueado" and u[7] != "Pendente"
                        ]
                        users_pendentes = [u for u in users_db if u[7] == "Pendente"]

                        if users_pendentes and not users_ativos:
                            st.warning(
                                "⏳ Seu cadastro ainda está aguardando aprovação do"
                                " administrador."
                            )
                        elif not users_ativos and not users_pendentes:
                            st.error("⛔ Este acesso foi bloqueado pelo administrador.")
                        elif len(users_ativos) == 1:
                            user_db = users_ativos[0]
                            st.session_state["autenticado"] = True
                            st.session_state["is_admin"] = False
                            st.session_state["empresa_usuario"] = user_db[3]
                            st.session_state["nome_usuario"] = user_db[1]
                            st.session_state["nivel_permissao"] = (
                                user_db[8]
                                if len(user_db) > 8 and user_db[8]
                                else "Somente Visualizar"
                            )
                            registrar_log(user_db[1], user_db[3], "Login no Sistema")
                            st.success(f"Bem-vindo(a), {user_db[1]}!")
                            st.rerun()
                        elif len(users_ativos) > 1:
                            st.session_state["usuarios_multiplos"] = users_ativos
                            st.rerun()
                    else:
                        st.error("Usuário/CPF ou senha inválidos.")

        if (
            "usuarios_multiplos" in st.session_state
            and st.session_state["usuarios_multiplos"]
        ):
            st.warning(
                "⚠️ Encontramos mais de uma empresa vinculada ao seu CPF. Selecione"
                " qual empresa deseja acessar:"
            )
            with st.form("form_selecionar_empresa_multipla"):
                opcoes_empresas_map = {
                    f"{u[3]} (Permissão: {u[8] if len(u) > 8 and u[8] else 'Somente Visualizar'})": u
                    for u in st.session_state["usuarios_multiplos"]
                }
                escolha_emp_mult = st.selectbox(
                    "Empresa Destino", list(opcoes_empresas_map.keys())
                )
                btn_confirmar_emp = st.form_submit_button(
                    "Acessar Empresa Selecionada", use_container_width=True
                )
                if btn_confirmar_emp:
                    user_db = opcoes_empresas_map[escolha_emp_mult]
                    st.session_state["autenticado"] = True
                    st.session_state["is_admin"] = False
                    st.session_state["empresa_usuario"] = user_db[3]
                    st.session_state["nome_usuario"] = user_db[1]
                    st.session_state["nivel_permissao"] = (
                        user_db[8]
                        if len(user_db) > 8 and user_db[8]
                        else "Somente Visualizar"
                    )
                    del st.session_state["usuarios_multiplos"]
                    registrar_log(
                        user_db[1],
                        user_db[3],
                        "Login no Sistema (Múltiplas Empresas)",
                    )
                    st.success(f"Bem-vindo(a) à empresa {user_db[3]}!")
                    st.rerun()

        with aba_cadastro:
            with st.form("form_novo_usuario"):
                st.markdown("### 📝 Solicitar Cadastro de Acesso")
                st.markdown("Preencha os seus dados para solicitar acesso ao sistema vinculado à sua empresa.")
                
                cad_nome = st.text_input("Nome Completo", value="", autocomplete="off")
                cad_cpf = st.text_input(
                    "CPF (com ou sem pontuação)", value="", autocomplete="off"
                )
                cad_email = st.text_input("E-mail", value="", autocomplete="off")
                cad_celular = st.text_input(
                    "Celular / WhatsApp", value="", autocomplete="off"
                )
                cad_empresa_busca = st.text_input(
                    "Nome da Empresa", value="", autocomplete="off"
                )
                cad_senha = st.text_input(
                    "Crie uma Senha", value="", type="password", autocomplete="new-password"
                )
                
                btn_cad_usuario = st.form_submit_button(
                    "Solicitar Cadastro", use_container_width=True
                )
                
                if btn_cad_usuario:
                    if (
                        cad_nome
                        and cad_cpf
                        and cad_email
                        and cad_celular
                        and cad_empresa_busca
                        and cad_senha
                    ):
                        cpf_formatado = formatar_cpf(cad_cpf)
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        
                        cursor.execute(
                            "SELECT nome_empresa FROM empresas WHERE nome_empresa LIKE ? LIMIT 1",
                            (f"%{cad_empresa_busca.strip()}%",),
                        )
                        emp_encontrada = cursor.fetchone()
                        
                        if emp_encontrada:
                            empresa_final = emp_encontrada[0]
                            
                            cursor.execute(
                                "SELECT status FROM usuarios_sistema WHERE cpf = ? AND empresa = ?",
                                (cpf_formatado, empresa_final),
                            )
                            reg_existente = cursor.fetchone()
                            
                            if reg_existente:
                                status_atual = reg_existente[0]
                                if status_atual == "Pendente":
                                    st.warning(
                                        f"⏳ **Aviso:** Já existe um pedido de cadastro pendente para o CPF `{cpf_formatado}` "
                                        f"na empresa **{empresa_final}**. O administrador já foi notificado e irá aprovar em breve."
                                    )
                                elif status_atual == "Bloqueado":
                                    st.error(
                                        "⛔ **Acesso Bloqueado:** Este acesso encontra-se atualmente bloqueado. "
                                        "Por favor, entre em contacto com o suporte da Cassilab."
                                    )
                                else:
                                    st.info(
                                        f"ℹ️ **Conta Ativa:** Já possui um acesso ativo para a empresa **{empresa_final}**! "
                                        "Pode utilizar a aba **'🔑 Entrar'** para iniciar sessão diretamente."
                                    )
                            else:
                                try:
                                    cursor.execute(
                                        """INSERT INTO usuarios_sistema 
                                           (nome, cpf, empresa, email, celular, senha, status, nivel_permissao) 
                                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                        (
                                            formatar_titulo(cad_nome),
                                            cpf_formatado,
                                            empresa_final,
                                            cad_email.strip(),
                                            cad_celular.strip(),
                                            cad_senha,
                                            "Pendente",
                                            "Somente Visualizar",
                                        ),
                                    )
                                    conn.commit()

                                    try:
                                        cursor.execute("SELECT email FROM configuracoes_email LIMIT 1")
                                        cfg_mail = cursor.fetchone()
                                        if cfg_mail and cfg_mail[0]:
                                            email_admin = cfg_mail[0]
                                            assunto_adm = "🔔 Novo Cadastro Pendente de Aprovação - Sistema Cassilab SST"
                                            corpo_adm = f"""Olá Administrador,

Um novo usuário realizou o cadastro de acesso no sistema e está aguardando a sua aprovação:

- Nome: {formatar_titulo(cad_nome)}
- CPF: {cpf_formatado}
- Empresa: {empresa_final}
- E-mail: {cad_email.strip()}
- Celular: {cad_celular.strip()}

Aceda à aba Administração no seu painel para aprovar ou bloquear o acesso.

Atenciosamente,
Sistema Cassilab SST"""
                                            enviar_email_smtp(email_admin, assunto_adm, corpo_adm)
                                    except Exception:
                                        pass

                                    st.success(
                                        f"✅ Cadastro realizado com sucesso para a empresa **{empresa_final}**! "
                                        "O seu pedido foi enviado ao administrador e será liberado brevemente."
                                    )
                                    st.cache_data.clear()
                                except Exception as e:
                                    st.error(f"Erro ao realizar cadastro: {e}")
                        else:
                            st.error("⚠️ Nenhuma empresa encontrada com esse nome. Verifique a grafia e tente novamente.")
                        conn.close()
                    else:
                        st.error("⚠️ Por favor, preencha todos os campos do formulário.")

        with aba_recuperar:
            with st.form("form_recuperar"):
                rec_cpf = st.text_input(
                    "Digite seu CPF cadastrado (com ou sem pontuação)",
                    value="",
                    autocomplete="off",
                )
                btn_rec_enviar = st.form_submit_button(
                    "Enviar Instruções por E-mail", use_container_width=True
                )
                if btn_rec_enviar:
                    if rec_cpf.strip():
                        cpf_formatado = formatar_cpf(rec_cpf)
                        cpf_limpo = re.sub(r"\D", "", rec_cpf)
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT nome, email, celular, empresa, senha FROM"
                            " usuarios_sistema WHERE cpf = ? OR cpf = ?",
                            (cpf_formatado, cpf_limpo),
                        )
                        res_user = cursor.fetchone()
                        conn.close()
                        if res_user:
                            nome_u, email_u, celular_u, empresa_u, senha_u = res_user
                            if email_u and "@" in email_u:
                                assunto = "Recuperação de Acesso - Sistema Cassilab SST"
                                corpo = f"""Prezado(a) {nome_u},

Recebemos uma solicitação de recuperação de senha vinculada ao seu CPF para o acesso ao Sistema de Gestão Integrada Cassilab SST.

Seguem abaixo os seus dados cadastrados para acesso:
- Empresa: {empresa_u}
- CPF / Usuário: {cpf_formatado}
- Senha: {senha_u}

Recomendamos que você guarde essas informações em um local seguro. Caso não tenha solicitado essa recuperação, ignore esta mensagem.

Atenciosamente,
Cassilab Consultoria e Treinamentos em SST"""
                                sucesso, msg_ret = enviar_email_smtp(email_u, assunto, corpo)
                                if sucesso:
                                    st.success(
                                        f"As instruções de recuperação de senha foram enviadas"
                                        f" para o e-mail {email_u}."
                                    )
                                    registrar_log(
                                        nome_u,
                                        empresa_u,
                                        "Solicitou recuperação de senha por e-mail",
                                    )
                                else:
                                    st.error("Erro ao enviar o e-mail: " + str(msg_ret))
                            else:
                                st.error(
                                    "Este usuário não possui um e-mail válido cadastrado no"
                                    " sistema."
                                )
                        else:
                            st.error("CPF não encontrado.")
                    else:
                        st.error("Digite o CPF.")
    st.stop()

# --- SIDEBAR ---
try:
    st.sidebar.image("logo.png", width=120)
except:
    st.sidebar.markdown("### Cassilab SST")

if not st.session_state["is_admin"]:
    st.sidebar.info(
        f"👤 **Perfil:** Colaborador\n"
        f"🏢 **Empresa:** {st.session_state['empresa_usuario']}\n"
        f"🔑 **Acesso:** {st.session_state['nivel_permissao']}"
    )
else:
    st.sidebar.info("👤 **Perfil:** Administrador\n🔑 **Acesso:** Fazer Tudo")

if st.session_state.get("is_admin", False):
    query_params = st.query_params
    empresa_url = query_params.get("emp", "Todas")
    
    empresas_disponiveis = ["Todas"] + get_empresas()
    
    empresa_inicial = empresa_url if empresa_url in empresas_disponiveis else st.session_state.get("empresa_global", "Todas")

    empresa_global_escolhida = st.sidebar.selectbox(
        "🏢 Empresa Ativa (Global)",
        empresas_disponiveis,
        index=empresas_disponiveis.index(empresa_inicial)
        if empresa_inicial in empresas_disponiveis
        else 0,
        key="select_empresa_global_sidebar"
    )

    st.session_state["empresa_global"] = empresa_global_escolhida
    st.query_params["emp"] = empresa_global_escolhida

    if empresa_global_escolhida != st.session_state.get("ultima_empresa_trabalhada", ""):
        atualizar_filtro_empresa(
            empresa_global_escolhida if empresa_global_escolhida != "Todas" else ""
        )
else:
    st.session_state["empresa_global"] = st.session_state.get("empresa_usuario", "")
    empresa_global_escolhida = st.session_state["empresa_global"]

query_params = st.query_params
menu_url = query_params.get("menu", None)

if st.session_state.get("is_admin", False):
    opcoes_menu = [
        "Dashboard / Visão Geral",
        "Cadastro de Empresas",
        "Cadastros Gerais",
        "Gestão de Funcionários",
        "Treinamentos",
        "Exames Ocupacionais",
        "Controle de Absenteísmo",
        "Controle de EPIs",
        "Controle de Documentos",
        "Alterar Senha",
        "Serviços Realizados",
        "Administração",
        "Relatórios Consolidados",
        "Elaboração de OS (Ordem de Serviço)",
        "Lista de Presença",
    ]
else:
    opcoes_menu = [
        "Dashboard / Visão Geral",
        "Gestão de Funcionários",
        "Treinamentos",
        "Exames Ocupacionais",
        "Controle de Absenteísmo",
        "Controle de EPIs",
        "Controle de Documentos",
        "Alterar Senha",
        "Relatórios Consolidados",
    ]

idx_menu_inicial = opcoes_menu.index(menu_url) if menu_url in opcoes_menu else 0

menu = st.sidebar.selectbox(
    "Menu Principal",
    opcoes_menu,
    index=idx_menu_inicial,
    key="select_menu_principal"
)

st.query_params["menu"] = menu

st.sidebar.markdown("---")
if st.sidebar.button("💾 Salvar tudo e Sair"):
    registrar_log(
        st.session_state.get("nome_usuario", "Desconhecido"),
        st.session_state.get("empresa_usuario", "Todas"),
        "Encerrou Sessão / Sair",
    )
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

pode_lancar = is_admin or nivel_permissao in [
    "Lançar",
    "Editar",
    "Fazer Tudo",
]
pode_editar = is_admin or nivel_permissao in ["Editar", "Fazer Tudo"]
pode_excluir = is_admin or nivel_permissao == "Fazer Tudo"

if st.session_state.get("msg_sucesso"):
    msg = st.session_state["msg_sucesso"]
    st.markdown(
        f'<div style="background-color: #d4edda; color: #155724; padding: 15px 25px; border-radius: 10px; border: 2px solid #28a745; text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 20px;">{msg}</div>',
        unsafe_allow_html=True
    )
    st.session_state["msg_sucesso"] = ""

if menu == "Alterar Senha":
    renderizar_aba_alterar_senha(DB_NAME, st.session_state.get("nome_usuario", ""))
    
# ==========================================
# 0. DASHBOARD
# ==========================================
if menu == "Dashboard / Visão Geral":
    col_t1, col_t2 = st.columns([0.8, 0.2])
    with col_t1:
        st.title("📊 Dashboard - Visão Geral Cassilab SST")
    with col_t2:
        st.write("")
        if st.button("🔄 Atualizar Esta Tela"):
            st.rerun()

    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
    try:
        total_empresas = (
            pd.read_sql(
                "SELECT COUNT(DISTINCT nome_empresa) as qtd FROM empresas WHERE"
                " nome_empresa IS NOT NULL AND nome_empresa != ''",
                conn,
            )
            .iloc[0]["qtd"]
            if is_admin
            else (1 if emp_usuario else 0)
        )
        df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios", conn)
        df_ex_all = pd.read_sql("SELECT * FROM exames", conn)
        df_tr_all = pd.read_sql("SELECT * FROM treinamentos", conn)
        df_docs_all = pd.read_sql("SELECT * FROM documentos", conn)
    except:
        (
            total_empresas,
            df_funcs_all,
            df_ex_all,
            df_tr_all,
            df_docs_all,
        ) = (0, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    conn.close()

    if not is_admin and emp_usuario:
        if not df_funcs_all.empty:
            df_funcs_all = df_funcs_all[
                df_funcs_all["empresa"].astype(str).str.strip().str.lower()
                == str(emp_usuario).strip().lower()
            ]
        if not df_ex_all.empty:
            df_ex_all = df_ex_all[
                df_ex_all["empresa"].astype(str).str.strip().str.lower()
                == str(emp_usuario).strip().lower()
            ]
        if not df_tr_all.empty:
            df_tr_all = df_tr_all[
                df_tr_all["empresa"].astype(str).str.strip().str.lower()
                == str(emp_usuario).strip().lower()
            ]
        if not df_docs_all.empty:
            df_docs_all = df_docs_all[
                df_docs_all["empresa"].astype(str).str.strip().str.lower()
                == str(emp_usuario).strip().lower()
            ]

    total_func_ativos = (
        len(
            df_funcs_all[
                df_funcs_all["status"].astype(str).str.contains(
                    "Ativo|ativo", na=False
                )
            ]
        )
        if not df_funcs_all.empty
        else 0
    )
    total_ex_vencidos = (
        len(
            df_ex_all[
                df_ex_all["status"].astype(str).str.contains(
                    "Vencido|vencido", na=False
                )
            ]
        )
        if not df_ex_all.empty
        else 0
    )
    total_tr_vencidos = (
        len(
            df_tr_all[
                df_tr_all["status"].astype(str).str.contains(
                    "vencido|Vencido", na=False
                )
            ]
        )
        if not df_tr_all.empty
        else 0
    )
    total_doc_vencidos = (
        len(
            df_docs_all[
                df_docs_all["status"].astype(str).str.contains(
                    "Vencido|vencido", na=False
                )
            ]
        )
        if not df_docs_all.empty
        else 0
    )

    empresas_inativas_detalhes = []
    hoje = datetime.today().date()

    try:
        conn_emp = sqlite_original.connect(DB_NAME, timeout=10.0)
        df_empresas = pd.read_sql("SELECT nome_empresa, data_registro FROM empresas", conn_emp)
        
        if not df_empresas.empty:
            for _, row_e in df_empresas.iterrows():
                emp_nome = row_e["nome_empresa"]
                dt_reg_str = str(row_e.get("data_registro", "")).strip()
                
                datas_lancamentos = []
                if dt_reg_str and dt_reg_str not in ("nan", "None", ""):
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                        try:
                            datas_lancamentos.append(datetime.strptime(dt_reg_str, fmt).date())
                            break
                        except ValueError:
                            continue

                tabelas_verificar = [
                    ("base_funcionarios", "data_admissao"),
                    ("exames", "ultimo_exame"),
                    ("treinamentos", "data_realizacao"),
                    ("documentos", "data_emissao"),
                    ("servicos_realizados", "data_realizacao")
                ]
                
                for tabela, col_d in tabelas_verificar:
                    try:
                        df_t = pd.read_sql(f"SELECT {col_d} FROM {tabela} WHERE empresa = ?", conn_emp, params=(emp_nome,))
                        for _, r_t in df_t.iterrows():
                            val_dt = str(r_t.get(col_d, "")).strip()[:10]
                            if val_dt and val_dt not in ("nan", "None", ""):
                                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                                    try:
                                        datas_lancamentos.append(datetime.strptime(val_dt, fmt).date())
                                        break
                                    except ValueError:
                                        continue
                    except:
                        pass

                if datas_lancamentos:
                    ultima_data = max(datas_lancamentos)
                    dias_parada = (hoje - ultima_data).days
                else:
                    dias_parada = 999

                if dias_parada > 30:
                    empresas_inativas_detalhes.append({
                        "empresa": emp_nome,
                        "dias": dias_parada
                    })
        conn_emp.close()
    except:
        pass

    inativas_30 = len(empresas_inativas_detalhes)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(
            f"<div style='font-size:14px; color:gray;'>🏢 Empresas Clientes</div>"
            f"<div style='font-size:28px; font-weight:bold;'>{total_empresas}</div>"
            f"<div style='font-size:12px; color:gray; margin-top:5px;'>Inativas 30 dias<br>"
            f"<b style='color:black; font-size:14px;'>{inativas_30:02d}</b></div>",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"<div style='font-size:14px; color:gray;'>👥 Funcionários</div>"
            f"<div style='font-size:28px; font-weight:bold;'>{len(df_funcs_all)}</div>"
            f"<div style='font-size:12px; color:gray; margin-top:5px;'>Ativos<br>"
            f"<b style='color:black; font-size:14px;'>{total_func_ativos}</b></div>",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"<div style='font-size:14px; color:gray;'>🩺 Exames</div>"
            f"<div style='font-size:28px; font-weight:bold;'>{len(df_ex_all)}</div>"
            f"<div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br>"
            f"<b style='color:red; font-size:14px;'>{total_ex_vencidos}</b></div>",
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"<div style='font-size:14px; color:gray;'>📚 Treinamentos</div>"
            f"<div style='font-size:28px; font-weight:bold;'>{len(df_tr_all)}</div>"
            f"<div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br>"
            f"<b style='color:red; font-size:14px;'>{total_tr_vencidos}</b></div>",
            unsafe_allow_html=True,
        )

    with c5:
        st.markdown(
            f"<div style='font-size:14px; color:gray;'>📄 Documentos</div>"
            f"<div style='font-size:28px; font-weight:bold;'>{len(df_docs_all)}</div>"
            f"<div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br>"
            f"<b style='color:red; font-size:14px;'>{total_doc_vencidos}</b></div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")

    renderizar_painel_aniversariantes(DB_NAME, is_admin, emp_usuario)
    st.markdown("---")

    if is_admin:
        st.markdown(
            "### ⚠️ Painel de Alertas (Vencidos e a vencer em até 30 dias) - Acesso Restrito Admin"
        )
        col_v1, col_v2, col_v3 = st.columns(3)
        
        with col_v1:
            st.markdown("#### 🩺 Exames (Vencidos / 30 dias)")
            df_ex_alertas = filtrar_vencidos_e_proximos(
                df_ex_all, "proximo_exame", "status"
            )
            if not df_ex_alertas.empty:
                res_ex = df_ex_alertas[
                    ["empresa", "funcionario", "tipo_exame", "proximo_exame"]
                ].drop_duplicates()
                for _, row in res_ex.iterrows():
                    msg_ex = f"**{row['empresa']}**\n- {row['funcionario']} ({row['tipo_exame']}) - Vencimento: {row['proximo_exame']}"
                    st.warning(msg_ex)
            else:
                st.success("Nenhum exame vencido ou próximo.")
                
        with col_v2:
            st.markdown("#### 📚 Treinamentos (Vencidos / 30 dias)")
            df_tr_alertas = filtrar_vencidos_e_proximos(
                df_tr_all, "proximo_treinamento", "status"
            )
            if not df_tr_alertas.empty:
                res_tr = df_tr_alertas[
                    ["empresa", "funcionario", "treinamento", "proximo_treinamento"]
                ].drop_duplicates()
                for _, row in res_tr.iterrows():
                    msg_tr = f"**{row['empresa']}**\n- {row['funcionario']} ({row['treinamento']}) - Vencimento: {row['proximo_treinamento']}"
                    st.error(msg_tr)
            else:
                st.success("Nenhum treinamento vencido ou próximo.")
                
        with col_v3:
            st.markdown("#### 📄 Documentos (Vencidos / 30 dias)")
            df_docs_alertas = filtrar_vencidos_e_proximos(
                df_docs_all, "proxima_renovacao", "status"
            )
            if not df_docs_alertas.empty:
                res_doc = df_docs_alertas[
                    ["empresa", "documento", "proxima_renovacao"]
                ].drop_duplicates()
                for _, row in res_doc.iterrows():
                    st.error(f"**{row['empresa']}**\n- {row['documento']} - Renovação: {row['proxima_renovacao']}")
            else:
                st.success("Nenhum documento vencido ou próximo.")
        
        st.markdown("---")

        if st.button(
            "📧 Disparar Alertas por E-mail para Clientes com Vencimentos",
            use_container_width=True,
        ):
            conn_m = sqlite_original.connect(DB_NAME, timeout=10.0)
            cursor_m = conn_m.cursor()
            alertas_por_empresa = {}
            
            if not df_ex_alertas.empty:
                for _, row in df_ex_alertas.iterrows():
                    emp = str(row["empresa"])
                    item_id = row["id"]
                    dt_venc = str(row["proximo_exame"])
                    cursor_m.execute(
                        "SELECT id FROM alertas_enviados WHERE empresa = ? AND tipo_item = 'exame' AND item_id = ? AND data_vencimento = ?",
                        (emp, item_id, dt_venc),
                    )
                    if not cursor_m.fetchone():
                        if emp not in alertas_por_empresa:
                            alertas_por_empresa[emp] = {
                                "exames": [],
                                "treinamentos": [],
                                "documentos": [],
                                "tracking": [],
                            }
                        texto_ex = "Exame: " + str(row['funcionario']) + " (" + str(row['tipo_exame']) + ") - Vencimento: " + dt_venc
                        alertas_por_empresa[emp]["exames"].append(texto_ex)
                        alertas_por_empresa[emp]["tracking"].append(("exame", item_id, dt_venc))

            if not df_tr_alertas.empty:
                for _, row in df_tr_alertas.iterrows():
                    emp = str(row["empresa"])
                    item_id = row["id"]
                    dt_venc = str(row["proximo_treinamento"])
                    cursor_m.execute(
                        "SELECT id FROM alertas_enviados WHERE empresa = ? AND tipo_item = 'treinamento' AND item_id = ? AND data_vencimento = ?",
                        (emp, item_id, dt_venc),
                    )
                    if not cursor_m.fetchone():
                        if emp not in alertas_por_empresa:
                            alertas_por_empresa[emp] = {
                                "exames": [],
                                "treinamentos": [],
                                "documentos": [],
                                "tracking": [],
                            }
                        texto_tr = "Treinamento: " + str(row['funcionario']) + " (" + str(row['treinamento']) + ") - Vencimento: " + dt_venc
                        alertas_por_empresa[emp]["treinamentos"].append(texto_tr)
                        alertas_por_empresa[emp]["tracking"].append(("treinamento", item_id, dt_venc))

            if not df_docs_alertas.empty:
                for _, row in df_docs_alertas.iterrows():
                    emp = str(row["empresa"])
                    item_id = row["id"]
                    dt_venc = str(row["proxima_renovacao"])
                    cursor_m.execute(
                        "SELECT id FROM alertas_enviados WHERE empresa = ? AND tipo_item = 'documento' AND item_id = ? AND data_vencimento = ?",
                        (emp, item_id, dt_venc),
                    )
                    if not cursor_m.fetchone():
                        if emp not in alertas_por_empresa:
                            alertas_por_empresa[emp] = {
                                "exames": [],
                                "treinamentos": [],
                                "documentos": [],
                                "tracking": [],
                            }
                        texto_doc = "Documento: " + str(row['documento']) + " - Renovação: " + dt_venc
                        alertas_por_empresa[emp]["documentos"].append(texto_doc)
                        alertas_por_empresa[emp]["tracking"].append(("documento", item_id, dt_venc))

            enviados = 0
            erros = 0
            hoje_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            relatorio_envios = []

            for emp, dados_emp in alertas_por_empresa.items():
                if not dados_emp["exames"] and not dados_emp["treinamentos"] and not dados_emp["documentos"]:
                    continue
                cursor_m.execute("SELECT email FROM empresas WHERE nome_empresa = ?", (emp,))
                res_emp_email = cursor_m.fetchone()
                email_emp = res_emp_email[0] if res_emp_email and res_emp_email[0] else None

                if email_emp and "@" in email_emp:
                    corpo_msg = f"Prezados(as) da empresa {emp},\n\nIdentificamos em nosso sistema de Gestão SST (Cassilab) itens vencidos ou próximos do vencimento (prazo de 30 dias) que exigem atenção:\n\n"
                    
                    itens_empresa_texto = []
                    if dados_emp["exames"]:
                        corpo_msg += "Exames Ocupacionais:\n" + "\n".join(["- " + i for i in dados_emp["exames"]]) + "\n\n"
                        itens_empresa_texto.extend(dados_emp["exames"])
                    if dados_emp["treinamentos"]:
                        corpo_msg += "Treinamentos:\n" + "\n".join(["- " + i for i in dados_emp["treinamentos"]]) + "\n\n"
                        itens_empresa_texto.extend(dados_emp["treinamentos"])
                    if dados_emp["documentos"]:
                        corpo_msg += "Documentos:\n" + "\n".join(["- " + i for i in dados_emp["documentos"]]) + "\n\n"
                        itens_empresa_texto.extend(dados_emp["documentos"])
                    
                    corpo_msg += "Por favor, entre em contato conosco ou regularize as pendências.\n\nAtenciosamente,\nCassilab Consultoria e Treinamentos em SST"
                    
                    sucesso, msg_ret = enviar_email_smtp(email_emp, "⚠️ Alerta de Vencimentos (30 dias) - Gestão SST Cassilab", corpo_msg)
                    if sucesso:
                        enviados += 1
                        for tipo_t, id_t, dt_t in dados_emp["tracking"]:
                            cursor_m.execute(
                                "INSERT INTO alertas_enviados (empresa, tipo_item, item_id, data_vencimento, data_envio) VALUES (?, ?, ?, ?, ?)",
                                (emp, tipo_t, id_t, dt_t, hoje_str),
                            )
                        conn_m.commit()
                        
                        texto_itens = "".join([f" * {item}\n" for item in itens_empresa_texto])
                        relatorio_envios.append(f"**{emp}** ({email_emp}):\n{texto_itens}")
                    else:
                        erros += 1
                else:
                    erros += 1

            conn_m.close()
            
            if enviados > 0:
                st.success("✅ Alertas novos enviados com sucesso para " + str(enviados) + " empresa(s)!")
                st.markdown("### 📋 Resumo dos Avisos Disparados:")
                for r in relatorio_envios:
                    st.markdown(r)
            elif erros > 0 and enviados == 0:
                st.warning("⚠️ Nenhuma nova mensagem foi enviada (verifique se as empresas possuem e-mail cadastrado ou se os itens já haviam sido notificados).")
            else:
                st.info("ℹ️ Todos os vencimentos atuais já haviam sido notificados anteriormente.")
            st.markdown("---")
    else:
        st.markdown("### ⚠️ Alertas de Vencimentos da sua Empresa (30 dias)")
        col_cv1, col_cv2, col_cv3 = st.columns(3)
        with col_cv1:
            st.markdown("#### 🩺 Exames (Vencidos / 30 dias)")
            df_ex_alertas_cli = filtrar_vencidos_e_proximos(
                df_ex_all, "proximo_exame", "status"
            )
            if not df_ex_alertas_cli.empty:
                res_ex_cli = df_ex_alertas_cli[
                    ["funcionario", "tipo_exame", "proximo_exame"]
                ].drop_duplicates()
                for _, row in res_ex_cli.iterrows():
                    st.warning(
                        f"- **{row['funcionario']}** ({row['tipo_exame']}) - Vencimento:"
                        f" {row['proximo_exame']}"
                    )
            else:
                st.success("Nenhum exame vencido ou próximo.")
        with col_cv2:
            st.markdown("#### 📚 Treinamentos (Vencidos / 30 dias)")
            df_tr_alertas_cli = filtrar_vencidos_e_proximos(
                df_tr_all, "proximo_treinamento", "status"
            )
            if not df_tr_alertas_cli.empty:
                res_tr_cli = df_tr_alertas_cli[
                    ["funcionario", "treinamento", "proximo_treinamento"]
                ].drop_duplicates()
                for _, row in res_tr_cli.iterrows():
                    st.error(
                        f"- **{row['funcionario']}** ({row['treinamento']}) -"
                        f" Vencimento: {row['proximo_treinamento']}"
                    )
            else:
                st.success("Nenhum treinamento vencido ou próximo.")
        with col_cv3:
            st.markdown("#### 📄 Documentos (Vencidos / 30 dias)")
            df_docs_alertas_cli = filtrar_vencidos_e_proximos(
                df_docs_all, "proxima_renovacao", "status"
            )
            if not df_docs_alertas_cli.empty:
                res_doc_cli = df_docs_alertas_cli[
                    ["documento", "proxima_renovacao"]
                ].drop_duplicates()
                for _, row in res_doc_cli.iterrows():
                    st.error(
                        f"- {row['documento']} - Renovação: {row['proxima_renovacao']}"
                    )
            else:
                st.success("Nenhum documento vencido ou próximo.")
        st.markdown("---")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
    renderizar_aba_empresas(
        DB_NAME,
        is_admin,
        emp_usuario,
        formatar_titulo,
        formatar_data_br,
        formatar_cnpj,
        consultar_cnpj,
        consultar_cep,
        consultar_grau_risco_por_cnae,
        formatar_colunas_tabela,
        adicionar_numeracao,
        atualizar_filtro_empresa,
        registrar_log,
    )

# ==========================================
# 2. CADASTROS GERAIS (O Bloco Completo)
# ==========================================

elif menu == "Cadastros Gerais":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1:
        st.title("⚙️ Gerenciamento de Cadastros Gerais")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"):
            st.rerun()

    if not is_admin:
        st.warning("🔒 Área restrita ao Administrador.")
    else:
        empresas_cadastradas = get_empresas()
        
        sub_abas_nomes = ["Cargos", "Setores", "Serviços", "Treinamentos", "EPIs"]
        sub_aba_url = st.query_params.get("sub_aba", "Cargos")
        idx_aba_inicial = sub_abas_nomes.index(sub_aba_url) if sub_aba_url in sub_abas_nomes else 0

        aba_selecionada = st.radio(
            "Navegação de Cadastros",
            sub_abas_nomes,
            index=idx_aba_inicial,
            horizontal=True,
            key="radio_sub_abas_gerais"
        )
        st.query_params["sub_aba"] = aba_selecionada
        st.markdown("---")

        if aba_selecionada == "Cargos":
            st.subheader("Gerenciar Cargos por Empresa")
            with st.form("form_cad_cargo_unico"):
                empresa_cargo_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_cargo",
                )
                novo_cargo = st.text_input("Novo Cargo")
                btn_add_salvar_cargo = st.form_submit_button(
                    "Adicionar e Salvar Cargo"
                )
                if btn_add_salvar_cargo:
                    if empresa_cargo_sel != "Nenhuma" and novo_cargo.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cargo_fmt = formatar_titulo(novo_cargo)
                        cursor.execute(
                            "SELECT id FROM cad_cargos WHERE empresa = ? AND cargo = ?",
                            (empresa_cargo_sel, cargo_fmt),
                        )
                        existe = cursor.fetchone()
                        if existe:
                            st.error(
                                "Este cargo já está cadastrado para a empresa"
                                f" {empresa_cargo_sel}."
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)",
                                (empresa_cargo_sel, cargo_fmt),
                            )
                            conn.commit()
                            if "edit_cargos_tbl" in st.session_state:
                                del st.session_state["edit_cargos_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_cargo_sel,
                                f"Adicionou cargo: {cargo_fmt}",
                            )
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do cargo.")
            st.markdown("---")
            filtro_cargo_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_cargo_emp_view",
            )
            
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            try:
                df_cargos_geral = pd.read_sql(
                    "SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC",
                    conn,
                )
            except Exception:
                # Fallback se a tabela antiga não tiver a coluna empresa
                df_temp = pd.read_sql("SELECT id, cargo FROM cad_cargos ORDER BY cargo ASC", conn)
                df_temp["empresa"] = "Todas"
                df_cargos_geral = df_temp[["id", "empresa", "cargo"]]
            conn.close()

            if filtro_cargo_emp != "Todas as Empresas" and not df_cargos_geral.empty:
                if "empresa" in df_cargos_geral.columns:
                    df_cargos_geral = df_cargos_geral[
                        df_cargos_geral["empresa"].astype(str).str.strip().str.lower()
                        == str(filtro_cargo_emp).strip().lower()
                    ]

            if not df_cargos_geral.empty:
                if "sel_id_cargo_geral" not in st.session_state:
                    st.session_state["sel_id_cargo_geral"] = None
                    
                df_cargos_geral["_id_banco"] = df_cargos_geral["id"]
                df_cargos_geral["Selecionar"] = (
                    df_cargos_geral["_id_banco"] == st.session_state["sel_id_cargo_geral"]
                )
                df_cargos_geral = df_cargos_geral[["Selecionar", "_id_banco", "empresa", "cargo"]]
                df_cargos_ex = formatar_colunas_tabela(df_cargos_geral)
                df_cargos_ex = adicionar_numeracao(df_cargos_ex)
                
                edit_cargos_geral = st.data_editor(
                    df_cargos_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key=f"edit_cargos_gerais_tbl_{filtro_cargo_emp}",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                
                curr_cargo = edit_cargos_geral[edit_cargos_geral["Selecionar"] == True]["_id_banco"].tolist()
                new_cargo = [uid for uid in curr_cargo if uid != st.session_state["sel_id_cargo_geral"]]
                if new_cargo:
                    st.session_state["sel_id_cargo_geral"] = new_cargo[-1]
                    st.rerun()
                elif not curr_cargo and st.session_state["sel_id_cargo_geral"] is not None:
                    st.session_state["sel_id_cargo_geral"] = None
                    st.rerun()

                col_cg_1, col_cg_2 = st.columns(2)
                if col_cg_1.button("💾 Salvar Alterações na Tabela de Cargos", use_container_width=True, key="btn_salvar_cargos_geral_tbl"):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_cargos_geral.iterrows():
                        c_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        c_val = row.get("Cargo", row.get("cargo"))
                        if pd.notna(e_val) and pd.notna(c_val) and str(c_val).strip():
                            if pd.notna(c_id) and str(c_id).strip() not in ("", "nan", "None"):
                                cursor.execute(
                                    "UPDATE cad_cargos SET empresa=?, cargo=? WHERE id=?",
                                    (str(e_val).strip(), formatar_titulo(c_val), int(c_id)),
                                )
                    conn.commit()
                    conn.close()
                    
                    if "edit_cargos_gerais_tbl" in st.session_state:
                        del st.session_state["edit_cargos_gerais_tbl"]
                        
                    st.session_state["sel_id_cargo_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    
                    if "registrar_log" in globals():
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            "Atualização na tabela de cargos",
                        )
                    st.rerun()
                if col_cg_2.button(
                    "🗑️ Excluir Cargo Selecionado", use_container_width=True
                ):
                    if len(linhas_sel_cargo) == 1:
                        cargo_id_exc = int(linhas_sel_cargo.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_cargos WHERE id = ?", (cargo_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_cargos_tbl" in st.session_state:
                            del st.session_state["edit_cargos_tbl"]
                        st.session_state["sel_id_cargo_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = (
                            "🗑️ Cargo excluído com sucesso!"
                        )
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu cargo ID {cargo_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um cargo marcando o quadradinho.")

        elif aba_selecionada == "Setores":
            st.subheader("Gerenciar Setores por Empresa")
            with st.form("form_cad_setor_unico"):
                empresa_setor_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_setor",
                )
                novo_setor = st.text_input("Novo Setor")
                btn_add_salvar_setor = st.form_submit_button("Adicionar e Salvar Setor")
                if btn_add_salvar_setor:
                    if empresa_setor_sel != "Nenhuma" and novo_setor.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        setor_fmt = formatar_titulo(novo_setor)
                        cursor.execute(
                            "SELECT id FROM cad_setores WHERE empresa = ? AND setor = ?",
                            (empresa_setor_sel, setor_fmt),
                        )
                        existe = cursor.fetchone()
                        if existe:
                            st.error(f"Este setor já está cadastrado para a empresa {empresa_setor_sel}.")
                        else:
                            cursor.execute(
                                "INSERT INTO cad_setores (empresa, setor) VALUES (?, ?)",
                                (empresa_setor_sel, setor_fmt),
                            )
                            conn.commit()
                            if "edit_setores_tbl" in st.session_state:
                                del st.session_state["edit_setores_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_setor_sel,
                                f"Adicionou setor: {setor_fmt}",
                            )
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do setor.")
            st.markdown("---")
            filtro_setor_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_setor_emp_view",
            )
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_setores_geral = pd.read_sql(
                "SELECT id, empresa, setor FROM cad_setores ORDER BY empresa, setor ASC",
                conn,
            )
            conn.close()
            if filtro_setor_emp != "Todas as Empresas" and not df_setores_geral.empty:
                df_setores_geral = df_setores_geral[
                    df_setores_geral["empresa"].astype(str).str.strip().str.lower()
                    == str(filtro_setor_emp).strip().lower()
                ]
            if not df_setores_geral.empty:
                if "sel_id_setor_geral" not in st.session_state:
                    st.session_state["sel_id_setor_geral"] = None
                df_setores_geral["_id_banco"] = df_setores_geral["id"]
                df_setores_geral["Selecionar"] = (
                    df_setores_geral["_id_banco"] == st.session_state["sel_id_setor_geral"]
                )
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
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                curr_s_geral = edit_setores[edit_setores["Selecionar"] == True]["_id_banco"].tolist()
                new_s_geral = [
                    uid for uid in curr_s_geral if uid != st.session_state["sel_id_setor_geral"]
                ]
                if new_s_geral:
                    st.session_state["sel_id_setor_geral"] = new_s_geral[-1]
                    st.rerun()
                elif not curr_s_geral and st.session_state["sel_id_setor_geral"] is not None:
                    st.session_state["sel_id_setor_geral"] = None
                    st.rerun()
                linhas_sel_setor = edit_setores[edit_setores["Selecionar"] == True]
                col_sg_1, col_sg_2 = st.columns(2)
                if col_sg_1.button("💾 Salvar Alterações na Tabela de Setores", use_container_width=True):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_setores.iterrows():
                        s_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        s_val = row.get("Setor", row.get("setor"))
                        if pd.notna(e_val) and pd.notna(s_val) and str(s_val).strip():
                            if pd.notna(s_id) and str(s_id).strip() not in ("", "nan", "None"):
                                cursor.execute(
                                    "UPDATE cad_setores SET empresa=?, setor=? WHERE id=?",
                                    (str(e_val).strip(), formatar_titulo(s_val), int(s_id)),
                                )
                    conn.commit()
                    conn.close()
                    if "edit_setores_tbl" in st.session_state:
                        del st.session_state["edit_setores_tbl"]
                    st.session_state["sel_id_setor_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        "Atualização na tabela de setores",
                    )
                    st.rerun()
                if col_sg_2.button("🗑️ Excluir Setor Selecionado", use_container_width=True):
                    if len(linhas_sel_setor) == 1:
                        setor_id_exc = int(linhas_sel_setor.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_setores WHERE id = ?", (setor_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_setores_tbl" in st.session_state:
                            del st.session_state["edit_setores_tbl"]
                        st.session_state["sel_id_setor_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ Setor excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu setor ID {setor_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um setor marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum setor cadastrado.")

        elif aba_selecionada == "Serviços":
            st.subheader("Gerenciar Serviços por Empresa")
            with st.form("form_cad_servico_geral_unico"):
                empresa_servico_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_servico_geral",
                )
                novo_servico_geral = st.text_input("Novo Serviço")
                btn_add_servico_geral = st.form_submit_button("Adicionar e Salvar Serviço")
                
                if btn_add_servico_geral:
                    if empresa_servico_sel != "Nenhuma" and novo_servico_geral.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        serv_fmt = formatar_titulo(novo_servico_geral)
                        
                        # Verifica se a tabela possui a coluna empresa, caso contrário ajusta ou trata
                        try:
                            cursor.execute("SELECT id FROM cad_servicos WHERE empresa = ? AND servico = ?", (empresa_servico_sel, serv_fmt))
                            existe = cursor.fetchone()
                            if existe:
                                st.error(f"Este serviço já está cadastrado para a empresa {empresa_servico_sel}.")
                            else:
                                cursor.execute(
                                    "INSERT INTO cad_servicos (empresa, servico) VALUES (?, ?)",
                                    (empresa_servico_sel, serv_fmt),
                                )
                                conn.commit()
                                if "edit_servicos_gerais_tbl" in st.session_state:
                                    del st.session_state["edit_servicos_gerais_tbl"]
                                st.cache_data.clear()
                                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                                registrar_log(
                                    st.session_state.get("nome_usuario", "Administrador"),
                                    empresa_servico_sel,
                                    f"Adicionou serviço: {serv_fmt}",
                                )
                                st.rerun()
                        except Exception as e:
                            # Caso a tabela antiga só tenha a coluna 'servico' sem 'empresa', garante a compatibilidade
                            try:
                                cursor.execute("ALTER TABLE cad_servicos ADD COLUMN empresa TEXT;")
                                conn.commit()
                                cursor.execute(
                                    "INSERT INTO cad_servicos (empresa, servico) VALUES (?, ?)",
                                    (empresa_servico_sel, serv_fmt),
                                )
                                conn.commit()
                                if "edit_servicos_gerais_tbl" in st.session_state:
                                    del st.session_state["edit_servicos_gerais_tbl"]
                                st.cache_data.clear()
                                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Erro ao salvar serviço: {ex}")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do serviço.")
                        
            st.markdown("---")
            filtro_servico_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_servico_emp_view",
            )
            
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            try:
                df_serv_geral = pd.read_sql(
                    "SELECT id, empresa, servico FROM cad_servicos ORDER BY empresa, servico ASC",
                    conn,
                )
            except:
                # Fallback se a tabela antiga não tiver a coluna empresa
                df_temp = pd.read_sql("SELECT id, servico FROM cad_servicos ORDER BY servico ASC", conn)
                df_temp["empresa"] = "Todas"
                df_serv_geral = df_temp[["id", "empresa", "servico"]]
            conn.close()

            if filtro_servico_emp != "Todas as Empresas" and not df_serv_geral.empty:
                if "empresa" in df_serv_geral.columns:
                    df_serv_geral = df_serv_geral[
                        df_serv_geral["empresa"].astype(str).str.strip().str.lower()
                        == str(filtro_servico_emp).strip().lower()
                    ]

            if not df_serv_geral.empty:
                if "sel_id_serv_geral" not in st.session_state:
                    st.session_state["sel_id_serv_geral"] = None
                df_serv_geral["_id_banco"] = df_serv_geral["id"]
                df_serv_geral["Selecionar"] = (
                    df_serv_geral["_id_banco"] == st.session_state["sel_id_serv_geral"]
                )
                df_serv_geral = df_serv_geral[["Selecionar", "_id_banco", "empresa", "servico"]]
                df_serv_ex = formatar_colunas_tabela(df_serv_geral)
                df_serv_ex = adicionar_numeracao(df_serv_ex)
                
                edit_serv_geral = st.data_editor(
                    df_serv_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_servicos_gerais_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                
                curr_sg = edit_serv_geral[edit_serv_geral["Selecionar"] == True]["_id_banco"].tolist()
                new_sg = [uid for uid in curr_sg if uid != st.session_state["sel_id_serv_geral"]]
                if new_sg:
                    st.session_state["sel_id_serv_geral"] = new_sg[-1]
                    st.rerun()
                elif not curr_sg and st.session_state["sel_id_serv_geral"] is not None:
                    st.session_state["sel_id_serv_geral"] = None
                    st.rerun()
                    
                linhas_sel_serv_geral = edit_serv_geral[edit_serv_geral["Selecionar"] == True]
                col_svg_1, col_svg_2 = st.columns(2)
                
                if col_svg_1.button("💾 Salvar Alterações na Tabela de Serviços", use_container_width=True, key="btn_salvar_serv_geral_tbl"):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_serv_geral.iterrows():
                        sg_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        sg_val = row.get("Serviço Executado", row.get("servico"))
                        if pd.notna(sg_val) and str(sg_val).strip():
                            if pd.notna(sg_id) and str(sg_id).strip() not in ("", "nan", "None"):
                                try:
                                    cursor.execute(
                                        "UPDATE cad_servicos SET empresa=?, servico=? WHERE id=?",
                                        (str(e_val).strip(), formatar_titulo(sg_val), int(sg_id)),
                                    )
                                except:
                                    pass
                    conn.commit()
                    conn.close()
                    if "edit_servicos_gerais_tbl" in st.session_state:
                        del st.session_state["edit_servicos_gerais_tbl"]
                    st.session_state["sel_id_serv_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        "Atualização na tabela de serviços gerais",
                    )
                    st.rerun()
                    
                if col_svg_2.button("🗑️ Excluir Serviço Selecionado", use_container_width=True, key="btn_excluir_serv_geral_tbl"):
                    if len(linhas_sel_serv_geral) == 1:
                        serv_id_exc = int(linhas_sel_serv_geral.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_servicos WHERE id = ?", (serv_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_servicos_gerais_tbl" in st.session_state:
                            del st.session_state["edit_servicos_gerais_tbl"]
                        st.session_state["sel_id_serv_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ Serviço excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu serviço geral ID {serv_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um serviço marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum serviço cadastrado.")
                
        elif aba_selecionada == "Treinamentos":
            st.subheader("Gerenciar Treinamentos por Empresa")
            with st.form("form_cad_treinamento_geral_unico"):
                empresa_trein_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_treinamento_geral",
                )
                
                # Puxa os serviços/itens já cadastrados para servirem de base de escolha
                conn_base = sqlite_original.connect(DB_NAME, timeout=10.0)
                try:
                    df_serv_base = pd.read_sql("SELECT DISTINCT servico FROM cad_servicos ORDER BY servico ASC", conn_base)
                except:
                    df_serv_base = pd.DataFrame()
                conn_base.close()
                lista_base_servicos = df_serv_base["servico"].tolist() if not df_serv_base.empty else []

                c_tr_1, c_tr_2, c_tr_3 = st.columns([0.4, 0.4, 0.2])
                
                if lista_base_servicos:
                    novo_treinamento_geral = c_tr_1.selectbox("Selecionar do Catálogo de Serviços", ["-- Digitar Novo --"] + lista_base_servicos)
                    if novo_treinamento_geral == "-- Digitar Novo --":
                        novo_treinamento_geral = c_tr_2.text_input("Nome do Novo Treinamento")
                else:
                    novo_treinamento_geral = c_tr_1.text_input("Nome do Treinamento")
                
                nova_carga_horaria_geral = c_tr_3.text_input("Carga Horária", value="8 horas")
                btn_add_treinamento_geral = st.form_submit_button("Adicionar e Salvar Treinamento")
                
                if btn_add_treinamento_geral:
                    # Se escolheu no selectbox mas digitou no input alternativo, trata
                    trein_para_salvar = novo_treinamento_geral if novo_treinamento_geral != "-- Digitar Novo --" else ""
                    
                    if empresa_trein_sel != "Nenhuma" and str(trein_para_salvar).strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        trein_fmt = formatar_titulo(trein_para_salvar)
                        
                        try:
                            cursor.execute("ALTER TABLE cad_treinamentos ADD COLUMN empresa TEXT;")
                            conn.commit()
                        except:
                            pass
                            
                        try:
                            cursor.execute(
                                "SELECT id FROM cad_treinamentos WHERE empresa = ? AND treinamento = ?",
                                (empresa_trein_sel, trein_fmt),
                            )
                            existe = cursor.fetchone()
                            if existe:
                                st.error(f"Este treinamento já está cadastrado para a empresa {empresa_trein_sel}.")
                            else:
                                cursor.execute(
                                    "INSERT INTO cad_treinamentos (empresa, treinamento, carga_horaria) VALUES (?, ?, ?)",
                                    (empresa_trein_sel, trein_fmt, nova_carga_horaria_geral.strip()),
                                )
                                conn.commit()
                                if "edit_treinamentos_gerais_tbl" in st.session_state:
                                    del st.session_state["edit_treinamentos_gerais_tbl"]
                                st.cache_data.clear()
                                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                                registrar_log(
                                    st.session_state.get("nome_usuario", "Administrador"),
                                    empresa_trein_sel,
                                    f"Adicionou treinamento: {trein_fmt}",
                                )
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar treinamento: {e}")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha ou escolha o nome do treinamento.")
                        
            st.markdown("---")
            filtro_treinamento_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_treinamento_emp_view",
            )
            
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            try:
                df_tr_geral = pd.read_sql(
                    "SELECT id, empresa, treinamento, carga_horaria FROM cad_treinamentos ORDER BY empresa, treinamento ASC",
                    conn,
                )
            except:
                try:
                    df_temp = pd.read_sql("SELECT id, treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
                    df_temp["empresa"] = "Todas"
                    df_tr_geral = df_temp[["id", "empresa", "treinamento", "carga_horaria"]]
                except:
                    df_tr_geral = pd.DataFrame()
            conn.close()

            if filtro_treinamento_emp != "Todas as Empresas" and not df_tr_geral.empty:
                if "empresa" in df_tr_geral.columns:
                    df_tr_geral = df_tr_geral[
                        df_tr_geral["empresa"].astype(str).str.strip().str.lower()
                        == str(filtro_treinamento_emp).strip().lower()
                    ]

            if not df_tr_geral.empty:
                if "sel_id_tr_geral" not in st.session_state:
                    st.session_state["sel_id_tr_geral"] = None
                df_tr_geral["_id_banco"] = df_tr_geral["id"]
                df_tr_geral["Selecionar"] = (
                    df_tr_geral["_id_banco"] == st.session_state["sel_id_tr_geral"]
                )
                df_tr_geral = df_tr_geral[["Selecionar", "_id_banco", "empresa", "treinamento", "carga_horaria"]]
                df_tr_ex = formatar_colunas_tabela(df_tr_geral)
                df_tr_ex = adicionar_numeracao(df_tr_ex)
                
                edit_tr_geral = st.data_editor(
                    df_tr_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key=f"edit_tr_geral_{filtro_treinamento_emp}",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                
                curr_trg = edit_tr_geral[edit_tr_geral["Selecionar"] == True]["_id_banco"].tolist()
                new_trg = [uid for uid in curr_trg if uid != st.session_state["sel_id_tr_geral"]]
                if new_trg:
                    st.session_state["sel_id_tr_geral"] = new_trg[-1]
                    st.rerun()
                elif not curr_trg and st.session_state["sel_id_tr_geral"] is not None:
                    st.session_state["sel_id_tr_geral"] = None
                    st.rerun()

                # Botões de Salvar Alterações e Excluir
                col_tr_1, col_tr_2 = st.columns(2)
                
                if col_tr_1.button("💾 Salvar Alterações em Treinamentos", use_container_width=True, key=f"btn_salvar_tr_geral_tbl_{filtro_treinamento_emp}"):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_tr_geral.iterrows():
                        t_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        tr_val = row.get("Treinamento", row.get("treinamento"))
                        ch_val = row.get("Carga Horária", row.get("carga_horaria"))
                        
                        if pd.notna(e_val) and pd.notna(tr_val) and str(tr_val).strip():
                            if pd.notna(t_id) and str(t_id).strip() not in ("", "nan", "None"):
                                cursor.execute(
                                    "UPDATE cad_treinamentos SET empresa=?, treinamento=?, carga_horaria=? WHERE id=?",
                                    (str(e_val).strip(), formatar_titulo(tr_val), str(ch_val), int(t_id)),
                                )
                    conn.commit()
                    conn.close()
                    
                    st.session_state["sel_id_tr_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Treinamentos atualizados com sucesso!"
                    st.rerun()

                if col_tr_2.button("🗑️ Excluir Treinamento Selecionado", use_container_width=True, key=f"btn_excluir_tr_{filtro_treinamento_emp}"):
                    if st.session_state["sel_id_tr_geral"] is not None:
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM cad_treinamentos WHERE id=?", (int(st.session_state["sel_id_tr_geral"]),))
                        conn.commit()
                        conn.close()
                        
                        st.session_state["sel_id_tr_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ Treinamento excluído com sucesso!"
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um treinamento na caixa de seleção da tabela para excluir.")
            else:
                st.info("ℹ️ Nenhum treinamento cadastrado.")
        
        elif aba_selecionada == "EPIs":
            st.subheader("Gerenciar EPIs por Empresa (com CA e Tipo)")
            with st.form("form_cad_epi_unico"):
                empresa_epi_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_epi_geral",
                )
                tipos_epi_lista = [
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]
                c_epi_1, c_epi_2, c_epi_3 = st.columns(3)
                novo_epi_nome = c_epi_1.text_input("Nome do EPI")
                novo_epi_ca = c_epi_2.text_input("Número do CA")
                tipo_epi_sel = c_epi_3.selectbox("Tipo / Categoria", tipos_epi_lista)
                
                btn_add_salvar_epi = c_epi_1.form_submit_button(
                    "Adicionar e Salvar EPI e CA"
                )
                if btn_add_salvar_epi:
                    if empresa_epi_sel != "Nenhuma" and novo_epi_nome.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        try:
                            conn.execute("ALTER TABLE cad_epis ADD COLUMN tipo TEXT;")
                        except:
                            pass
                            
                        try:
                            epi_fmt = formatar_titulo(novo_epi_nome)
                            conn.execute(
                                "INSERT INTO cad_epis (empresa, epi, ca, tipo) VALUES (?, ?, ?, ?)",
                                (empresa_epi_sel, epi_fmt, novo_epi_ca.strip(), tipo_epi_sel),
                            )
                            conn.commit()
                            if "edit_epis_tbl" in st.session_state:
                                del st.session_state["edit_epis_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_epi_sel,
                                f"Adicionou EPI: {epi_fmt} (Tipo: {tipo_epi_sel})",
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar EPI: {e}")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do EPI.")
                        
            st.markdown("---")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_epi_geral_emp = st.selectbox(
                    "Filtrar por Empresa",
                    ["Todas as Empresas"] + empresas_cadastradas,
                    key="filtro_epi_geral_emp_view",
                )
            with col_f2:
                tipos_epi_filtro_lista = [
                    "Todos os Tipos",
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]
                filtro_tipo_epi_sel = st.selectbox(
                    "Filtrar por Tipo de EPI",
                    tipos_epi_filtro_lista,
                    key="filtro_epi_tipo_view",
                )

            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            try:
                df_epis_geral = pd.read_sql(
                    "SELECT id, empresa, epi, ca, tipo FROM cad_epis ORDER BY empresa, epi ASC",
                    conn,
                )
            except:
                df_epis_geral = pd.read_sql(
                    "SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC",
                    conn,
                )
                if "tipo" not in df_epis_geral.columns:
                    df_epis_geral["tipo"] = "Diversos"
            conn.close()

            if filtro_epi_geral_emp != "Todas as Empresas" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[
                    df_epis_geral["empresa"].astype(str).str.strip().str.lower()
                    == str(filtro_epi_geral_emp).strip().lower()
                ]

            if filtro_tipo_epi_sel != "Todos os Tipos" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[
                    df_epis_geral["tipo"].astype(str).str.strip().str.lower()
                    == str(filtro_tipo_epi_sel).strip().lower()
                ]

            if not df_epis_geral.empty:
                if "sel_id_epi_geral" not in st.session_state:
                    st.session_state["sel_id_epi_geral"] = None
                df_epis_geral["_id_banco"] = df_epis_geral["id"]
                df_epis_geral["Selecionar"] = (
                    df_epis_geral["_id_banco"] == st.session_state["sel_id_epi_geral"]
                )
                
                cols_epi_exib = ["Selecionar", "_id_banco", "empresa"]
                if "tipo" in df_epis_geral.columns:
                    cols_epi_exib.append("tipo")
                cols_epi_exib.extend(["epi", "ca"])
                
                df_epis_geral = df_epis_geral[cols_epi_exib]

                df_epis_ex = formatar_colunas_tabela(df_epis_geral)
                df_epis_ex = adicionar_numeracao(df_epis_ex)

                tipos_epi_lista = [
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]

                edit_epis = st.data_editor(
                    df_epis_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_epis_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar", required=True
                        ),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                        "tipo": st.column_config.SelectboxColumn(
                            "Tipo",
                            options=tipos_epi_lista,
                            required=True,
                        ),
                        "Tipo": st.column_config.SelectboxColumn(
                            "Tipo",
                            options=tipos_epi_lista,
                            required=True,
                        ),
                    },
                )
                curr_ep_geral = edit_epis[edit_epis["Selecionar"] == True][
                    "_id_banco"
                ].tolist()
                new_ep_geral = [
                    uid
                    for uid in curr_ep_geral
                    if uid != st.session_state["sel_id_epi_geral"]
                ]
                if new_ep_geral:
                    st.session_state["sel_id_epi_geral"] = new_ep_geral[-1]
                    st.rerun()
                elif not curr_ep_geral and st.session_state["sel_id_epi_geral"] is not None:
                    st.session_state["sel_id_epi_geral"] = None
                    st.rerun()

                linhas_sel_epi_geral = edit_epis[edit_epis["Selecionar"] == True]
                col_ep_1, col_ep_2 = st.columns(2)
                if col_ep_1.button(
                    "💾 Salvar Alterações na Tabela de EPIs", use_container_width=True
                ):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    erro_integridade = False
                    
                    for _, row in edit_epis.iterrows():
                        epi_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        epi_val = row.get("EPI", row.get("epi"))
                        ca_val = row.get("CA", row.get("ca"))
                        tipo_val = row.get("Tipo", row.get("tipo", "Diversos"))
                        
                        if pd.notna(e_val) and pd.notna(epi_val) and str(epi_val).strip():
                            if pd.notna(epi_id) and str(epi_id).strip() not in (
                                "",
                                "nan",
                                "None",
                            ):
                                try:
                                    cursor.execute("ALTER TABLE cad_epis ADD COLUMN tipo TEXT;")
                                except:
                                    pass
                                
                                try:
                                    cursor.execute(
                                        "UPDATE cad_epis SET empresa=?, epi=?, ca=?, tipo=? WHERE id=?",
                                        (
                                            str(e_val).strip(),
                                            formatar_titulo(epi_val),
                                            str(ca_val).strip(),
                                            str(tipo_val).strip(),
                                            int(epi_id),
                                        ),
                                    )
                                except sqlite_original.IntegrityError:
                                    erro_integridade = True
                                    st.error(f"❌ Conflito: Já existe um EPI chamado '{formatar_titulo(epi_val)}' cadastrado para a empresa '{str(e_val).strip()}'.")

                    if not erro_integridade:
                        conn.commit()
                        conn.close()
                        if "edit_epis_tbl" in st.session_state:
                            del st.session_state["edit_epis_tbl"]
                        st.session_state["sel_id_epi_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            "Atualização na tabela de EPIs cadastrados",
                        )
                        st.rerun()
                    else:
                        conn.rollback()
                        conn.close()
                if col_ep_2.button(
                    "🗑️ Excluir EPI Selecionado", use_container_width=True
                ):
                    if len(linhas_sel_epi_geral) == 1:
                        epi_id_exc = int(linhas_sel_epi_geral.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_epis WHERE id = ?", (epi_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_epis_tbl" in st.session_state:
                            del st.session_state["edit_epis_tbl"]
                        st.session_state["sel_id_epi_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ EPI excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu EPI cadastrado ID {epi_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um EPI marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum EPI cadastrado com os filtros selecionados.")

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================

elif menu == "Gestão de Funcionários":
    renderizar_aba_funcionarios(
        DB_NAME,
        is_admin,
        emp_usuario,
        pode_lancar,
        pode_editar,
        pode_excluir,
        get_empresas,
        get_cargos_por_empresa,
        get_setores_por_empresa,
        formatar_titulo,
        formatar_cpf,
        validar_e_formatar_data_input,
        limpar_status_banco,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_data_br,
        formatar_status_visual,
        formatar_colunas_tabela,
        adicionar_numeracao,
        reset_func_selection,
        dialog_editar_funcionario,
    )

# ==========================================
# 4. TREINAMENTOS (Com Matriz Integrada)
# ==========================================
elif menu == "Treinamentos":
    renderizar_aba_treinamentos(
        DB_NAME,
        is_admin,
        emp_usuario,
        pode_lancar,
        pode_editar,
        pode_excluir,
        get_empresas,
        calcular_proximo_treinamento,
        validar_e_formatar_data_input,
        limpar_status_banco,
        sincronizar_status_treinamentos,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_data_br,
        formatar_status_visual,
        formatar_colunas_tabela,
        adicionar_numeracao,
        reset_tr_selection,
        dialog_editar_treinamento,
        renderizar_matriz_treinamentos,
    )

# ==========================================
# 5. EXAMES OCUPACIONAIS
# ==========================================
elif menu == "Exames Ocupacionais":
    renderizar_aba_exames(
        DB_NAME,
        is_admin,
        emp_usuario,
        pode_lancar,
        pode_editar,
        pode_excluir,
        get_empresas,
        calcular_proximo_exame,
        validar_e_formatar_data_input,
        limpar_status_banco,
        sincronizar_status_exames,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_data_br,
        formatar_status_visual,
        formatar_colunas_tabela,
        adicionar_numeracao,
        reset_ex_selection,
        dialog_editar_exame,
    )

# ==========================================
# 6. CONTROLE DE ABSENTEÍSMO
# ==========================================
elif menu == "Controle de Absenteísmo":
    renderizar_aba_absenteismo(
        DB_NAME, is_admin, emp_usuario, get_empresas, registrar_log
    )

# ==========================================
# 7. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
    renderizar_aba_epis(
        DB_NAME,
        is_admin,
        emp_usuario,
        pode_lancar,
        pode_editar,
        pode_excluir,
        get_empresas,
        validar_e_formatar_data_input,
        limpar_status_banco,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_data_br,
        formatar_status_visual,
        formatar_colunas_tabela,
        adicionar_numeracao,
        reset_epi_selection,
        dialog_editar_epi,
    )

# ==========================================
# 8. CONTROLE DE DOCUMENTOS
# ==========================================
elif menu == "Controle de Documentos":
    renderizar_aba_documentos(
        DB_NAME,
        is_admin,
        emp_usuario,
        pode_lancar,
        pode_editar,
        pode_excluir,
        get_empresas,
        calcular_proxima_renovacao,
        calcular_status_por_data,
        validar_e_formatar_data_input,
        sincronizar_status_documentos,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_data_br,
        formatar_status_visual,
        formatar_titulo,
        formatar_colunas_tabela,
        adicionar_numeracao,
        reset_doc_selection,
        dialog_editar_documento,
    )

# ==========================================
# 9. SERVIÇOS REALIZADOS (Exclusivo Admin)
# ==========================================
elif menu == "Serviços Realizados":
    renderizar_aba_servicos(
        DB_NAME,
        is_admin,
        get_empresas,
        validar_e_formatar_data_input,
        formatar_titulo,
        formatar_valor_brasileiro,
        limpar_status_banco,
        atualizar_filtro_empresa,
        registrar_log,
        formatar_status_visual,
        adicionar_numeracao,
        reset_serv_selection,
        dialog_editar_servico,
    )

# ==========================================
# 10. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    renderizar_aba_admin(
        DB_NAME, is_admin, enviar_email_smtp, adicionar_numeracao, registrar_log
    )

# ==========================================
# 11. RELATÓRIOS CONSOLIDADOS
# ==========================================
elif menu == "Relatórios Consolidados":
    renderizar_aba_relatorios(
        DB_NAME, is_admin, emp_usuario, get_empresas, formatar_colunas_tabela, adicionar_numeracao
    )

# ==========================================
# 12. ELABORAÇÃO DE OS (ORDEM DE SERVIÇO)
# ==========================================
elif menu == "Elaboração de OS (Ordem de Serviço)":
    renderizar_aba_os(DB_NAME, get_empresas, registrar_log)

# ==========================================
# 13. LISTA DE PRESENÇA
# ==========================================
elif menu == "Lista de Presença":
    renderizar_aba_lista_presenca(DB_NAME, is_admin, emp_usuario, get_empresas, registrar_log)

