import streamlit as st
import sqlite3
import os
from datetime import datetime, timedelta
import re
import pandas as pd
import requests
import csv

# Configuração da Página
st.set_page_config(page_title="Cassilab - Gestão em SST", page_icon="🛡️", layout="wide")

# --- BANCO DE DADOS LOCAL ---
DB_NAME = "cassilab_gestao.db"

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

def sincronizar_status_exames():
    """Atualiza automaticamente o status dos exames com base na data de hoje."""
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql("SELECT id, proximo_exame FROM exames", conn)
        if not df.empty:
            cursor = conn.cursor()
            hoje = datetime.today().date()
            for _, row in df.iterrows():
                prox = row["proximo_exame"]
                novo_st = "Válido"
                if prox and not pd.isna(prox):
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                        try:
                            dt = datetime.strptime(str(prox).strip(), fmt).date()
                            diff = (dt - hoje).days
                            if diff < 0:
                                novo_st = "Vencido"
                            elif diff <= 15:
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
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Tabela Grau de Risco NR-04 (Tabela Oficial)
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

    # 2. Tabela Empresas
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
    
    cursor.execute("PRAGMA table_info(empresas);")
    cols_emp_db = [col[1] for col in cursor.fetchall()]
    if "data_registro" not in cols_emp_db:
        try: cursor.execute("ALTER TABLE empresas ADD COLUMN data_registro TEXT;")
        except: pass
    if "cnae" not in cols_emp_db:
        try: cursor.execute("ALTER TABLE empresas ADD COLUMN cnae TEXT;")
        except: pass
            
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    cursor.execute("UPDATE empresas SET data_registro = ? WHERE data_registro IS NULL OR data_registro = '' OR data_registro = 'nan'", (data_hoje,))
    
    # 3. Tabela Funcionários
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
    
    # 4. Tabela Usuários do Sistema
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
            try: cursor.execute(f"ALTER TABLE usuarios_sistema ADD COLUMN {col_nova} {tipo_col};")
            except: pass

    # 5. Tabela Exames
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
    
    # 6. Tabela Treinamentos
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
    
    cursor.execute("PRAGMA table_info(treinamentos);")
    cols_tr_db = [col[1] for col in cursor.fetchall()]
    if "pessoas_treinadas" not in cols_tr_db:
        try: cursor.execute("ALTER TABLE treinamentos ADD COLUMN pessoas_treinadas TEXT;")
        except: pass
    if "validade" not in cols_tr_db:
        try: cursor.execute("ALTER TABLE treinamentos ADD COLUMN validade TEXT;")
        except: pass

    # 7. Tabela EPIs
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

    # 8. Tabela Serviços Realizados
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

    cursor.execute("PRAGMA table_info(servicos_realizados);")
    cols_srv_db = [col[1] for col in cursor.fetchall()]
    if "valor" not in cols_srv_db:
        try: cursor.execute("ALTER TABLE servicos_realizados ADD COLUMN valor REAL DEFAULT 0;")
        except: pass
    if "nfes" not in cols_srv_db:
        try: cursor.execute("ALTER TABLE servicos_realizados ADD COLUMN nfes TEXT;")
        except: pass

    # 9. Tabela Documentos
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

    # Tabelas de Apoio
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
    
    cursor.execute("PRAGMA table_info(cad_treinamentos);")
    cols_cad_tr = [col[1] for col in cursor.fetchall()]
    if "carga_horaria" not in cols_cad_tr:
        try: cursor.execute("ALTER TABLE cad_treinamentos ADD COLUMN carga_horaria TEXT;")
        except: pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cad_servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico TEXT UNIQUE
        )
    """)
    
    conn.commit()
    conn.close()

    # --- MIGRAÇÃO AUTOMÁTICA: ATUALIZA TODAS AS SIGLAS NO BANCO JÁ LANÇADO ---
    try:
        conn_mig = sqlite3.connect(DB_NAME)
        cur_mig = conn_mig.cursor()
        
        # Empresas
        cur_mig.execute("SELECT id, nome_empresa, cidade, bairro, endereco, responsavel FROM empresas")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE empresas SET nome_empresa=?, cidade=?, bairro=?, endereco=?, responsavel=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), formatar_titulo(r[5]), r[0]))
        
        # Funcionários
        cur_mig.execute("SELECT id, funcionario, cargo, setor, empresa FROM base_funcionarios")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE base_funcionarios SET funcionario=?, cargo=?, setor=?, empresa=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), r[0]))
        
        # Exames
        cur_mig.execute("SELECT id, empresa, funcionario, cargo, setor, tipo_exame FROM exames")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE exames SET empresa=?, funcionario=?, cargo=?, setor=?, tipo_exame=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), formatar_titulo(r[5]), r[0]))
        
        # Treinamentos
        cur_mig.execute("SELECT id, empresa, funcionario, cargo, setor, treinamento FROM treinamentos")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE treinamentos SET empresa=?, funcionario=?, cargo=?, setor=?, treinamento=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), formatar_titulo(r[5]), r[0]))
        
        # EPIs
        cur_mig.execute("SELECT id, empresa, funcionario, cargo, setor, epi FROM epis")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE epis SET empresa=?, funcionario=?, cargo=?, setor=?, epi=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), formatar_titulo(r[5]), r[0]))
        
        # Serviços Realizados
        cur_mig.execute("SELECT id, empresa, servico, responsavel, observacoes FROM servicos_realizados")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE servicos_realizados SET empresa=?, servico=?, responsavel=?, observacoes=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), formatar_titulo(r[3]), formatar_titulo(r[4]), r[0]))
        
        # Documentos
        cur_mig.execute("SELECT id, empresa, documento FROM documentos")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE documentos SET empresa=?, documento=? WHERE id=?", 
                            (formatar_titulo(r[1]), formatar_titulo(r[2]), r[0]))
        
        # Cadastros Gerais
        cur_mig.execute("SELECT id, empresa, cargo FROM cad_cargos")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE cad_cargos SET empresa=?, cargo=? WHERE id=?", (formatar_titulo(r[1]), formatar_titulo(r[2]), r[0]))
            
        cur_mig.execute("SELECT id, empresa, setor FROM cad_setores")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE cad_setores SET empresa=?, setor=? WHERE id=?", (formatar_titulo(r[1]), formatar_titulo(r[2]), r[0]))
            
        cur_mig.execute("SELECT id, empresa, epi FROM cad_epis")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE cad_epis SET empresa=?, epi=? WHERE id=?", (formatar_titulo(r[1]), formatar_titulo(r[2]), r[0]))
            
        cur_mig.execute("SELECT id, treinamento FROM cad_treinamentos")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE cad_treinamentos SET treinamento=? WHERE id=?", (formatar_titulo(r[1]), r[0]))
            
        cur_mig.execute("SELECT id, servico FROM cad_servicos")
        for r in cur_mig.fetchall():
            cur_mig.execute("UPDATE cad_servicos SET servico=? WHERE id=?", (formatar_titulo(r[1]), r[0]))
            
        conn_mig.commit()
        conn_mig.close()
    except:
        pass

init_db()

# Executa a sincronização automática dos status dos exames com base na data de hoje
sincronizar_status_exames()

def enforce_single_selection(df_editado, session_key):
    if df_editado is None or "Selecionar" not in df_editado.columns:
        return df_editado
    atuais = df_editado[df_editado["Selecionar"] == True].index.tolist()
    anteriores = st.session_state.get(session_key, [])
    novos = [idx for idx in atuais if idx not in anteriores]
    if novos:
        ultimo = novos[-1]
        df_editado["Selecionar"] = False
        df_editado.loc[ultimo, "Selecionar"] = True
        st.session_state[session_key] = [ultimo]
        st.rerun()
    elif len(atuais) > 1:
        ultimo = atuais[-1]
        df_editado["Selecionar"] = False
        df_editado.loc[ultimo, "Selecionar"] = True
        st.session_state[session_key] = [ultimo]
        st.rerun()
    else:
        st.session_state[session_key] = atuais
    return df_editado

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

def get_cargos_por_empresa(empresa_nome):
    if not empresa_nome or empresa_nome == "Nenhuma":
        return []
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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
    conn = sqlite3.connect(DB_NAME)
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
                    if diff <= 15:
                        indices_validos.append(idx)
                    break
                except ValueError:
                    continue
    return df.loc[indices_validos] if indices_validos else pd.DataFrame()

# --- CONTROLE DE SESSÃO COM TELA DE LOGIN CENTRALIZADA ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "is_admin" not in st.session_state: st.session_state["is_admin"] = False
if "empresa_usuario" not in st.session_state: st.session_state["empresa_usuario"] = ""

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
        if st.button("🔄 Atualizar Esta Tela"): st.rerun()
    
    conn = sqlite3.connect(DB_NAME)
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
        st.markdown("### ⚠️ Painel de Alertas (Vencidos e a vencer em até 15 dias) - Acesso Restrito Admin")
        
        col_v1, col_v2, col_v3 = st.columns(3)
        
        with col_v1:
            st.markdown("#### 🩺 Exames (Vencidos / 15 dias)")
            df_ex_alertas = filtrar_vencidos_e_proximos(df_ex_all, "proximo_exame", "status")
            if not df_ex_alertas.empty:
                res_ex = df_ex_alertas[["empresa", "funcionario", "tipo_exame", "proximo_exame"]].drop_duplicates()
                for _, row in res_ex.iterrows():
                    st.warning(f"**{row['empresa']}**\n- {row['funcionario']} ({row['tipo_exame']}) - Vencimento: {row['proximo_exame']}")
            else:
                st.success("Nenhum exame vencido ou próximo.")
                
        with col_v2:
            st.markdown("#### 📚 Treinamentos (Vencidos / 15 dias)")
            df_tr_alertas = filtrar_vencidos_e_proximos(df_tr_all, "validade", "status")
            if not df_tr_alertas.empty:
                res_tr = df_tr_alertas[["empresa", "funcionario", "treinamento"]].drop_duplicates()
                for _, row in res_tr.iterrows():
                    st.error(f"**{row['empresa']}**\n- {row['funcionario']} ({row['treinamento']})")
            else:
                st.success("Nenhum treinamento vencido ou próximo.")
                
        with col_v3:
            st.markdown("#### 📄 Documentos (Vencidos / 15 dias)")
            df_docs_alertas = filtrar_vencidos_e_proximos(df_docs_all, "validade", "status")
            if not df_docs_alertas.empty:
                res_doc = df_docs_alertas[["empresa", "documento"]].drop_duplicates()
                for _, row in res_doc.iterrows():
                    st.error(f"**{row['empresa']}**\n- {row['documento']}")
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
        with st.expander("➕ Adicionar Nova Empresa", expanded=True):
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
                        
                        conn = sqlite3.connect(DB_NAME)
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
                            st.success("Empresa cadastrada com sucesso!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esta empresa já está cadastrada (nome duplicado).")
                        finally:
                            conn.close()
                    else:
                        st.error("O campo 'Nome da Empresa' é obrigatório.")

    st.subheader("Empresas Cadastradas")
    conn = sqlite3.connect(DB_NAME)
    df_emp = pd.read_sql("SELECT id, data_registro, nome_empresa, cnpj, endereco, bairro, cep, cidade, email, telefone, responsavel, cnae, grau_risco, qtd_funcionarios FROM empresas ORDER BY nome_empresa ASC", conn)
    conn.close()

    if not is_admin and not df_emp.empty:
        df_emp = df_emp[df_emp["nome_empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_emp.empty:
        if "data_registro" in df_emp.columns: df_emp["data_registro"] = df_emp["data_registro"].apply(formatar_data_br)
        if "cnpj" in df_emp.columns: df_emp["cnpj"] = df_emp["cnpj"].apply(formatar_cnpj)

        df_emp["_id_banco"] = df_emp["id"]
        cols_emp_ord = ["_id_banco"] + [c for c in df_emp.columns if c not in ["_id_banco", "id"]]
        df_emp = df_emp[cols_emp_ord]

        if is_admin:
            df_emp_exibicao = formatar_colunas_tabela(df_emp)
            editado_emp = st.data_editor(
                df_emp_exibicao, 
                num_rows="dynamic", 
                key="editor_emp", 
                use_container_width=True,
                column_config={
                    "_id_banco": None
                }
            )
            chk_salvar_emp = st.checkbox("⚠️ Confirmo salvar as alterações feitas na tabela de empresas", key="chk_salvar_emp")
            if st.button("💾 Salvar Alterações"):
                if chk_salvar_emp:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    for _, row in editado_emp.iterrows():
                        emp_id = row.get("_id_banco", row.get("id"))
                        nome_emp_val = row.get("Nome Empresa", row.get("nome_empresa", ""))
                        if pd.notna(nome_emp_val) and str(nome_emp_val).strip():
                            try: qtd_func_val = int(row.get("Qtd Funcionários", row.get("qtd_funcionarios", 0)))
                            except: qtd_func_val = 0
                            
                            if pd.notna(emp_id) and str(emp_id).strip() not in ("", "nan", "None"):
                                cursor.execute("""
                                    UPDATE empresas SET data_registro=?, nome_empresa=?, cnpj=?, cep=?, cidade=?, bairro=?, endereco=?, telefone=?, email=?, responsavel=?, cnae=?, grau_risco=?, qtd_funcionarios=?
                                    WHERE id=?
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
                                    str(row.get("CNAE", row.get("cnae", ""))).strip(),
                                    str(row.get("Grau Risco", row.get("grau_risco", "1"))).strip(),
                                    qtd_func_val,
                                    int(emp_id)
                                ))
                            else:
                                try:
                                    cursor.execute("""
                                        INSERT INTO empresas (data_registro, nome_empresa, cnpj, cep, cidade, bairro, endereco, telefone, email, responsavel, cnae, grau_risco, qtd_funcionarios) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                                        str(row.get("CNAE", row.get("cnae", ""))).strip(),
                                        str(row.get("Grau Risco", row.get("grau_risco", "1"))).strip(),
                                        qtd_func_val
                                    ))
                                except:
                                    pass
                    conn.commit()
                    conn.close()
                    if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                    st.success("Atualizado com sucesso!")
                    st.rerun()
                else:
                    st.warning("Marque a caixa de confirmação.")

            st.markdown("---")
            st.subheader("🗑️ Excluir Empresa Definitivamente")
            with st.form("form_excluir_empresa"):
                lista_nomes_empresas = sorted(df_emp["nome_empresa"].tolist() if "nome_empresa" in df_emp.columns else df_emp["Nome Empresa"].tolist())
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
                        cursor.execute("DELETE FROM cad_setores WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM cad_epis WHERE empresa = ?", (empresa_para_excluir,))
                        cursor.execute("DELETE FROM documentos WHERE empresa = ?", (empresa_para_excluir,))
                        conn.commit()
                        conn.close()
                        if "editor_emp" in st.session_state: del st.session_state["editor_emp"]
                        st.success(f"Empresa '{empresa_para_excluir}' e todos os seus registros associados foram excluídos com sucesso!")
                        st.rerun()
                    else:
                        st.error("Selecione a empresa e marque a caixa de confirmação para autorizar a exclusão.")
        else:
            df_exib_sem_banco = df_emp.drop(columns=["_id_banco"])
            st.dataframe(formatar_colunas_tabela(df_exib_sem_banco), use_container_width=True)

# ==========================================
# 2. CADASTROS GERAIS
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
                        conn = sqlite3.connect(DB_NAME)
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
                            st.success("Cargo adicionado e salvo com sucesso!")
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do cargo.")

            st.markdown("---")
            filtro_cargo_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_cargo_emp_view")
            
            conn = sqlite3.connect(DB_NAME)
            df_cargos_geral = pd.read_sql("SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC", conn)
            conn.close()
            
            if filtro_cargo_emp != "Todas as Empresas" and not df_cargos_geral.empty:
                df_cargos_geral = df_cargos_geral[df_cargos_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_cargo_emp).strip().lower()]

            if not df_cargos_geral.empty:
                df_cargos_geral["Selecionar"] = False
                df_cargos_geral["_id_banco"] = df_cargos_geral["id"]
                df_cargos_geral = df_cargos_geral[["Selecionar", "_id_banco", "empresa", "cargo"]]

                df_cargos_ex = formatar_colunas_tabela(df_cargos_geral)
                edit_cargos = st.data_editor(
                    df_cargos_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_cargos_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None
                    }
                )
                edit_cargos = enforce_single_selection(edit_cargos, "single_sel_cargos")

                linhas_sel_cargo = edit_cargos[edit_cargos["Selecionar"] == True]

                col_cg_1, col_cg_2 = st.columns(2)
                if col_cg_1.button("💾 Salvar Alterações na Tabela de Cargos", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
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
                    st.success("Cargos atualizados com sucesso!")
                    st.rerun()

                if col_cg_2.button("🗑️ Excluir Cargo Selecionado", use_container_width=True):
                    if len(linhas_sel_cargo) == 1:
                        id_exc_c = int(linhas_sel_cargo.iloc[0]["_id_banco"])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM cad_cargos WHERE id = ?", (id_exc_c,))
                        conn.commit()
                        conn.close()
                        if "edit_cargos_tbl" in st.session_state: del st.session_state["edit_cargos_tbl"]
                        st.success(f"Cargo ID {id_exc_c} excluído com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione **um** cargo marcando o quadradinho para excluir.")

        with aba_g_setores:
            st.subheader("Gerenciar Setores por Empresa")
            with st.form("form_cad_setor_unico"):
                empresa_setor_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_setor")
                novo_setor = st.text_input("Novo Setor")
                btn_add_salvar_setor = st.form_submit_button("Adicionar e Salvar Setor")
                
                if btn_add_salvar_setor:
                    if empresa_setor_sel != "Nenhuma" and novo_setor.strip():
                        conn = sqlite3.connect(DB_NAME)
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
                            st.success("Setor adicionado e salvo com sucesso!")
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do setor.")

            st.markdown("---")
            filtro_setor_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_setor_emp_view")
            
            conn = sqlite3.connect(DB_NAME)
            df_setores_geral = pd.read_sql("SELECT id, empresa, setor FROM cad_setores ORDER BY empresa, setor ASC", conn)
            conn.close()
            
            if filtro_setor_emp != "Todas as Empresas" and not df_setores_geral.empty:
                df_setores_geral = df_setores_geral[df_setores_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_setor_emp).strip().lower()]

            if not df_setores_geral.empty:
                df_setores_geral["Selecionar"] = False
                df_setores_geral["_id_banco"] = df_setores_geral["id"]
                df_setores_geral = df_setores_geral[["Selecionar", "_id_banco", "empresa", "setor"]]

                df_setores_ex = formatar_colunas_tabela(df_setores_geral)
                edit_setores = st.data_editor(
                    df_setores_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_setores_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None
                    }
                )
                edit_setores = enforce_single_selection(edit_setores, "single_sel_setores")

                linhas_sel_setor = edit_setores[edit_setores["Selecionar"] == True]

                col_st_1, col_st_2 = st.columns(2)
                if col_st_1.button("💾 Salvar Alterações na Tabela de Setores", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
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
                    st.success("Setores atualizados com sucesso!")
                    st.rerun()

                if col_st_2.button("🗑️ Excluir Setor Selecionado", use_container_width=True):
                    if len(linhas_sel_setor) == 1:
                        id_exc_s = int(linhas_sel_setor.iloc[0]["_id_banco"])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM cad_setores WHERE id = ?", (id_exc_s,))
                        conn.commit()
                        conn.close()
                        if "edit_setores_tbl" in st.session_state: del st.session_state["edit_setores_tbl"]
                        st.success(f"Setor ID {id_exc_s} excluído com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione **um** setor marcando o quadradinho para excluir.")

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
                            if "edit_serv_tbl" in st.session_state: del st.session_state["edit_serv_tbl"]
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
                df_serv_geral["Selecionar"] = False
                df_serv_geral["_id_banco"] = df_serv_geral["id"]
                df_serv_geral = df_serv_geral[["Selecionar", "_id_banco", "servico"]]

                df_serv_ex = formatar_colunas_tabela(df_serv_geral)
                edit_serv = st.data_editor(
                    df_serv_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_serv_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None
                    }
                )
                edit_serv = enforce_single_selection(edit_serv, "single_sel_serv")

                linhas_sel_serv = edit_serv[edit_serv["Selecionar"] == True]

                col_sv_1, col_sv_2 = st.columns(2)
                if col_sv_1.button("💾 Salvar Alterações na Tabela de Serviços", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
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
                    st.success("Serviços atualizados com sucesso!")
                    st.rerun()

                if col_sv_2.button("🗑️ Excluir Serviço Selecionado", use_container_width=True):
                    if len(linhas_sel_serv) == 1:
                        id_exc_sv = int(linhas_sel_serv.iloc[0]["_id_banco"])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM cad_servicos WHERE id = ?", (id_exc_sv,))
                        conn.commit()
                        conn.close()
                        if "edit_serv_tbl" in st.session_state: del st.session_state["edit_serv_tbl"]
                        st.success(f"Serviço ID {id_exc_sv} excluído com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione **um** serviço marcando o quadradinho para excluir.")

        with aba_g3:
            st.subheader("Gerenciar Tipos de Treinamentos e Carga Horária")
            with st.form("form_cad_treinamento_unico"):
                c_tr_1, c_tr_2 = st.columns(2)
                novo_trein = c_tr_1.text_input("Novo Treinamento")
                nova_carga = c_tr_2.text_input("Carga Horária (ex: 16 horas, 8 horas)")
                btn_add_salvar_trein = st.form_submit_button("Adicionar e Salvar Treinamento")
                
                if btn_add_salvar_trein:
                    if novo_trein.strip():
                        conn = sqlite3.connect(DB_NAME)
                        try:
                            conn.execute("INSERT INTO cad_treinamentos (treinamento, carga_horaria) VALUES (?, ?)", (formatar_titulo(novo_trein), nova_carga.strip()))
                            conn.commit()
                            if "edit_trein_tbl" in st.session_state: del st.session_state["edit_trein_tbl"]
                            st.success("Treinamento adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este treinamento já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do treinamento.")

            st.markdown("---")
            conn = sqlite3.connect(DB_NAME)
            df_trein_geral = pd.read_sql("SELECT id, treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
            conn.close()
            if not df_trein_geral.empty:
                df_trein_geral["Selecionar"] = False
                df_trein_geral["_id_banco"] = df_trein_geral["id"]
                df_trein_geral = df_trein_geral[["Selecionar", "_id_banco", "treinamento", "carga_horaria"]]

                df_trein_ex = formatar_colunas_tabela(df_trein_geral)
                edit_trein = st.data_editor(
                    df_trein_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_trein_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None
                    }
                )
                edit_trein = enforce_single_selection(edit_trein, "single_sel_cad_trein")

                linhas_sel_tr_geral = edit_trein[edit_trein["Selecionar"] == True]

                col_tr_1, col_tr_2 = st.columns(2)
                if col_tr_1.button("💾 Salvar Alterações na Tabela de Treinamentos", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
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
                    st.success("Treinamentos atualizados com sucesso!")
                    st.rerun()

                if col_tr_2.button("🗑️ Excluir Treinamento Selecionado", use_container_width=True):
                    if len(linhas_sel_tr_geral) == 1:
                        id_exc_trg = int(linhas_sel_tr_geral.iloc[0]["_id_banco"])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM cad_treinamentos WHERE id = ?", (id_exc_trg,))
                        conn.commit()
                        conn.close()
                        if "edit_trein_tbl" in st.session_state: del st.session_state["edit_trein_tbl"]
                        st.success(f"Treinamento ID {id_exc_trg} excluído com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione **um** treinamento marcando o quadradinho para excluir.")

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
                            if "edit_epis_tbl" in st.session_state: del st.session_state["edit_epis_tbl"]
                            st.success("EPI adicionado e salvo com sucesso!")
                            st.rerun()
                        except:
                            st.error("Este EPI já está cadastrado para esta empresa.")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do EPI.")

            st.markdown("---")
            filtro_epi_geral_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_epi_geral_emp_view")
            
            conn = sqlite3.connect(DB_NAME)
            df_epis_geral = pd.read_sql("SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC", conn)
            conn.close()
            
            if filtro_epi_geral_emp != "Todas as Empresas" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[df_epis_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_epi_geral_emp).strip().lower()]

            if not df_epis_geral.empty:
                df_epis_geral["Selecionar"] = False
                df_epis_geral["_id_banco"] = df_epis_geral["id"]
                df_epis_geral = df_epis_geral[["Selecionar", "_id_banco", "empresa", "epi", "ca"]]

                df_epis_ex = formatar_colunas_tabela(df_epis_geral)
                edit_epis = st.data_editor(
                    df_epis_ex, 
                    hide_index=True,
                    num_rows="fixed", 
                    key="edit_epis_tbl", 
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None
                    }
                )
                edit_epis = enforce_single_selection(edit_epis, "single_sel_cad_epis")

                linhas_sel_epi_geral = edit_epis[edit_epis["Selecionar"] == True]

                col_ep_1, col_ep_2 = st.columns(2)
                if col_ep_1.button("💾 Salvar Alterações na Tabela de EPIs", use_container_width=True):
                    conn = sqlite3.connect(DB_NAME)
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
                    st.success("EPIs atualizados com sucesso!")
                    st.rerun()

                if col_ep_2.button("🗑️ Excluir EPI Selecionado", use_container_width=True):
                    if len(linhas_sel_epi_geral) == 1:
                        id_exc_epg = int(linhas_sel_epi_geral.iloc[0]["_id_banco"])
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM cad_epis WHERE id = ?", (id_exc_epg,))
                        conn.commit()
                        conn.close()
                        if "edit_epis_tbl" in st.session_state: del st.session_state["edit_epis_tbl"]
                        st.success(f"EPI ID {id_exc_epg} excluído com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione **um** EPI marcando o quadradinho para excluir.")

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

    if is_admin:
        with st.expander("➕ Adicionar Novo Funcionário", expanded=False):
            empresa = st.selectbox("Empresa Cliente", options=empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="func_emp_sel_form")
            
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
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO base_funcionarios (matricula, funcionario, cargo, setor, cpf, data_admissao, status, empresa) 
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (matricula, formatar_titulo(nome), formatar_titulo(cargo), formatar_titulo(setor), formatar_cpf(cpf), validar_e_formatar_data_input(data_admissao_input), limpar_status_banco(status_func), empresa))
                    
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
                    st.success("Funcionário cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("Preencha a empresa, o nome e o cargo do funcionário.")

    st.subheader("Funcionários Cadastrados")
    filtro_empresa_func = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_func_emp") if is_admin else emp_usuario
    
    conn = sqlite3.connect(DB_NAME)
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

        if is_admin:
            df["Selecionar"] = False
            cols_func_ord = ["Selecionar", "_id_banco", "empresa", "matricula", "funcionario", "cargo", "setor", "cpf", "data_admissao", "status"]
            df_func_sel = df[[c for c in cols_func_ord if c in df.columns]]
            
            df_func_exib = formatar_colunas_tabela(df_func_sel)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do funcionário desejado e clique no botão correspondente abaixo para Editar ou Excluir.")
            
            editado_func = st.data_editor(
                df_func_exib, 
                hide_index=True,
                num_rows="fixed", 
                key="editor_selecao_funcionarios", 
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None
                }
            )
            editado_func = enforce_single_selection(editado_func, "single_sel_funcs")

            linhas_sel_func = editado_func[editado_func["Selecionar"] == True]

            col_fb1, col_fb2 = st.columns(2)
            if col_fb1.button("✏️ Editar Funcionário Selecionado", key="btn_editar_func", use_container_width=True):
                if len(linhas_sel_func) == 1:
                    st.session_state["id_funcionario_editando"] = int(linhas_sel_func.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** funcionário marcando o quadradinho para editar.")

            if col_fb2.button("🗑️ Excluir Funcionário Selecionado", key="btn_excluir_func", use_container_width=True):
                if len(linhas_sel_func) == 1:
                    id_exc_f = int(linhas_sel_func.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM base_funcionarios WHERE id = ?", (id_exc_f,))
                    conn.commit()
                    conn.close()
                    if "id_funcionario_editando" in st.session_state:
                        del st.session_state["id_funcionario_editando"]
                    if "editor_selecao_funcionarios" in st.session_state: del st.session_state["editor_selecao_funcionarios"]
                    st.success(f"Funcionário ID {id_exc_f} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** funcionário marcando o quadradinho para excluir.")

            if "id_funcionario_editando" in st.session_state:
                id_alvo_f = st.session_state["id_funcionario_editando"]
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios WHERE id = ?", (id_alvo_f,))
                reg_func = cursor.fetchone()
                conn.close()

                if reg_func:
                    f_emp, f_mat, f_nome, f_cargo, f_setor, f_cpf, f_dt, f_st = reg_func
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Funcionário (ID: {id_alvo_f})")
                    
                    with st.form(f"form_edicao_func_{id_alvo_f}"):
                        c_e1, c_e2 = st.columns(2)
                        c_e1.markdown(f"**Empresa:** {f_emp}")
                        novo_mat = c_e1.text_input("Matrícula", value=str(f_mat) if f_mat else "")
                        novo_nome = c_e2.text_input("Nome do Funcionário", value=str(f_nome))
                        
                        cargos_emp_ed = get_cargos_por_empresa(f_emp)
                        if f_cargo in cargos_emp_ed:
                            idx_c_ed = cargos_emp_ed.index(f_cargo)
                            novo_cargo = c_e1.selectbox("Cargo", cargos_emp_ed, index=idx_c_ed)
                        else:
                            novo_cargo = c_e1.text_input("Cargo", value=str(f_cargo))

                        setores_emp_ed = get_setores_por_empresa(f_emp)
                        if f_setor in setores_emp_ed:
                            idx_s_ed = setores_emp_ed.index(f_setor)
                            novo_setor = c_e2.selectbox("Setor", setores_emp_ed, index=idx_s_ed)
                        else:
                            novo_setor = c_e2.text_input("Setor", value=str(f_setor) if f_setor else "")

                        novo_cpf = c_e1.text_input("CPF", value=str(f_cpf) if f_cpf else "")
                        nova_data_adm = c_e2.text_input("Data Admissão", value=str(f_dt) if f_dt else "")
                        
                        st_limpo_f = limpar_status_banco(f_st)
                        opcoes_st_f = ["Ativo", "Afastado", "Desligado"]
                        try: idx_st_f = opcoes_st_f.index(st_limpo_f)
                        except: idx_st_f = 0
                        novo_status_f = c_e1.selectbox("Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"], index=idx_st_f)

                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.form_submit_button("💾 Salvar Alterações do Funcionário", use_container_width=True):
                            conn = sqlite3.connect(DB_NAME)
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
                                id_alvo_f
                            ))
                            conn.commit()
                            conn.close()
                            del st.session_state["id_funcionario_editando"]
                            if "editor_selecao_funcionarios" in st.session_state: del st.session_state["editor_selecao_funcionarios"]
                            st.success("Funcionário atualizado com sucesso!")
                            st.rerun()

                        if btn_col2.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                            del st.session_state["id_funcionario_editando"]
                            st.rerun()
                else:
                    if "id_funcionario_editando" in st.session_state:
                        del st.session_state["id_funcionario_editando"]
        else:
            df_exib_sem_banco = df.drop(columns=["_id_banco"])
            st.dataframe(formatar_colunas_tabela(df_exib_sem_banco), use_container_width=True)
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
    
    if is_admin:
        with st.expander("➕ Inserção de Treinamento", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_trein")
            conn = sqlite3.connect(DB_NAME)
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
                        conn = sqlite3.connect(DB_NAME)
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
                        st.success("Treinamento salvo com sucesso!")
                        st.rerun()

    st.subheader("Treinamentos Registrados")
    filtro_tr = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_tr_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
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
        
        if is_admin:
            df_tr["Selecionar"] = False
            cols_tr_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "status"]
            df_tr_sel = df_tr[[c for c in cols_tr_ord if c in df_tr.columns]]
            
            df_tr_exib = formatar_colunas_tabela(df_tr_sel)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do treinamento desejado e clique no botão correspondente abaixo para Editar ou Excluir.")
            
            editado_trein = st.data_editor(
                df_tr_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_treinamentos",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None
                }
            )
            editado_trein = enforce_single_selection(editado_trein, "single_sel_treinamentos")

            linhas_sel_tr = editado_trein[editado_trein["Selecionar"] == True]

            col_tb1, col_tb2 = st.columns(2)
            if col_tb1.button("✏️ Editar Treinamento Selecionado", key="btn_editar_trein", use_container_width=True):
                if len(linhas_sel_tr) == 1:
                    st.session_state["id_treinamento_editando"] = int(linhas_sel_tr.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** treinamento marcando o quadradinho para editar.")

            if col_tb2.button("🗑️ Excluir Treinamento Selecionado", key="btn_excluir_trein", use_container_width=True):
                if len(linhas_sel_tr) == 1:
                    id_exc_tr = int(linhas_sel_tr.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM treinamentos WHERE id = ?", (id_exc_tr,))
                    conn.commit()
                    conn.close()
                    if "id_treinamento_editando" in st.session_state:
                        del st.session_state["id_treinamento_editando"]
                    if "editor_selecao_treinamentos" in st.session_state: del st.session_state["editor_selecao_treinamentos"]
                    st.success(f"Treinamento ID {id_exc_tr} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** treinamento marcando o quadradinho para excluir.")

            if "id_treinamento_editando" in st.session_state:
                id_alvo_tr = st.session_state["id_treinamento_editando"]
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT empresa, funcionario, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, status, matricula, cargo, setor FROM treinamentos WHERE id = ?", (id_alvo_tr,))
                reg_tr = cursor.fetchone()
                conn.close()

                if reg_tr:
                    t_emp, t_func, t_trein, t_carga, t_pessoas, t_data, t_val, t_status, t_mat, t_cargo, t_setor = reg_tr
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Treinamento (ID: {id_alvo_tr})")
                    
                    with st.form(f"form_edicao_trein_{id_alvo_tr}"):
                        c_e1, c_e2 = st.columns(2)
                        c_e1.markdown(f"**Empresa:** {t_emp}")
                        
                        conn = sqlite3.connect(DB_NAME)
                        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(t_emp,))
                        conn.close()
                        
                        lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [t_func]
                        if t_func not in lista_funcs:
                            lista_funcs.insert(0, t_func)
                        try: idx_f = lista_funcs.index(t_func)
                        except: idx_f = 0
                        
                        novo_func_sel = c_e1.selectbox("Funcionário", lista_funcs, index=idx_f)

                        conn = sqlite3.connect(DB_NAME)
                        df_cad_tr_ed = pd.read_sql("SELECT treinamento FROM cad_treinamentos ORDER BY treinamento ASC", conn)
                        conn.close()
                        lista_tr_ed = df_cad_tr_ed["treinamento"].tolist() if not df_cad_tr_ed.empty else []
                        
                        if t_trein in lista_tr_ed:
                            idx_tr_sel = lista_tr_ed.index(t_trein)
                            novo_trein_val = c_e2.selectbox("Treinamento", lista_tr_ed, index=idx_tr_sel)
                        else:
                            novo_trein_val = c_e2.text_input("Treinamento", value=str(t_trein))

                        nova_carga_val = c_e1.text_input("Carga Horária", value=str(t_carga) if t_carga else "16 horas")
                        novas_pessoas = c_e2.text_input("Pessoas Treinadas", value=str(t_pessoas) if t_pessoas else "1")
                        nova_data_real = c_e1.text_input("Data da Realização", value=str(t_data))
                        nova_validade = c_e2.text_input("Validade", value=str(t_val) if t_val else "1 ano")
                        
                        st_limpo_tr = limpar_status_banco(t_status)
                        opcoes_st_tr = ["em dia", "vencido"]
                        try: idx_st_tr = opcoes_st_tr.index(st_limpo_tr.lower())
                        except: idx_st_tr = 0
                        novo_status_tr = c_e1.selectbox("Status", ["🟢 em dia", "🔴 vencido"], index=idx_st_tr)

                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.form_submit_button("💾 Salvar Alterações do Treinamento", use_container_width=True):
                            novo_mat = t_mat
                            novo_c = t_cargo
                            novo_s = t_setor
                            if not df_funcs_emp.empty:
                                match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                                if not match_f.empty:
                                    novo_mat = match_f.iloc[0]["matricula"]
                                    novo_c = match_f.iloc[0]["cargo"]
                                    novo_s = match_f.iloc[0]["setor"]

                            conn = sqlite3.connect(DB_NAME)
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
                                id_alvo_tr
                            ))
                            conn.commit()
                            conn.close()
                            del st.session_state["id_treinamento_editando"]
                            if "editor_selecao_treinamentos" in st.session_state: del st.session_state["editor_selecao_treinamentos"]
                            st.success("Treinamento atualizado com sucesso!")
                            st.rerun()

                        if btn_col2.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                            del st.session_state["id_treinamento_editando"]
                            st.rerun()
                else:
                    if "id_treinamento_editando" in st.session_state:
                        del st.session_state["id_treinamento_editando"]
        else:
            df_tr_exib = df_tr[["empresa", "funcionario", "treinamento", "carga_horaria", "pessoas_treinadas", "data_realizacao", "validade", "status"]]
            st.dataframe(formatar_colunas_tabela(df_tr_exib), use_container_width=True)
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
    
    if is_admin:
        with st.expander("➕ Adicionar Novo Exame", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="ex_emp")
            conn = sqlite3.connect(DB_NAME)
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
                    tipo_ex = c1.selectbox("Tipo", ["Admissional", "Periódico", "Retorno ao Trabalho", "Demissional"])
                    proximo = c2.text_input("Data Próximo Exame", value=datetime.today().strftime("%d/%m/%Y"))
                    status_ex = c2.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"])
                    if st.form_submit_button("Salvar Exame"):
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO exames (empresa, matricula, funcionario, cargo, setor, ultimo_exame, tipo_exame, proximo_exame, status) VALUES (?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], validar_e_formatar_data_input(ultimo), tipo_ex, validar_e_formatar_data_input(proximo), limpar_status_banco(status_ex)))
                        conn.commit()
                        conn.close()
                        # Atualiza os status imediatamente após inserir
                        sincronizar_status_exames()
                        if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
                        st.success("Exame salvo!")
                        st.rerun()

    st.subheader("Exames Registrados")
    filtro_ex = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ex_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
    df_ex = pd.read_sql("SELECT * FROM exames ORDER BY funcionario ASC", conn)
    conn.close()

    if is_admin and filtro_ex != "Todas as Empresas" and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(filtro_ex).strip().lower()]
    elif not is_admin and not df_ex.empty:
        df_ex = df_ex[df_ex["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_ex.empty:
        df_ex["ultimo_exame"] = df_ex["ultimo_exame"].apply(formatar_data_br)
        df_ex["proximo_exame"] = df_ex["proximo_exame"].apply(formatar_data_br)
        df_ex["status"] = df_ex["status"].apply(lambda x: formatar_status_visual(x, "ex"))
        
        df_ex["_id_banco"] = df_ex["id"]

        if is_admin:
            df_ex["Selecionar"] = False
            cols_ex_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "proximo_exame", "status"]
            df_ex_sel = df_ex[[c for c in cols_ex_ord if c in df_ex.columns]]
            
            df_ex_exib = formatar_colunas_tabela(df_ex_sel)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do exame desejado e clique no botão correspondente abaixo para Editar ou Excluir.")
            
            editado_ex = st.data_editor(
                df_ex_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_exames",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None
                }
            )
            editado_ex = enforce_single_selection(editado_ex, "single_sel_exames")

            linhas_sel_ex = editado_ex[editado_ex["Selecionar"] == True]

            col_ex_b1, col_ex_b2 = st.columns(2)
            if col_ex_b1.button("✏️ Editar Exame Selecionado", key="btn_editar_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    st.session_state["id_exame_editando"] = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** exame marcando o quadradinho para editar.")

            if col_ex_b2.button("🗑️ Excluir Exame Selecionado", key="btn_excluir_exame", use_container_width=True):
                if len(linhas_sel_ex) == 1:
                    id_exc_ex = int(linhas_sel_ex.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM exames WHERE id = ?", (id_exc_ex,))
                    conn.commit()
                    conn.close()
                    if "id_exame_editando" in st.session_state:
                        del st.session_state["id_exame_editando"]
                    if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
                    st.success(f"Exame ID {id_exc_ex} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** exame marcando o quadradinho para excluir.")

            if "id_exame_editando" in st.session_state:
                id_alvo_ex = st.session_state["id_exame_editando"]
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT empresa, funcionario, tipo_exame, ultimo_exame, proximo_exame, status, matricula, cargo, setor FROM exames WHERE id = ?", (id_alvo_ex,))
                reg_ex = cursor.fetchone()
                conn.close()

                if reg_ex:
                    ex_emp, ex_func, ex_tipo, ex_ultimo, ex_proximo, ex_status, ex_mat, ex_cargo, ex_setor = reg_ex
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Exame (ID: {id_alvo_ex})")
                    
                    with st.form(f"form_edicao_exame_{id_alvo_ex}"):
                        c_e1, c_e2 = st.columns(2)
                        c_e1.markdown(f"**Empresa:** {ex_emp}")
                        
                        conn = sqlite3.connect(DB_NAME)
                        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(ex_emp,))
                        conn.close()
                        
                        lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ex_func]
                        if ex_func not in lista_funcs:
                            lista_funcs.insert(0, ex_func)
                        try: idx_f = lista_funcs.index(ex_func)
                        except: idx_f = 0
                        
                        novo_func_sel = c_e1.selectbox("Funcionário", lista_funcs, index=idx_f)
                        
                        opcoes_tipos_ex = ["Admissional", "Periódico", "Retorno ao Trabalho", "Demissional"]
                        try: idx_tipo_ex = opcoes_tipos_ex.index(ex_tipo)
                        except: idx_tipo_ex = 0
                        
                        novo_tipo_ex = c_e2.selectbox("Tipo de Exame", opcoes_tipos_ex, index=idx_tipo_ex)
                        
                        novo_ultimo_ex = c_e1.text_input("Data Último Exame", value=str(ex_ultimo))
                        novo_proximo_ex = c_e2.text_input("Data Próximo Exame", value=str(ex_proximo))
                        
                        st_limpo_ex = limpar_status_banco(ex_status)
                        opcoes_st_ex = ["Válido", "A Vencer", "Vencido"]
                        try: idx_st_ex = opcoes_st_ex.index(st_limpo_ex)
                        except: idx_st_ex = 0
                        novo_status_ex = c_e1.selectbox("Status", ["🟢 Válido", "🟠 A Vencer", "🔴 Vencido"], index=idx_st_ex)

                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.form_submit_button("💾 Salvar Alterações do Exame", use_container_width=True):
                            novo_mat = ex_mat
                            novo_c = ex_cargo
                            novo_s = ex_setor
                            if not df_funcs_emp.empty:
                                match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                                if not match_f.empty:
                                    novo_mat = match_f.iloc[0]["matricula"]
                                    novo_c = match_f.iloc[0]["cargo"]
                                    novo_s = match_f.iloc[0]["setor"]

                            conn = sqlite3.connect(DB_NAME)
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
                                id_alvo_ex
                            ))
                            conn.commit()
                            conn.close()
                            sincronizar_status_exames()
                            del st.session_state["id_exame_editando"]
                            if "editor_selecao_exames" in st.session_state: del st.session_state["editor_selecao_exames"]
                            st.success("Exame atualizado com sucesso!")
                            st.rerun()

                        if btn_col2.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                            del st.session_state["id_exame_editando"]
                            st.rerun()
                else:
                    if "id_exame_editando" in st.session_state:
                        del st.session_state["id_exame_editando"]
        else:
            df_ex_exib = df_ex[["empresa", "funcionario", "cargo", "setor", "tipo_exame", "ultimo_exame", "proximo_exame", "status"]]
            st.dataframe(formatar_colunas_tabela(df_ex_exib), use_container_width=True)
    else:
        st.info("ℹ️ Nenhum exame encontrado.")

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

    if is_admin:
        with st.expander("➕ Registrar Entrega de EPI", expanded=False):
            empresa_sel = st.selectbox("Selecione a Empresa", empresas, key="emp_epi")
            conn_e = sqlite3.connect(DB_NAME)
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
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                     (empresa_sel, colab['matricula'], nome_sel, colab['cargo'], colab['setor'], epi_sel, ca_epi, validar_e_formatar_data_input(data_entrega), int(qtd), limpar_status_banco(status_epi)))
                        conn.commit()
                        conn.close()
                        if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
                        st.success("EPI registrado!")
                        st.rerun()

    st.subheader("EPIs Registrados")
    filtro_ep = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_ep_emp") if is_admin else emp_usuario
    conn = sqlite3.connect(DB_NAME)
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

        if is_admin:
            df_ep["Selecionar"] = False
            cols_ep_ord = ["Selecionar", "_id_banco", "empresa", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]
            df_ep_sel = df_ep[[c for c in cols_ep_ord if c in df_ep.columns]]
            
            df_ep_exib = formatar_colunas_tabela(df_ep_sel)
            
            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do EPI desejado e clique no botão correspondente abaixo para Editar ou Excluir.")
            
            editado_ep = st.data_editor(
                df_ep_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_epis",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None
                }
            )
            editado_ep = enforce_single_selection(editado_ep, "single_sel_epis")

            linhas_sel_ep = editado_ep[editado_ep["Selecionar"] == True]

            col_ep_b1, col_ep_b2 = st.columns(2)
            if col_ep_b1.button("✏️ Editar EPI Selecionado", key="btn_editar_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    st.session_state["id_epi_editando"] = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** EPI marcando o quadradinho para editar.")

            if col_ep_b2.button("🗑️ Excluir EPI Selecionado", key="btn_excluir_epi", use_container_width=True):
                if len(linhas_sel_ep) == 1:
                    id_exc_ep = int(linhas_sel_ep.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM epis WHERE id = ?", (id_exc_ep,))
                    conn.commit()
                    conn.close()
                    if "id_epi_editando" in st.session_state:
                        del st.session_state["id_epi_editando"]
                    if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
                    st.success(f"EPI ID {id_exc_ep} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **um** EPI marcando o quadradinho para excluir.")

            if "id_epi_editando" in st.session_state:
                id_alvo_ep = st.session_state["id_epi_editando"]
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT empresa, funcionario, epi, ca, data_entrega, quantidade, status, matricula, cargo, setor FROM epis WHERE id = ?", (id_alvo_ep,))
                reg_ep = cursor.fetchone()
                conn.close()

                if reg_ep:
                    ep_emp, ep_func, ep_epi, ep_ca, ep_dt, ep_qtd, ep_st, ep_mat, ep_cargo, ep_setor = reg_ep
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Registro de EPI (ID: {id_alvo_ep})")
                    
                    with st.form(f"form_edicao_epi_{id_alvo_ep}"):
                        c_e1, c_e2 = st.columns(2)
                        c_e1.markdown(f"**Empresa:** {ep_emp}")
                        
                        conn = sqlite3.connect(DB_NAME)
                        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(ep_emp,))
                        conn.close()
                        
                        lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ep_func]
                        if ep_func not in lista_funcs:
                            lista_funcs.insert(0, ep_func)
                        try: idx_f = lista_funcs.index(ep_func)
                        except: idx_f = 0
                        
                        novo_func_sel = c_e1.selectbox("Funcionário", lista_funcs, index=idx_f)
                        
                        novo_epi_nome = c_e2.text_input("EPI", value=str(ep_epi))
                        novo_ca = c_e1.text_input("Número do CA", value=str(ep_ca) if ep_ca else "")
                        nova_data_ent = c_e2.text_input("Data Entrega", value=str(ep_dt))
                        
                        try: qtd_val = int(ep_qtd)
                        except: qtd_val = 1
                        nova_qtd = c_e1.number_input("Quantidade", min_value=1, value=qtd_val)
                        
                        st_limpo_ep = limpar_status_banco(ep_st)
                        opcoes_st_ep = ["Entregue", "Devolvido", "Substituído"]
                        try: idx_st_ep = opcoes_st_ep.index(st_limpo_ep)
                        except: idx_st_ep = 0
                        novo_status_ep = c_e2.selectbox("Status", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"], index=idx_st_ep)

                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.form_submit_button("💾 Salvar Alterações do EPI", use_container_width=True):
                            novo_mat = ep_mat
                            novo_c = ep_cargo
                            novo_s = ep_setor
                            if not df_funcs_emp.empty:
                                match_f = df_funcs_emp[df_funcs_emp["funcionario"] == novo_func_sel]
                                if not match_f.empty:
                                    novo_mat = match_f.iloc[0]["matricula"]
                                    novo_c = match_f.iloc[0]["cargo"]
                                    novo_s = match_f.iloc[0]["setor"]

                            conn = sqlite3.connect(DB_NAME)
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
                                id_alvo_ep
                            ))
                            conn.commit()
                            conn.close()
                            del st.session_state["id_epi_editando"]
                            if "editor_selecao_epis" in st.session_state: del st.session_state["editor_selecao_epis"]
                            st.success("EPI atualizado com sucesso!")
                            st.rerun()

                        if btn_col2.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                            del st.session_state["id_epi_editando"]
                            st.rerun()
                else:
                    if "id_epi_editando" in st.session_state:
                        del st.session_state["id_epi_editando"]
        else:
            df_ep_exib = df_ep[["empresa", "funcionario", "cargo", "setor", "epi", "ca", "data_entrega", "quantidade", "status"]]
            st.dataframe(formatar_colunas_tabela(df_ep_exib), use_container_width=True)
    else:
        st.info("ℹ️ Nenhum EPI encontrado.")

# ==========================================
# 7. SERVIÇOS REALIZADOS
# ==========================================
elif menu == "Serviços Realizados":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🛠️ Controle de Serviços Realizados")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    empresas = get_empresas()
    
    if is_admin:
        with st.expander("➕ Registrar Novo Serviço Realizado", expanded=False):
            conn = sqlite3.connect(DB_NAME)
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
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("""
                            INSERT INTO servicos_realizados 
                            (empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes) 
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (
                            empresa_sel_srv, 
                            formatar_titulo(servico_sel), 
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
                        st.success("Serviço registrado com sucesso!")
                        st.rerun()

    st.subheader("Serviços Registrados")
    
    col_f1, col_f2 = st.columns(2)
    if is_admin:
        filtro_srv = col_f1.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas, key="filtro_srv_emp_trad")
    else:
        filtro_srv = emp_usuario
        col_f1.markdown(f"**Empresa:** {emp_usuario}")

    conn = sqlite3.connect(DB_NAME)
    df_serv = pd.read_sql("SELECT id, empresa, servico, data_realizacao, responsavel, observacoes, status, valor, nfes FROM servicos_realizados", conn)
    conn.close()

    if is_admin and filtro_srv != "Todas as Empresas" and not df_serv.empty:
        df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == str(filtro_srv).strip().lower()]
    elif not is_admin and not df_serv.empty:
        df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

    if not df_serv.empty:
        df_serv["_dt_temp"] = pd.to_datetime(df_serv["data_realizacao"], dayfirst=True, errors="coerce")
        
        meses_disponiveis = ["Todos os Meses"]
        if df_serv["_dt_temp"].notna().any():
            m_unicos = df_serv["_dt_temp"].dropna().dt.strftime("%m/%Y").unique()
            m_unicos = sorted(m_unicos, key=lambda x: datetime.strptime(x, "%m/%Y"), reverse=True)
            meses_disponiveis.extend(m_unicos)

        filtro_mes = col_f2.selectbox("Filtrar por Mês", meses_disponiveis, key="filtro_srv_mes")

        if filtro_mes != "Todos os Meses":
            df_serv["_mes_ano"] = df_serv["_dt_temp"].dt.strftime("%m/%Y")
            df_serv = df_serv[df_serv["_mes_ano"] == filtro_mes]
            df_serv = df_serv.drop(columns=["_mes_ano"])

        df_serv = df_serv.sort_values(by="_dt_temp", ascending=False, na_position="last").drop(columns=["_dt_temp"])

        valor_total_soma = pd.to_numeric(df_serv["valor"], errors="coerce").fillna(0.0).sum()
        st.markdown(f"<p style='font-size: 13px; color: #555; margin-bottom: 8px;'>Total: <b>R$ {formatar_valor_brasileiro(valor_total_soma)}</b></p>", unsafe_allow_html=True)

        df_serv["_id_banco"] = df_serv["id"]

        if is_admin:
            df_serv["Selecionar"] = False
            
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

            st.info("💡 **Dica:** Marque o quadradinho **'Selecionar'** na linha do serviço desejado e clique no botão correspondente abaixo para Editar ou Excluir.")

            editado_tabela = st.data_editor(
                df_tabela_exib,
                hide_index=True,
                num_rows="fixed",
                key="editor_selecao_servicos",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None
                }
            )
            editado_tabela = enforce_single_selection(editado_tabela, "single_sel_servicos")

            linhas_selecionadas = editado_tabela[editado_tabela["Selecionar"] == True]

            col_b1, col_b2 = st.columns(2)
            
            if col_b1.button("✏️ Editar Linha Selecionada", key="btn_ir_editar", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    st.session_state["id_servico_editando"] = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **uma** linha marcando o quadradinho para editar.")

            if col_b2.button("🗑️ Excluir Linha Selecionada", key="btn_ir_excluir", use_container_width=True):
                if len(linhas_selecionadas) == 1:
                    id_exc = int(linhas_selecionadas.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME)
                    conn.execute("DELETE FROM servicos_realizados WHERE id = ?", (id_exc,))
                    conn.commit()
                    conn.close()
                    if "id_servico_editando" in st.session_state:
                        del st.session_state["id_servico_editando"]
                    if "editor_selecao_servicos" in st.session_state: del st.session_state["editor_selecao_servicos"]
                    st.success(f"Serviço ID {id_exc} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Selecione **uma** linha marcando o quadradinho para excluir.")

            if "id_servico_editando" in st.session_state:
                id_alvo = st.session_state["id_servico_editando"]
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes FROM servicos_realizados WHERE id = ?", (id_alvo,))
                reg_alvo = cursor.fetchone()
                conn.close()

                if reg_alvo:
                    e_emp, e_serv, e_data, e_resp, e_obs, e_val, e_status, e_nfes = reg_alvo
                    st.markdown("---")
                    st.markdown(f"### ✏️ Editando Serviço (ID: {id_alvo})")
                    
                    with st.form(f"form_edicao_direta_{id_alvo}"):
                        c1, c2 = st.columns(2)
                        try: idx_emp = empresas.index(e_emp)
                        except: idx_emp = 0
                        
                        nova_empresa = c1.selectbox("Empresa Cliente", empresas, index=idx_emp)
                        nova_data = c1.text_input("Data da Realização (DD/MM/AAAA)", value=str(e_data))
                        
                        conn = sqlite3.connect(DB_NAME)
                        df_cad_serv_ed = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", conn)
                        conn.close()
                        lista_serv_ed = df_cad_serv_ed["servico"].tolist() if not df_cad_serv_ed.empty else []
                        
                        if e_serv in lista_serv_ed:
                            idx_serv = lista_serv_ed.index(e_serv)
                            novo_servico = c1.selectbox("Serviço Executado", lista_serv_ed, index=idx_serv)
                        else:
                            novo_servico = c1.text_input("Serviço Executado", value=str(e_serv))

                        try: float_val = float(e_val)
                        except: float_val = 0.0
                        
                        novo_valor = c1.number_input("Valor do Serviço (R$)", min_value=0.0, value=float_val, step=50.0, format="%.2f")

                        novo_resp = c2.text_input("Responsável Técnico", value=str(e_resp))
                        
                        status_limpo_atual = limpar_status_banco(e_status)
                        opcoes_status = ["Concluído", "Em Andamento", "Agendado", "Cancelado"]
                        try: idx_st = opcoes_status.index(status_limpo_atual)
                        except: idx_st = 0
                        
                        novo_status_sel = c2.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"], index=idx_st)
                        nova_nfes = c2.text_input("NFES / Nº da Nota", value=str(e_nfes) if e_nfes else "")
                        novas_obs = c2.text_input("Observações", value=str(e_obs) if e_obs else "")

                        col_f1, col_f2 = st.columns(2)
                        if col_f1.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                            conn = sqlite3.connect(DB_NAME)
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
                            del st.session_state["id_servico_editando"]
                            if "editor_selecao_servicos" in st.session_state: del st.session_state["editor_selecao_servicos"]
                            st.success("Serviço atualizado com sucesso!")
                            st.rerun()

                        if col_f2.form_submit_button("❌ Cancelar Edição", use_container_width=True):
                            del st.session_state["id_servico_editando"]
                            st.rerun()
                else:
                    if "id_servico_editando" in st.session_state:
                        del st.session_state["id_servico_editando"]
        else:
            df_serv_exib = df_serv[["empresa", "data_realizacao", "servico", "responsavel", "observacoes", "status", "valor", "nfes"]].copy()
            df_serv_exib["data_realizacao"] = df_serv_exib["data_realizacao"].apply(formatar_data_br)
            df_serv_exib["valor"] = pd.to_numeric(df_serv_exib["valor"], errors="coerce").fillna(0.0).apply(formatar_valor_brasileiro)
            df_serv_exib["status"] = df_serv_exib["status"].apply(lambda x: formatar_status_visual(x, "serv"))
            st.dataframe(formatar_colunas_tabela(df_serv_exib), use_container_width=True)
    else:
        st.info("ℹ️ Nenhum serviço registrado para esta seleção.")

# ==========================================
# 8. ADMINISTRAÇÃO
# ==========================================
elif menu == "Administração":
    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("🛠️ Painel Administrativo e Backup")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba"): st.rerun()

    if not is_admin:
        st.warning("🔒 Área exclusiva para o Administrador.")
    else:
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
        df_f = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status FROM base_funcionarios", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_f.empty:
            df_f = df_f[df_f["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_f.empty:
            df_f = df_f[df_f["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_f.empty: 
            st.dataframe(formatar_colunas_tabela(df_f), use_container_width=True)

    if inc_ex:
        st.subheader("Exames")
        df_e = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, tipo_exame, ultimo_exame, proximo_exame, status FROM exames", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_e.empty:
            df_e = df_e[df_e["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_e.empty:
            df_e = df_e[df_e["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_e.empty: 
            st.dataframe(formatar_colunas_tabela(df_e), use_container_width=True)

    if inc_tr:
        st.subheader("Treinamentos")
        df_t = pd.read_sql("SELECT empresa, funcionario, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, status FROM treinamentos", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_t.empty:
            df_t = df_t[df_t["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_t.empty:
            df_t = df_t[df_t["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_t.empty: 
            st.dataframe(formatar_colunas_tabela(df_t), use_container_width=True)

    if inc_ep:
        st.subheader("EPIs")
        df_p = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status FROM epis", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_p.empty:
            df_p = df_p[df_p["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_p.empty:
            df_p = df_p[df_p["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_p.empty: 
            st.dataframe(formatar_colunas_tabela(df_p), use_container_width=True)

    if inc_srv:
        st.subheader("Serviços")
        df_s = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes FROM servicos_realizados", conn)
        if is_admin and empresa_filtro != "Todas as Empresas" and not df_s.empty:
            df_s = df_s[df_s["empresa"].astype(str).str.strip().str.lower() == str(empresa_filtro).strip().lower()]
        elif not is_admin and not df_s.empty:
            df_s = df_s[df_s["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]
        if not df_s.empty:
            df_s["valor"] = df_s["valor"].apply(formatar_valor_brasileiro)
            df_s["data_realizacao"] = df_s["data_realizacao"].apply(formatar_data_br)
            st.dataframe(formatar_colunas_tabela(df_s), use_container_width=True)
    conn.close()