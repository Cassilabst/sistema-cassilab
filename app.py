import calendar
import csv
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import re
import shutil
import smtplib
import sqlite3
import pandas as pd
import requests
from sqlalchemy import create_engine, text
import streamlit as st

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

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Cassilab - Gestão em SST", page_icon="🛡️️", layout="wide"
)

# --- BANCO DE DADOS LOCAL E BACKUP AUTOMÁTICO ---
DB_NAME = "cassilab_gestao.db"

# --- LIGAÇÃO AO SUPABASE POSTGRESQL ---
SUPABASE_URL = "postgresql://postgres:Disc%40976043@db.lythephlnnyyjrcrbbcy.supabase.co:5432/postgres"
engine = create_engine(SUPABASE_URL)


def criar_backup_automatico():
  try:
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
      os.makedirs(backup_dir)
    hoje_data = datetime.now().strftime("%Y-%m-%d")
    backup_path = os.path.join(
        backup_dir, f"cassilab_gestao_backup_{hoje_data}.db"
    )
    if not os.path.exists(backup_path) and os.path.exists(DB_NAME):
      shutil.copy(DB_NAME, backup_path)
  except:
    pass


def formatar_titulo(texto):
  if not texto or pd.isna(texto):
    return ""
  excecoes = {"e", "da", "de", "do", "das", "dos", "em", "para", "com", "S.A."}
  siglas_maiusculas = {
      "ltda",
      "nr",
      "me",
      "mei",
      "epp",
      "epi",
      "cnae",
      "pgr",
      "pcmso",
      "pgrs",
      "pca",
      "ppr",
      "npt",
      "ccb",
      "aet",
      "aep",
      "arp",
      "ltcat",
      "apr",
      "ppp",
      "cipa",
      "epc",
      "aso",
      "sst",
      "sesmt",
      "ca",
      "nfes",
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
              sub.upper()
              if sub.lower() in siglas_maiusculas
              else sub.capitalize()
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
    with engine.begin() as conn:
      dt_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
      conn.execute(
          text("INSERT INTO logs_sistema (data_hora, usuario, empresa, acao) VALUES (:dh, :u, :e, :a)"),
          {"dh": dt_atual, "u": str(usuario), "e": str(empresa), "a": str(acao)}
      )
  except:
    pass


def enviar_email_smtp(destinatario, assunto, corpo):
  try:
    df_cfg = pd.read_sql("SELECT email, senha_app FROM configuracoes_email LIMIT 1", engine)
    if df_cfg.empty or not df_cfg.iloc[0]["email"] or not df_cfg.iloc[0]["senha_app"]:
      return (
          False,
          "Configurações de e-mail não encontradas na aba Administração.",
      )
    remetente = df_cfg.iloc[0]["email"]
    senha_app = df_cfg.iloc[0]["senha_app"]
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


def sincronizar_status_exames():
  try:
    df = pd.read_sql("SELECT id, proximo_exame FROM exames", engine)
    if not df.empty:
      hoje = datetime.today().date()
      with engine.begin() as conn:
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
                elif diff <= 30:
                  novo_st = "A Vencer"
                else:
                  novo_st = "Válido"
                break
              except ValueError:
                continue
          conn.execute(
              text("UPDATE exames SET status = :st WHERE id = :id"),
              {"st": novo_st, "id": row["id"]}
          )
  except:
    pass


def sincronizar_status_treinamentos():
  try:
    df = pd.read_sql("SELECT id, proximo_treinamento FROM treinamentos", engine)
    if not df.empty:
      hoje = datetime.today().date()
      with engine.begin() as conn:
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
          conn.execute(
              text("UPDATE treinamentos SET status = :st WHERE id = :id"),
              {"st": novo_st, "id": row["id"]}
          )
  except:
    pass


def sincronizar_status_documentos():
  try:
    df = pd.read_sql("SELECT id, proxima_renovacao FROM documentos", engine)
    if not df.empty:
      hoje = datetime.today().date()
      with engine.begin() as conn:
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
          conn.execute(
              text("UPDATE documentos SET status = :st WHERE id = :id"),
              {"st": novo_st, "id": row["id"]}
          )
  except:
    pass


def atualizar_cargo_setor_treinamentos_antigos():
  try:
    with engine.begin() as conn:
      conn.execute(text("""
          UPDATE treinamentos 
          SET cargo = COALESCE(NULLIF(cargo, ''), (SELECT b.cargo FROM base_funcionarios b WHERE b.funcionario = treinamentos.funcionario AND b.empresa = treinamentos.empresa LIMIT 1)),
              setor = COALESCE(NULLIF(setor, ''), (SELECT b.setor FROM base_funcionarios b WHERE b.funcionario = treinamentos.funcionario AND b.empresa = treinamentos.empresa LIMIT 1))
          WHERE cargo IS NULL OR cargo = '' OR setor IS NULL OR setor = ''
      """))
  except:
    pass


def atualizar_validade_treinamentos_para_meses():
  try:
    df = pd.read_sql("SELECT id, validade, data_realizacao FROM treinamentos WHERE validade LIKE '%ano%'", engine)
    if not df.empty:
      with engine.begin() as conn:
        for _, row in df.iterrows():
          rid, val_str, dt_real = row["id"], str(row["validade"]).lower(), row["data_realizacao"]
          numeros = "".join(filter(str.isdigit, val_str))
          anos = int(numeros) if numeros else 1
          meses = anos * 12
          nova_val = f"{meses} meses"
          novo_prox = calcular_proximo_treinamento(dt_real, nova_val)
          conn.execute(
              text("UPDATE treinamentos SET validade = :val, proximo_treinamento = :prox WHERE id = :id"),
              {"val": nova_val, "prox": novo_prox, "id": rid}
          )
  except:
    pass


def init_db():
  # Mantém compatibilidade local se necessário, mas o foco é Supabase via engine
  criar_backup_automatico()


init_db()
atualizar_cargo_setor_treinamentos_antigos()
atualizar_validade_treinamentos_para_meses()
sincronizar_status_exames()
sincronizar_status_treinamentos()
sincronizar_status_documentos()


def atualizar_filtro_empresa(empresa_nome):
  st.session_state["ultima_empresa_trabalhada"] = empresa_nome
  st.session_state["filtro_func_emp"] = empresa_nome
  st.session_state["filtro_tr_emp"] = empresa_nome
  st.session_state["filtro_ex_emp"] = empresa_nome
  st.session_state["filtro_ep_emp"] = empresa_nome
  st.session_state["filtro_doc_emp"] = empresa_nome
  st.session_state["filtro_srv_emp_trad"] = empresa_nome


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

  try:
    df_func = pd.read_sql("SELECT empresa, matricula, funcionario, cargo, setor, cpf, data_admissao, status, data_nascimento FROM base_funcionarios WHERE id = :id", engine, params={"id": id_alvo})
  except:
    df_func = pd.DataFrame()

  if not df_func.empty:
    reg_func = df_func.iloc[0]
    f_emp, f_mat, f_nome, f_cargo, f_setor, f_cpf, f_dt, f_st, f_nasc = (
        reg_func["empresa"], reg_func["matricula"], reg_func["funcionario"],
        reg_func["cargo"], reg_func["setor"], reg_func["cpf"],
        reg_func["data_admissao"], reg_func["status"], reg_func["data_nascimento"]
    )
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
      nova_data_nasc = st.text_input("Data de Nascimento", value=str(f_nasc) if f_nasc else "")
      st_limpo_f = limpar_status_banco(f_st)
      opcoes_st_f = ["Ativo", "Afastado", "Desligado"]
      try:
        idx_st_f = opcoes_st_f.index(st_limpo_f)
      except:
        idx_st_f = 0
      novo_status_f = st.selectbox(
          "Status", ["🟢 Ativo", "🟠 Afastado", "🔴 Desligado"], index=idx_st_f
      )

      if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
        dt_adm_fmt = formatar_data_flexivel_local(nova_data_adm)
        dt_nasc_fmt = formatar_data_flexivel_local(nova_data_nasc)
        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE base_funcionarios 
              SET matricula = :mat, funcionario = :nome, cargo = :cargo, setor = :setor, cpf = :cpf, data_admissao = :dt, status = :st, data_nascimento = :nasc
              WHERE id = :id
          """),
              {
                  "mat": str(novo_mat).strip(),
                  "nome": formatar_titulo(novo_nome),
                  "cargo": formatar_titulo(novo_cargo),
                  "setor": formatar_titulo(novo_setor),
                  "cpf": formatar_cpf(novo_cpf),
                  "dt": dt_adm_fmt,
                  "st": limpar_status_banco(novo_status_f),
                  "nasc": dt_nasc_fmt,
                  "id": id_alvo
              }
          )
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
  try:
    df_tr = pd.read_sql("SELECT empresa, funcionario, treinamento, carga_horaria, pessoas_treinadas, data_realizacao, validade, proximo_treinamento, status, matricula, cargo, setor FROM treinamentos WHERE id = :id", engine, params={"id": id_alvo})
    df_cad_tr_ed = pd.read_sql("SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", engine)
  except:
    df_tr = pd.DataFrame()
    df_cad_tr_ed = pd.DataFrame()

  if not df_tr.empty:
    reg_tr = df_tr.iloc[0]
    (
        t_emp, t_func, t_trein, t_carga, t_pessoas, t_data, t_val, t_prox,
        t_status, t_mat, t_cargo, t_setor
    ) = (
        reg_tr["empresa"], reg_tr["funcionario"], reg_tr["treinamento"],
        reg_tr["carga_horaria"], reg_tr["pessoas_treinadas"], reg_tr["data_realizacao"],
        reg_tr["validade"], reg_tr["proximo_treinamento"], reg_tr["status"],
        reg_tr["matricula"], reg_tr["cargo"], reg_tr["setor"]
    )
    with st.form(f"form_edicao_trein_modal_{id_alvo}"):
      st.markdown(f"**Empresa:** {t_emp}")
      try:
        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = :emp ORDER BY funcionario ASC", engine, params={"emp": t_emp})
      except:
        df_funcs_emp = pd.DataFrame()

      lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [t_func]
      if t_func not in lista_funcs:
        lista_funcs.insert(0, t_func)
      try:
        idx_f = lista_funcs.index(t_func)
      except:
        idx_f = 0
      novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
      lista_tr_ed = df_cad_tr_ed["treinamento"].tolist() if not df_cad_tr_ed.empty else []
      lista_cargas_gerais = df_cad_tr_ed["carga_horaria"].dropna().unique().tolist() if not df_cad_tr_ed.empty else []
      if not lista_cargas_gerais:
        lista_cargas_gerais = ["8 horas", "16 horas", "20 horas", "40 horas"]
      if t_trein in lista_tr_ed:
        idx_tr_sel = lista_tr_ed.index(t_trein)
        novo_trein_val = st.selectbox("Treinamento", lista_tr_ed, index=idx_tr_sel)
      else:
        novo_trein_val = st.text_input("Treinamento", value=str(t_trein))
      try:
        idx_carga = lista_cargas_gerais.index(t_carga)
      except:
        idx_carga = 0
      nova_carga_val = st.selectbox("Carga Horária", lista_cargas_gerais, index=idx_carga)
      opcoes_modalidade = ["Presencial", "Semi-presencial", "EaD"]
      try:
        idx_mod = opcoes_modalidade.index(str(t_pessoas))
      except:
        idx_mod = 0
      nova_modalidade = st.selectbox("Tipo de Treinamento", opcoes_modalidade, index=idx_mod)
      nova_data_real = st.text_input("Data da Realização", value=str(t_data))
      nova_validade = st.text_input("Validade (ex: 12 meses)", value=str(t_val) if t_val else "12 meses")
      proximo_calc_ed = calcular_proximo_treinamento(nova_data_real, nova_validade)
      novo_proximo_tr = st.text_input("Data do Próximo Treinamento", value=str(t_prox) if t_prox else proximo_calc_ed)
      st_limpo_tr = limpar_status_banco(t_status)
      opcoes_st_tr = ["em dia", "vencido"]
      try:
        idx_st_tr = opcoes_st_tr.index(st_limpo_tr.lower())
      except:
        idx_st_tr = 0
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
        proximo_final_ed = (
            calcular_proximo_treinamento(nova_data_real, nova_validade)
            if not novo_proximo_tr
            else validar_e_formatar_data_input(novo_proximo_tr)
        )
        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE treinamentos 
              SET funcionario = :func, matricula = :mat, cargo = :cargo, setor = :setor, treinamento = :trein, carga_horaria = :carga, pessoas_treinadas = :pes, data_realizacao = :dt, validade = :val, proximo_treinamento = :prox, status = :st
              WHERE id = :id
          """),
              {
                  "func": novo_func_sel,
                  "mat": str(novo_mat or ""),
                  "cargo": str(novo_c or ""),
                  "setor": str(novo_s or ""),
                  "trein": formatar_titulo(novo_trein_val),
                  "carga": str(nova_carga_val).strip(),
                  "pes": str(nova_modalidade).strip(),
                  "dt": validar_e_formatar_data_input(nova_data_real),
                  "val": str(nova_validade).strip(),
                  "prox": proximo_final_ed,
                  "st": limpar_status_banco(novo_status_tr),
                  "id": id_alvo
              }
          )
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
  try:
    df_ex = pd.read_sql("SELECT empresa, funcionario, tipo_exame, ultimo_exame, periodicidade, proximo_exame, status, matricula, cargo, setor FROM exames WHERE id = :id", engine, params={"id": id_alvo})
  except:
    df_ex = pd.DataFrame()

  if not df_ex.empty:
    reg_ex = df_ex.iloc[0]
    (
        ex_emp, ex_func, ex_tipo, ex_ultimo, ex_period, ex_proximo,
        ex_status, ex_mat, ex_cargo, ex_setor
    ) = (
        reg_ex["empresa"], reg_ex["funcionario"], reg_ex["tipo_exame"],
        reg_ex["ultimo_exame"], reg_ex["periodicidade"], reg_ex["proximo_exame"],
        reg_ex["status"], reg_ex["matricula"], reg_ex["cargo"], reg_ex["setor"]
    )
    with st.form(f"form_edicao_exame_modal_{id_alvo}"):
      st.markdown(f"**Empresa:** {ex_emp}")
      try:
        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = :emp ORDER BY funcionario ASC", engine, params={"emp": ex_emp})
      except:
        df_funcs_emp = pd.DataFrame()

      lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ex_func]
      if ex_func not in lista_funcs:
        lista_funcs.insert(0, ex_func)
      try:
        idx_f = lista_funcs.index(ex_func)
      except:
        idx_f = 0
      novo_func_sel = st.selectbox("Funcionário", lista_funcs, index=idx_f)
      opcoes_tipos_ex = ["Admissional", "Periódico", "Retorno ao Trabalho", "Mudança de Riscos", "Demissional"]
      try:
        idx_tipo_ex = opcoes_tipos_ex.index(ex_tipo)
      except:
        idx_tipo_ex = 0
      novo_tipo_ex = st.selectbox("Tipo de Exame", opcoes_tipos_ex, index=idx_tipo_ex)
      novo_ultimo_ex = st.text_input("Data Último Exame", value=str(ex_ultimo) if ex_ultimo else "")
      opcoes_periodicidade = ["1 mês", "3 meses", "6 meses", "12 meses", "18 meses", "24 meses"]
      try:
        idx_p = opcoes_periodicidade.index(ex_period)
      except:
        idx_p = 3
      nova_periodicidade = st.selectbox("Periodicidade", opcoes_periodicidade, index=idx_p)

      proximo_calc_ed = calcular_proximo_exame(novo_ultimo_ex, nova_periodicidade)
      status_calc_ed = calcular_status_por_data(proximo_calc_ed)

      novo_proximo_ex = st.text_input("Data Próximo Exame", value=proximo_calc_ed)
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
        status_final_ed = calcular_status_por_data(proximo_final_ed)

        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE exames 
              SET funcionario = :func, matricula = :mat, cargo = :cargo, setor = :setor, tipo_exame = :tipo, ultimo_exame = :ult, periodicidade = :per, proximo_exame = :prox, status = :st
              WHERE id = :id
          """),
              {
                  "func": novo_func_sel,
                  "mat": str(novo_mat or ""),
                  "cargo": str(novo_c or ""),
                  "setor": str(novo_s or ""),
                  "tipo": novo_tipo_ex,
                  "ult": validar_e_formatar_data_input(novo_ultimo_ex),
                  "per": nova_periodicidade,
                  "prox": proximo_final_ed,
                  "st": status_final_ed,
                  "id": id_alvo
              }
          )
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


@st.dialog("✏️️ Editar Registro de EPI")
def dialog_editar_epi(id_alvo):
  try:
    df_ep = pd.read_sql("SELECT empresa, funcionario, epi, ca, data_entrega, quantidade, status, matricula, cargo, setor FROM epis WHERE id = :id", engine, params={"id": id_alvo})
  except:
    df_ep = pd.DataFrame()

  if not df_ep.empty:
    reg_ep = df_ep.iloc[0]
    ep_emp, ep_func, ep_epi, ep_ca, ep_dt, ep_qtd, ep_st, ep_mat, ep_cargo, ep_setor = (
        reg_ep["empresa"], reg_ep["funcionario"], reg_ep["epi"], reg_ep["ca"],
        reg_ep["data_entrega"], reg_ep["quantidade"], reg_ep["status"],
        reg_ep["matricula"], reg_ep["cargo"], reg_ep["setor"]
    )
    with st.form(f"form_edicao_epi_modal_{id_alvo}"):
      st.markdown(f"**Empresa:** {ep_emp}")
      try:
        df_funcs_emp = pd.read_sql("SELECT matricula, funcionario, cargo, setor FROM base_funcionarios WHERE empresa = :emp ORDER BY funcionario ASC", engine, params={"emp": ep_emp})
      except:
        df_funcs_emp = pd.DataFrame()

      lista_funcs = df_funcs_emp["funcionario"].tolist() if not df_funcs_emp.empty else [ep_func]
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
          "Status", ["🟢 Entregue", "🟠 Devolvido", "🟡 Substituído"], index=idx_st_ep
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
        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE epis 
              SET funcionario = :func, matricula = :mat, cargo = :cargo, setor = :setor, epi = :epi, ca = :ca, data_entrega = :dt, quantidade = :qtd, status = :st
              WHERE id = :id
          """),
              {
                  "func": novo_func_sel,
                  "mat": str(novo_mat or ""),
                  "cargo": str(novo_c or ""),
                  "setor": str(novo_s or ""),
                  "epi": formatar_titulo(novo_epi_nome),
                  "ca": str(novo_ca).strip(),
                  "dt": validar_e_formatar_data_input(nova_data_ent),
                  "qtd": int(nova_qtd),
                  "st": limpar_status_banco(novo_status_ep),
                  "id": id_alvo
              }
          )
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
  try:
    df_doc = pd.read_sql("SELECT empresa, documento, data_emissao, vigencia, proxima_renovacao, status FROM documentos WHERE id = :id", engine, params={"id": id_alvo})
    df_cad_serv_ed_doc = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", engine)
  except:
    df_doc = pd.DataFrame()
    df_cad_serv_ed_doc = pd.DataFrame()

  lista_serv_ed_doc = df_cad_serv_ed_doc["servico"].tolist() if not df_cad_serv_ed_doc.empty else []
  if not df_doc.empty:
    reg = df_doc.iloc[0]
    d_emp, d_doc, d_emissao, d_vig, d_prox, d_st = (
        reg["empresa"], reg["documento"], reg["data_emissao"],
        reg["vigencia"], reg["proxima_renovacao"], reg["status"]
    )
    with st.form(f"form_edicao_doc_modal_{id_alvo}"):
      st.markdown(f"**Empresa:** {d_emp}")
      if lista_serv_ed_doc:
        if d_doc in lista_serv_ed_doc:
          idx_doc = lista_serv_ed_doc.index(d_doc)
          novo_doc = st.selectbox("Documento", lista_serv_ed_doc, index=idx_doc)
        else:
          lista_serv_ed_doc_opt = [d_doc] + lista_serv_ed_doc
          novo_doc = st.selectbox("Documento", lista_serv_ed_doc_opt, index=0)
      else:
        novo_doc = st.text_input("Documento", value=str(d_doc))
      nova_emissao = st.text_input("Data Emissão", value=str(d_emissao) if d_emissao else datetime.today().strftime("%d/%m/%Y"))
      nova_vigencia = st.text_input("Vigência", value=str(d_vig) if d_vig else "1 ano")
      prox_calc_ed = calcular_proxima_renovacao(nova_emissao, nova_vigencia)
      nova_proxima_renovacao = st.text_input("Data da Próxima Renovação/Atualização", value=str(d_prox) if d_prox else prox_calc_ed)

      status_calculado_ed = calcular_status_por_data(nova_proxima_renovacao if nova_proxima_renovacao else prox_calc_ed)
      st.info(f"Status calculado automaticamente: **{status_calculado_ed}**")

      if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
        proxima_final_ed = (
            calcular_proxima_renovacao(nova_emissao, nova_vigencia)
            if not nova_proxima_renovacao
            else validar_e_formatar_data_input(nova_proxima_renovacao)
        )
        status_final_ed = calcular_status_por_data(proxima_final_ed)

        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE documentos 
              SET documento = :doc, data_emissao = :dt, vigencia = :vig, proxima_renovacao = :prox, status = :st
              WHERE id = :id
          """),
              {
                  "doc": formatar_titulo(novo_doc),
                  "dt": validar_e_formatar_data_input(nova_emissao),
                  "vig": str(nova_vigencia).strip(),
                  "prox": proxima_final_ed,
                  "st": status_final_ed,
                  "id": id_alvo
              }
          )
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
  try:
    df_srv = pd.read_sql("SELECT empresa, servico, data_realizacao, responsavel, observacoes, valor, status, nfes FROM servicos_realizados WHERE id = :id", engine, params={"id": id_alvo})
    df_cad_serv_ed = pd.read_sql("SELECT servico FROM cad_servicos ORDER BY servico ASC", engine)
  except:
    df_srv = pd.DataFrame()
    df_cad_serv_ed = pd.DataFrame()

  if not df_srv.empty:
    reg_alvo = df_srv.iloc[0]
    e_emp, e_serv, e_data, e_resp, e_obs, e_val, e_status, e_nfes = (
        reg_alvo["empresa"], reg_alvo["servico"], reg_alvo["data_realizacao"],
        reg_alvo["responsavel"], reg_alvo["observacoes"], reg_alvo["valor"],
        reg_alvo["status"], reg_alvo["nfes"]
    )
    with st.form(f"form_edicao_servico_modal_{id_alvo}"):
      empresas_cad = get_empresas()
      try:
        idx_emp = empresas_cad.index(e_emp)
      except:
        idx_emp = 0
      nova_empresa = st.selectbox("Empresa Cliente", empresas_cad, index=idx_emp)
      nova_data = st.text_input("Data da Realização (DD/MM/AAAA)", value=str(e_data))
      lista_serv_ed = df_cad_serv_ed["servico"].tolist() if not df_cad_serv_ed.empty else []
      if e_serv in lista_serv_ed:
        idx_serv = lista_serv_ed.index(e_serv)
        novo_servico = st.selectbox("Serviço Executado", lista_serv_ed, index=idx_serv)
      else:
        novo_servico = st.text_input("Serviço Executado", value=str(e_serv))
      try:
        float_val = float(e_val)
      except:
        float_val = 0.0
      novo_valor = st.number_input("Valor do Serviço (R$)", min_value=0.0, value=float_val, step=50.0, format="%.2f")
      novo_resp = st.text_input("Responsável Técnico", value=str(e_resp))
      status_limpo_atual = limpar_status_banco(e_status)
      opcoes_status = ["Concluído", "Em Andamento", "Agendado", "Cancelado"]
      try:
        idx_st = opcoes_status.index(status_limpo_atual)
      except:
        idx_st = 0
      novo_status_sel = st.selectbox("Status", ["🟢 Concluído", "🟠 Em Andamento", "🟡 Agendado", "🔴 Cancelado"], index=idx_st)
      nova_nfes = st.text_input("NFES / Nº da Nota", value=str(e_nfes) if e_nfes else "")
      novas_obs = st.text_input("Observações", value=str(e_obs) if e_obs else "")

      if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
        with engine.begin() as conn:
          conn.execute(
              text("""
              UPDATE servicos_realizados 
              SET empresa = :emp, servico = :srv, data_realizacao = :dt, responsavel = :resp, observacoes = :obs, valor = :val, status = :st, nfes = :nfes
              WHERE id = :id
          """),
              {
                  "emp": nova_empresa,
                  "srv": formatar_titulo(novo_servico),
                  "dt": validar_e_formatar_data_input(nova_data),
                  "resp": formatar_titulo(novo_resp),
                  "obs": novas_obs,
                  "val": float(novo_valor),
                  "st": limpar_status_banco(novo_status_sel),
                  "nfes": str(nova_nfes).strip(),
                  "id": id_alvo
              }
          )
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
      "funcionario", "cargo", "setor", "treinamento", "epi", "servico",
      "observacoes", "responsavel", "nome_empresa", "cidade", "bairro",
      "endereco", "empresa", "cnae", "documento", "Funcionário", "Cargo",
      "Setor", "Treinamento", "EPI", "Serviço Executado", "Observações",
      "Responsável", "Nome Empresa", "Cidade", "Bairro", "Endereço",
      "Empresa", "CNAE", "Documento",
  ]
  for col in colunas_texto:
    if col in df.columns:
      df[col] = df[col].apply(lambda x: formatar_titulo(x) if isinstance(x, str) else x)
  rename_dict = {
      "id": "ID", "data_registro": "Data Registro", "nome_empresa": "Nome Empresa",
      "cnpj": "CNPJ", "cep": "CEP", "cidade": "Cidade", "bairro": "Bairro",
      "endereco": "Endereço", "telefone": "Telefone", "email": "E-mail",
      "responsavel": "Responsável", "cnae": "CNAE", "qtd_funcionarios": "Qtd Funcionários",
      "grau_risco": "Grau Risco", "matricula": "Matrícula", "funcionario": "Funcionário",
      "cargo": "Cargo", "setor": "Setor", "cpf": "CPF", "data_admissao": "Data Admissão",
      "status": "Status", "empresa": "Empresa", "treinamento": "Treinamento",
      "carga_horaria": "Carga Horária", "pessoas_treinadas": "Tipo de Treinamento",
      "data_realizacao": "Data da Realização", "validade": "Validade",
      "proximo_treinamento": "Data Próximo Treinamento", "ultimo_exame": "Último Exame",
      "periodicidade": "Periodicidade", "tipo_exame": "Tipo Exame", "proximo_exame": "Próximo Exame",
      "epi": "EPI", "ca": "CA", "data_entrega": "Data Entrega", "quantidade": "Quantidade",
      "servico": "Serviço Executado", "observacoes": "Observações", "valor": "Valor do Serviço (R$)",
      "nfes": "NFES", "documento": "Documento", "data_emissao": "Data Emissão",
      "vigencia": "Vigência", "proxima_renovacao": "Data da Próxima Renovação/Atualização",
      "data_nascimento": "Data de Nascimento",
  }
  return df.rename(columns=rename_dict)


def get_empresas():
  empresas_set = set()
  try:
    df1 = pd.read_sql(
        "SELECT DISTINCT nome_empresa FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != '' ORDER BY nome_empresa ASC",
        engine,
    )
    for e in df1["nome_empresa"].tolist():
      if str(e).strip():
        empresas_set.add(formatar_titulo(str(e).strip()))
  except:
    pass
  return sorted(list(empresas_set))


def get_cargos_por_empresa(empresa_nome):
  if not empresa_nome or empresa_nome == "Nenhuma":
    return []
  try:
    df_c = pd.read_sql(
        "SELECT DISTINCT cargo FROM cad_cargos WHERE empresa = :emp ORDER BY cargo ASC",
        engine,
        params={"emp": empresa_nome},
    )
    if not df_c.empty:
      return [str(c).strip() for c in df_c["cargo"].tolist() if str(c).strip()]
  except:
    pass
  return []


def get_setores_por_empresa(empresa_nome):
  if not empresa_nome or empresa_nome == "Nenhuma":
    return []
  try:
    df_s = pd.read_sql(
        "SELECT DISTINCT setor FROM cad_setores WHERE empresa = :emp ORDER BY setor ASC",
        engine,
        params={"emp": empresa_nome},
    )
    if not df_s.empty:
      return [str(s).strip() for s in df_s["setor"].tolist() if str(s).strip()]
  except:
    pass
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
  try:
    df_gr = pd.read_sql("SELECT grau_risco FROM grau_risco_nr04 WHERE cnae = :cnae", engine, params={"cnae": cnae_fmt})
    if not df_gr.empty:
      return str(df_gr.iloc[0]["grau_risco"]).strip()
  except:
    pass
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
              "cidade": (
                  f"{formatar_titulo(dados.get('localidade', ''))} - {dados.get('uf', '').upper()}"
                  if dados.get("uf")
                  else formatar_titulo(dados.get("localidade", ""))
              ),
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
        cidade_uf = (
            f"{formatar_titulo(dados.get('municipio', ''))} - {dados.get('uf', '').upper()}"
            if dados.get("uf")
            else formatar_titulo(dados.get("municipio", ""))
        )
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
            "telefone": (dados.get("ddd_telefone_1", "") or dados.get("telefone", "")),
            "email": dados.get("email", ""),
            "grau_risco": grau_risco,
            "cnae_principal": cnae_principal,
            "lista_cnaes": lista_cnaes,
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
          if diff <= 30:
            indices_validos.append(idx)
            break
        except ValueError:
          continue
  return df.loc[indices_validos] if indices_validos else pd.DataFrame()


def renderizar_painel_aniversariantes(engine_db, is_admin, emp_usuario):
  st.markdown("### 🎂 Aniversariantes do Mês")
  try:
    df = pd.read_sql("SELECT funcionario, empresa, data_nascimento, cargo FROM base_funcionarios", engine_db)
  except:
    df = pd.DataFrame()

  if df.empty or "data_nascimento" not in df.columns:
    st.info("Nenhum funcionário cadastrado ou coluna de data de nascimento não encontrada.")
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
  if not is_admin:
    df_aniv = df_aniv[df_aniv["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).strip().lower()]

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
    st.markdown("<h1 style='font-size: 22px; margin-bottom: 0px;'>Cassilab Consultoria e Treinamentos</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: gray; font-size: 14px; margin-top: 0px;'>Sistema de Gestão Integrada em SST</p>", unsafe_allow_html=True)
    st.write("")
    aba_login, aba_cadastro, aba_recuperar = st.tabs(["🔑 Entrar", "📝 Cadastrar", "🔄 Recuperar"])

    with aba_login:
      with st.form("form_login"):
        usuario_input = st.text_input("Usuário ou CPF (com ou sem pontuação)", value="", autocomplete="username")
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
          cpf_limpo = re.sub(r"\D", "", usuario_input)
          cpf_fmt = formatar_cpf(cpf_limpo) if len(cpf_limpo) == 11 else usuario_input

          try:
            query = text("""
                SELECT id, nome, cpf, empresa, email, celular, senha, status, nivel_permissao 
                FROM usuarios_sistema 
                WHERE (nome = :nome OR cpf = :cpf1 OR cpf = :cpf2) AND senha = :senha
            """)
            df_users = pd.read_sql(query, engine, params={"nome": usuario_input, "cpf1": cpf_limpo, "cpf2": cpf_fmt, "senha": senha_input})
            users_db = df_users.values.tolist()
          except:
            users_db = []

          if users_db:
            users_ativos = [u for u in users_db if u[7] != "Bloqueado" and u[7] != "Pendente"]
            users_pendentes = [u for u in users_db if u[7] == "Pendente"]

            if users_pendentes and not users_ativos:
              st.warning("⏳ Seu cadastro ainda está aguardando aprovação do administrador.")
            elif not users_ativos and not users_pendentes:
              st.error("⛔ Este acesso foi bloqueado pelo administrador.")
            elif len(users_ativos) == 1:
              user_db = users_ativos[0]
              st.session_state["autenticado"] = True
              st.session_state["is_admin"] = False
              st.session_state["empresa_usuario"] = user_db[3]
              st.session_state["nome_usuario"] = user_db[1]
              st.session_state["nivel_permissao"] = user_db[8] if len(user_db) > 8 and user_db[8] else "Somente Visualizar"
              registrar_log(user_db[1], user_db[3], "Login no Sistema")
              st.success(f"Bem-vindo(a), {user_db[1]}!")
              st.rerun()
            elif len(users_ativos) > 1:
              st.session_state["usuarios_multiplos"] = users_ativos
              st.rerun()
          else:
            st.error("Usuário/CPF ou senha inválidos.")

    if "usuarios_multiplos" in st.session_state and st.session_state["usuarios_multiplos"]:
      st.warning("⚠️ Encontramos mais de uma empresa vinculada ao seu CPF. Selecione qual empresa deseja acessar:")
      with st.form("form_selecionar_empresa_multipla"):
        opcoes_empresas_map = {
            f"{u[3]} (Permissão: {u[8] if len(u) > 8 and u[8] else 'Somente Visualizar'})": u
            for u in st.session_state["usuarios_multiplos"]
        }
        escolha_emp_mult = st.selectbox("Empresa Destino", list(opcoes_empresas_map.keys()))
        btn_confirmar_emp = st.form_submit_button("Acessar Empresa Selecionada", use_container_width=True)
        if btn_confirmar_emp:
          user_db = opcoes_empresas_map[escolha_emp_mult]
          st.session_state["autenticado"] = True
          st.session_state["is_admin"] = False
          st.session_state["empresa_usuario"] = user_db[3]
          st.session_state["nome_usuario"] = user_db[1]
          st.session_state["nivel_permissao"] = user_db[8] if len(user_db) > 8 and user_db[8] else "Somente Visualizar"
          del st.session_state["usuarios_multiplos"]
          registrar_log(user_db[1], user_db[3], "Login no Sistema (Múltiplas Empresas)")
          st.success(f"Bem-vindo(a) à empresa {user_db[3]}!")
          st.rerun()

    with aba_cadastro:
      with st.form("form_novo_usuario"):
        cad_nome = st.text_input("Nome Completo", value="", autocomplete="off")
        cad_cpf = st.text_input("CPF (com ou sem pontuação)", value="", autocomplete="off")
        cad_email = st.text_input("E-mail", value="", autocomplete="off")
        cad_celular = st.text_input("Celular / WhatsApp", value="", autocomplete="off")
        cad_empresa_busca = st.text_input("Nome da Empresa", value="", autocomplete="off")
        cad_senha = st.text_input("Crie uma Senha", value="", type="password", autocomplete="new-password")
        btn_cad_usuario = st.form_submit_button("Cadastrar Acesso", use_container_width=True)
        if btn_cad_usuario:
          if cad_nome and cad_cpf and cad_email and cad_celular and cad_empresa_busca and cad_senha:
            cpf_formatado = formatar_cpf(cad_cpf)
            try:
              df_emp_busca = pd.read_sql("SELECT nome_empresa FROM empresas WHERE nome_empresa ILIKE :emp LIMIT 1", engine, params={"emp": f"%{cad_empresa_busca.strip()}%"})
              if not df_emp_busca.empty:
                empresa_final = df_emp_busca.iloc[0]["nome_empresa"]
                df_ja_existe = pd.read_sql("SELECT id FROM usuarios_sistema WHERE cpf = :cpf AND empresa = :emp", engine, params={"cpf": cpf_formatado, "emp": empresa_final})
                if not df_ja_existe.empty:
                  st.error("Você já possui cadastro de acesso para esta empresa.")
                else:
                  with engine.begin() as conn:
                    conn.execute(
                        text("""
                        INSERT INTO usuarios_sistema (nome, cpf, empresa, email, celular, senha, status, nivel_permissao) 
                        VALUES (:nome, :cpf, :emp, :email, :cel, :senha, 'Pendente', 'Somente Visualizar')
                    """),
                        {
                            "nome": formatar_titulo(cad_nome), "cpf": cpf_formatado,
                            "emp": empresa_final, "email": cad_email.strip(),
                            "cel": cad_celular.strip(), "senha": cad_senha
                        }
                    )
                  st.success(f"Cadastro realizado com sucesso para a empresa {empresa_final}! Aguardando liberação do administrador.")
              else:
                st.error("Nenhuma empresa encontrada com esse nome.")
            except Exception as e:
              st.error(f"Erro ao realizar cadastro: {e}")
          else:
            st.error("Preencha todos os campos.")

    with aba_recuperar:
      with st.form("form_recuperar"):
        rec_cpf = st.text_input("Digite seu CPF cadastrado (com ou sem pontuação)", value="", autocomplete="off")
        btn_rec_enviar = st.form_submit_button("Enviar Instruções por E-mail", use_container_width=True)
        if btn_rec_enviar:
          if rec_cpf.strip():
            cpf_formatado = formatar_cpf(rec_cpf)
            cpf_limpo = re.sub(r"\D", "", rec_cpf)
            try:
              df_rec = pd.read_sql("SELECT nome, email, celular, empresa, senha FROM usuarios_sistema WHERE cpf = :cpf1 OR cpf = :cpf2", engine, params={"cpf1": cpf_formatado, "cpf2": cpf_limpo})
            except:
              df_rec = pd.DataFrame()

            if not df_rec.empty:
              res_user = df_rec.iloc[0]
              nome_u, email_u, celular_u, empresa_u, senha_u = (
                  res_user["nome"], res_user["email"], res_user["celular"],
                  res_user["empresa"], res_user["senha"]
              )
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
                  st.success(f"As instruções de recuperação de senha foram enviadas para o e-mail {email_u}.")
                  registrar_log(nome_u, empresa_u, "Solicitou recuperação de senha por e-mail")
                else:
                  st.error(f"Erro ao enviar o e-mail: {msg_ret}")
              else:
                st.error("Este usuário não possui um e-mail válido cadastrado no sistema.")
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
      f"👤 **Perfil:** Colaborador\n🏢 **Empresa:** {st.session_state['empresa_usuario']}\n🔑 **Acesso:** {st.session_state['nivel_permissao']}"
  )
else:
  st.sidebar.info(f"👤 **Perfil:** Administrador\n🔑 **Acesso:** Fazer Tudo")

if st.session_state.get("is_admin", False):
  empresas_disponiveis = ["Todas"] + get_empresas()
  if "empresa_global" not in st.session_state:
    st.session_state["empresa_global"] = "Todas"

  empresa_global_escolhida = st.sidebar.selectbox(
      "🏢 Empresa Ativa (Global)",
      empresas_disponiveis,
      index=empresas_disponiveis.index(st.session_state["empresa_global"])
      if st.session_state["empresa_global"] in empresas_disponiveis
      else 0,
  )

  if empresa_global_escolhida != st.session_state["empresa_global"]:
    st.session_state["empresa_global"] = empresa_global_escolhida
    atualizar_filtro_empresa(empresa_global_escolhida if empresa_global_escolhida != "Todas" else "")
else:
  st.session_state["empresa_global"] = st.session_state.get("empresa_usuario", "")
  empresa_global_escolhida = st.session_state["empresa_global"]

if st.session_state.get("is_admin", False):
  menu = st.sidebar.selectbox(
      "Menu Principal",
      [
          "Dashboard / Visão Geral",
          "Cadastro de Empresas",
          "Cadastros Gerais",
          "Gestão de Funcionários",
          "Treinamentos",
          "Exames Ocupacionais",
          "Controle de Absenteísmo",
          "Controle de EPIs",
          "Controle de Documentos",
          "Serviços Realizados",
          "Administração",
          "Relatórios Consolidados",
          "Elaboração de OS (Ordem de Serviço)",
          "Lista de Presença",
      ],
  )
else:
  menu = st.sidebar.selectbox(
      "Menu Principal",
      [
          "Dashboard / Visão Geral",
          "Gestão de Funcionários",
          "Treinamentos",
          "Exames Ocupacionais",
          "Controle de Absenteísmo",
          "Controle de EPIs",
          "Controle de Documentos",
          "Relatórios Consolidados",
      ],
  )

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

pode_lancar = is_admin or nivel_permissao in ["Lançar", "Editar", "Fazer Tudo"]
pode_editar = is_admin or nivel_permissao in ["Editar", "Fazer Tudo"]
pode_excluir = is_admin or nivel_permissao == "Fazer Tudo"

if st.session_state.get("msg_sucesso"):
  st.markdown(
      f"""
    <div style="background-color: #d4edda; color: #155724; padding: 15px 25px; border-radius: 10px; border: 2px solid #28a745; text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 20px; box-shadow: 0 6px 12px rgba(0,0,0,0.15);">
        {st.session_state["msg_sucesso"]}
    </div>
    """,
      unsafe_allow_html=True,
  )
  st.session_state["msg_sucesso"] = ""

# ==========================================
# 0. DASHBOARD
# ==========================================
if menu == "Dashboard / Visão Geral":
  col_t1, col_t2 = st.columns([0.8, 0.2])
  with col_t1:
    st.title("📊 Dashboard - Visão Geral Cassilab SST (Supabase)")
  with col_t2:
    st.write("")
    if st.button("🔄 Atualizar Esta Tela"):
      st.rerun()

    try:
          df_empresas_all = pd.read_sql(
              "SELECT DISTINCT nome_empresa, data_registro FROM empresas WHERE nome_empresa IS NOT NULL AND nome_empresa != ''",
              engine,
          )
          total_empresas = len(df_empresas_all) if is_admin else (1 if emp_usuario else 0)
          df_funcs_all = pd.read_sql("SELECT * FROM base_funcionarios", engine)
          df_ex_all = pd.read_sql("SELECT * FROM exames", engine)
          df_tr_all = pd.read_sql("SELECT * FROM treinamentos", engine)
          df_docs_all = pd.read_sql("SELECT * FROM documentos", engine)
    except Exception as e:
          st.error(f"⚠️ Erro exato ao carregar dados: {e}")
          total_empresas, df_empresas_all, df_funcs_all, df_ex_all, df_tr_all, df_docs_all = 0, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
 
    if not is_admin and emp_usuario:
    if not df_funcs_all.empty:
      df_funcs_all = df_funcs_all[df_funcs_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).str.strip().lower()]
    if not df_ex_all.empty:
      df_ex_all = df_ex_all[df_ex_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).str.strip().lower()]
    if not df_tr_all.empty:
      df_tr_all = df_tr_all[df_tr_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).str.strip().lower()]
    if not df_docs_all.empty:
      df_docs_all = df_docs_all[df_docs_all["empresa"].astype(str).str.strip().str.lower() == str(emp_usuario).str.strip().lower()]

    total_func_ativos = len(df_funcs_all[df_funcs_all["status"].astype(str).str.contains("Ativo|ativo", na=False)]) if not df_funcs_all.empty else 0
    total_ex_vencidos = len(df_ex_all[df_ex_all["status"].astype(str).str.contains("Vencido|vencido", na=False)]) if not df_ex_all.empty else 0
    total_tr_vencidos = len(df_tr_all[df_tr_all["status"].astype(str).str.contains("vencido|Vencido", na=False)]) if not df_tr_all.empty else 0
    total_doc_vencidos = len(df_docs_all[df_docs_all["status"].astype(str).str.contains("Vencido|vencido", na=False)]) if not df_docs_all.empty else 0

  empresas_inativas_detalhes = []
  hoje = datetime.today().date()

  if not df_empresas_all.empty:
    for _, row_e in df_empresas_all.iterrows():
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
          df_t = pd.read_sql(f"SELECT {col_d} FROM {tabela} WHERE empresa = :emp", engine, params={"emp": emp_nome})
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
        empresas_inativas_detalhes.append({"empresa": emp_nome, "dias": dias_parada})

  inativas_30 = len(empresas_inativas_detalhes)

  c1, c2, c3, c4, c5 = st.columns(5)
  with c1:
    st.markdown(f"<div style='font-size:14px; color:gray;'>🏢 Empresas Clientes</div><div style='font-size:28px; font-weight:bold;'>{total_empresas}</div><div style='font-size:12px; color:gray; margin-top:5px;'>Inativas 30 dias<br><b style='color:black; font-size:14px;'>{inativas_30:02d}</b></div>", unsafe_allow_html=True)
  with c2:
    st.markdown(f"<div style='font-size:14px; color:gray;'>👥 Funcionários</div><div style='font-size:28px; font-weight:bold;'>{len(df_funcs_all)}</div><div style='font-size:12px; color:gray; margin-top:5px;'>Ativos<br><b style='color:black; font-size:14px;'>{total_func_ativos}</b></div>", unsafe_allow_html=True)
  with c3:
    st.markdown(f"<div style='font-size:14px; color:gray;'>🩺 Exames</div><div style='font-size:28px; font-weight:bold;'>{len(df_ex_all)}</div><div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br><b style='color:red; font-size:14px;'>{total_ex_vencidos}</b></div>", unsafe_allow_html=True)
  with c4:
    st.markdown(f"<div style='font-size:14px; color:gray;'>📚 Treinamentos</div><div style='font-size:28px; font-weight:bold;'>{len(df_tr_all)}</div><div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br><b style='color:red; font-size:14px;'>{total_tr_vencidos}</b></div>", unsafe_allow_html=True)
  with c5:
    st.markdown(f"<div style='font-size:14px; color:gray;'>📄 Documentos</div><div style='font-size:28px; font-weight:bold;'>{len(df_docs_all)}</div><div style='font-size:12px; color:gray; margin-top:5px;'>Vencidos<br><b style='color:red; font-size:14px;'>{total_doc_vencidos}</b></div>", unsafe_allow_html=True)
  st.markdown("---")

  renderizar_painel_aniversariantes(engine, is_admin, emp_usuario)
  st.markdown("---")

  if is_admin:
    st.markdown("### ⚠️ Painel de Alertas (Vencidos e a vencer em até 30 dias) - Acesso Restrito Admin")
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
      df_tr_alertas = filtrar_vencidos_e_proximos(df_tr_all, "proximo_treinamento", "status")
      if not df_tr_alertas.empty:
        res_tr = df_tr_alertas[["empresa", "funcionario", "treinamento", "proximo_treinamento"]].drop_duplicates()
        for _, row in res_tr.iterrows():
          st.error(f"**{row['empresa']}**\n- {row['funcionario']} ({row['treinamento']}) - Vencimento: {row['proximo_treinamento']}")
      else:
        st.success("Nenhum treinamento vencido ou próximo.")
    with col_v3:
      st.markdown("#### 📄 Documentos (Vencidos / 30 dias)")
      df_docs_alertas = filtrar_vencidos_e_proximos(df_docs_all, "proxima_renovacao", "status")
      if not df_docs_alertas.empty:
        res_doc = df_docs_alertas[["empresa", "documento", "proxima_renovacao"]].drop_duplicates()
        for _, row in res_doc.iterrows():
          st.error(f"**{row['empresa']}**\n- {row['documento']} - Renovação: {row['proxima_renovacao']}")
      else:
        st.success("Nenhum documento vencido ou próximo.")
    st.markdown("---")

    if st.button("📧 Disparar Alertas por E-mail para Clientes com Vencimentos", use_container_width=True):
      alertas_por_empresa = {}
      if not df_ex_alertas.empty:
        for _, row in df_ex_alertas.iterrows():
          emp, item_id, dt_venc = row["empresa"], row["id"], row["proximo_exame"]
          df_ja_env = pd.read_sql("SELECT id FROM alertas_enviados WHERE empresa = :emp AND tipo_item = 'exame' AND item_id = :iid AND data_vencimento = :dt", engine, params={"emp": emp, "iid": int(item_id), "dt": dt_venc})
          if df_ja_env.empty:
            if emp not in alertas_por_empresa:
              alertas_por_empresa[emp] = {"exames": [], "treinamentos": [], "documentos": [], "tracking": []}
            alertas_por_empresa[emp]["exames"].append(f"Exame: {row['funcionario']} ({row['tipo_exame']}) - Vencimento: {dt_venc}")
            alertas_por_empresa[emp]["tracking"].append(("exame", int(item_id), dt_venc))

      if not df_tr_alertas.empty:
        for _, row in df_tr_alertas.iterrows():
          emp, item_id, dt_venc = row["empresa"], row["id"], row["proximo_treinamento"]
          df_ja_env = pd.read_sql("SELECT id FROM alertas_enviados WHERE empresa = :emp AND tipo_item = 'treinamento' AND item_id = :iid AND data_vencimento = :dt", engine, params={"emp": emp, "iid": int(item_id), "dt": dt_venc})
          if df_ja_env.empty:
            if emp not in alertas_por_empresa:
              alertas_por_empresa[emp] = {"exames": [], "treinamentos": [], "documentos": [], "tracking": []}
            alertas_por_empresa[emp]["treinamentos"].append(f"Treinamento: {row['funcionario']} ({row['treinamento']}) - Vencimento: {dt_venc}")
            alertas_por_empresa[emp]["tracking"].append(("treinamento", int(item_id), dt_venc))

      if not df_docs_alertas.empty:
        for _, row in df_docs_alertas.iterrows():
          emp, item_id, dt_venc = row["empresa"], row["id"], row["proxima_renovacao"]
          df_ja_env = pd.read_sql("SELECT id FROM alertas_enviados WHERE empresa = :emp AND tipo_item = 'documento' AND item_id = :iid AND data_vencimento = :dt", engine, params={"emp": emp, "iid": int(item_id), "dt": dt_venc})
          if df_ja_env.empty:
            if emp not in alertas_por_empresa:
              alertas_por_empresa[emp] = {"exames": [], "treinamentos": [], "documentos": [], "tracking": []}
            alertas_por_empresa[emp]["documentos"].append(f"Documento: {row['documento']} - Renovação: {dt_venc}")
            alertas_por_empresa[emp]["tracking"].append(("documento", int(item_id), dt_venc))

      enviados, erros = 0, 0
      hoje_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
      relatorio_envios = []

      for emp, dados_emp in alertas_por_empresa.items():
        if not dados_emp["exames"] and not dados_emp["treinamentos"] and not dados_emp["documentos"]:
          continue
        try:
          df_emp_e = pd.read_sql("SELECT email FROM empresas WHERE nome_empresa = :emp", engine, params={"emp": emp})
          email_emp = df_emp_e.iloc[0]["email"] if not df_emp_e.empty and df_emp_e.iloc[0]["email"] else None
        except:
          email_emp = None

        if email_emp and "@" in email_emp:
          corpo_msg = f"Prezados(as) da empresa {emp},\n\nIdentificamos em nosso sistema de Gestão SST (Cassilab) itens vencidos ou próximos do vencimento (prazo de 30 dias) que exigem atenção:\n\n"
          itens_empresa_texto = []
          if dados_emp["exames"]:
            corpo_msg += "Exames Ocupacionais:\n" + "\n".join([f"- {i}" for i in dados_emp["exames"]]) + "\n\n"
            itens_empresa_texto.extend(dados_emp["exames"])
          if dados_emp["treinamentos"]:
            corpo_msg += "Treinamentos:\n" + "\n".join([f"- {i}" for i in dados_emp["treinamentos"]]) + "\n\n"
            itens_empresa_texto.extend(dados_emp["treinamentos"])
          if dados_emp["documentos"]:
            corpo_msg += "Documentos:\n" + "\n".join([f"- {i}" for i in dados_emp["documentos"]]) + "\n\n"
            itens_empresa_texto.extend(dados_emp["documentos"])
          corpo_msg += "Por favor, entre em contato conosco ou regularize as pendências.\n\nAtenciosamente,\nCassilab Consultoria e Treinamentos em SST"

          sucesso, msg_ret = enviar_email_smtp(email_emp, "⚠️ Alerta de Vencimentos (30 dias) - Gestão SST Cassilab", corpo_msg)
          if sucesso:
            enviados += 1
            with engine.begin() as conn_tr:
              for tipo_t, id_t, dt_t in dados_emp["tracking"]:
                conn_tr.execute(
                    text("INSERT INTO alertas_enviados (empresa, tipo_item, item_id, data_vencimento, data_envio) VALUES (:emp, :tipo, :iid, :dt, :env)"),
                    {"emp": emp, "tipo": tipo_t, "iid": id_t, "dt": dt_t, "env": hoje_str}
                )
            relatorio_envios.append(f"**{emp}** ({email_emp}):\n" + "".join([f" * {item}\n" for item in itens_empresa_texto]))
          else:
            erros += 1
        else:
          erros += 1

      if enviados > 0:
        st.success(f"✅ Alertas novos enviados com sucesso para {enviados} empresa(s)!")
        st.markdown("### 📋 Resumo dos Avisos Disparados:")
        for r in relatorio_envios:
          st.markdown(r)
      elif erros > 0 and enviados == 0:
        st.warning("⚠️️ Nenhuma nova mensagem foi enviada (verifique se as empresas possuem e-mail cadastrado ou se os itens já haviam sido notificados).")
      else:
        st.info("ℹ️ Todos os vencimentos atuais já haviam sido notificados anteriormente.")
      st.markdown("---")
  else:
    st.markdown("### ⚠️ Alertas de Vencimentos da sua Empresa (30 dias)")
    col_cv1, col_cv2, col_cv3 = st.columns(3)
    with col_cv1:
      st.markdown("#### 🩺 Exames (Vencidos / 30 dias)")
      df_ex_alertas_cli = filtrar_vencidos_e_proximos(df_ex_all, "proximo_exame", "status")
      if not df_ex_alertas_cli.empty:
        res_ex_cli = df_ex_alertas_cli[["funcionario", "tipo_exame", "proximo_exame"]].drop_duplicates()
        for _, row in res_ex_cli.iterrows():
          st.warning(f"- **{row['funcionario']}** ({row['tipo_exame']}) - Vencimento: {row['proximo_exame']}")
      else:
        st.success("Nenhum exame vencido ou próximo.")
    with col_cv2:
      st.markdown("#### 📚 Treinamentos (Vencidos / 30 dias)")
      df_tr_alertas_cli = filtrar_vencidos_e_proximos(df_tr_all, "proximo_treinamento", "status")
      if not df_tr_alertas_cli.empty:
        res_tr_cli = df_tr_alertas_cli[["funcionario", "treinamento", "proximo_treinamento"]].drop_duplicates()
        for _, row in res_tr_cli.iterrows():
          st.error(f"- **{row['funcionario']}** ({row['treinamento']}) - Vencimento: {row['proximo_treinamento']}")
      else:
        st.success("Nenhum treinamento vencido ou próximo.")
    with col_cv3:
      st.markdown("#### 📄 Documentos (Vencidos / 30 dias)")
      df_docs_alertas_cli = filtrar_vencidos_e_proximos(df_docs_all, "proxima_renovacao", "status")
      if not df_docs_alertas_cli.empty:
        res_doc_cli = df_docs_alertas_cli[["documento", "proxima_renovacao"]].drop_duplicates()
        for _, row in res_doc_cli.iterrows():
          st.error(f"- {row['documento']} - Renovação: {row['proxima_renovacao']}")
      else:
        st.success("Nenhum documento vencido ou próximo.")
    st.markdown("---")

# ==========================================
# 1. CADASTRO DE EMPRESAS
# ==========================================
elif menu == "Cadastro de Empresas":
  renderizar_aba_empresas(
      engine,
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
# 2. CADASTROS GERAIS (Apenas Admin)
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
    aba_g1, aba_g_setores, aba_g2, aba_g3, aba_g4 = st.tabs(["Cargos", "Setores", "Serviços", "Treinamentos", "EPIs"])
    with aba_g1:
      st.subheader("Gerenciar Cargos por Empresa")
      with st.form("form_cad_cargo_unico"):
        empresa_cargo_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_cargo")
        novo_cargo = st.text_input("Novo Cargo")
        btn_add_salvar_cargo = st.form_submit_button("Adicionar e Salvar Cargo")
        if btn_add_salvar_cargo:
          if empresa_cargo_sel != "Nenhuma" and novo_cargo.strip():
            cargo_fmt = formatar_titulo(novo_cargo)
            try:
              df_ex_cargo = pd.read_sql("SELECT id FROM cad_cargos WHERE empresa = :emp AND cargo = :c", engine, params={"emp": empresa_cargo_sel, "c": cargo_fmt})
              if not df_ex_cargo.empty:
                st.error(f"Este cargo já está cadastrado para a empresa {empresa_cargo_sel}.")
              else:
                with engine.begin() as conn:
                  conn.execute(text("INSERT INTO cad_cargos (empresa, cargo) VALUES (:emp, :c)"), {"emp": empresa_cargo_sel, "c": cargo_fmt})
                if "edit_cargos_tbl" in st.session_state:
                  del st.session_state["edit_cargos_tbl"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_cargo_sel, f"Adicionou cargo: {cargo_fmt}")
                st.rerun()
            except Exception as e:
              st.error(f"Erro ao salvar cargo: {e}")
          else:
            st.error("Selecione a empresa e preencha o nome do cargo.")
      st.markdown("---")
      filtro_cargo_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_cargo_emp_view")
      try:
        df_cargos_geral = pd.read_sql("SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC", engine)
      except:
        df_cargos_geral = pd.DataFrame()
      if filtro_cargo_emp != "Todas as Empresas" and not df_cargos_geral.empty:
        df_cargos_geral = df_cargos_geral[df_cargos_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_cargo_emp).strip().lower()]
      if not df_cargos_geral.empty:
        if "sel_id_cargo_geral" not in st.session_state:
          st.session_state["sel_id_cargo_geral"] = None
        df_cargos_geral["_id_banco"] = df_cargos_geral["id"]
        df_cargos_geral["Selecionar"] = df_cargos_geral["_id_banco"] == st.session_state["sel_id_cargo_geral"]
        df_cargos_geral = df_cargos_geral[["Selecionar", "_id_banco", "empresa", "cargo"]]
        df_cargos_ex = formatar_colunas_tabela(df_cargos_geral)
        df_cargos_ex = adicionar_numeracao(df_cargos_ex)
        edit_cargos = st.data_editor(df_cargos_ex, hide_index=True, num_rows="fixed", key="edit_cargos_tbl", use_container_width=True, column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True), "_id_banco": None, "Nº": st.column_config.NumberColumn("Nº", disabled=True)})
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
          with engine.begin() as conn:
            for _, row in edit_cargos.iterrows():
              c_id, e_val, c_val = row.get("_id_banco"), row.get("Empresa"), row.get("Cargo")
              if pd.notna(e_val) and pd.notna(c_val) and str(c_val).strip() and pd.notna(c_id):
                conn.execute(
                    text("UPDATE cad_cargos SET empresa = :emp, cargo = :c WHERE id = :id"),
                    {"emp": str(e_val).strip(), "c": formatar_titulo(c_val), "id": int(c_id)}
                )
          if "edit_cargos_tbl" in st.session_state:
            del st.session_state["edit_cargos_tbl"]
          st.session_state["sel_id_cargo_geral"] = None
          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de cargos")
          st.rerun()
        if col_cg_2.button("🗑️ Excluir Cargo Selecionado", use_container_width=True):
          if len(linhas_sel_cargo) == 1:
            try:
              with engine.begin() as conn:
                conn.execute(text("DELETE FROM cad_cargos WHERE id = :id"), {"id": int(linhas_sel_cargo.iloc[0]["_id_banco"])})
              if "edit_cargos_tbl" in st.session_state:
                del st.session_state["edit_cargos_tbl"]
              st.session_state["sel_id_cargo_geral"] = None
              st.session_state["msg_sucesso"] = "🗑️ Cargo excluído com sucesso!"
              st.rerun()
            except Exception as e:
              st.error(f"Erro ao excluir: {e}")
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
            setor_fmt = formatar_titulo(novo_setor)
            try:
              df_ex_setor = pd.read_sql("SELECT id FROM cad_setores WHERE empresa = :emp AND setor = :s", engine, params={"emp": empresa_setor_sel, "s": setor_fmt})
              if not df_ex_setor.empty:
                st.error(f"Este setor já está cadastrado para a empresa {empresa_setor_sel}.")
              else:
                with engine.begin() as conn:
                  conn.execute(text("INSERT INTO cad_setores (empresa, setor) VALUES (:emp, :s)"), {"emp": empresa_setor_sel, "s": setor_fmt})
                if "edit_setores_tbl" in st.session_state:
                  del st.session_state["edit_setores_tbl"]
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_setor_sel, f"Adicionou setor: {setor_fmt}")
                st.rerun()
            except Exception as e:
              st.error(f"Erro ao salvar setor: {e}")
          else:
            st.error("Selecione a empresa e preencha o nome do setor.")
      st.markdown("---")
      filtro_setor_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_setor_emp_view")
      try:
        df_setores_geral = pd.read_sql("SELECT id, empresa, setor FROM cad_setores ORDER BY empresa, setor ASC", engine)
      except:
        df_setores_geral = pd.DataFrame()
      if filtro_setor_emp != "Todas as Empresas" and not df_setores_geral.empty:
        df_setores_geral = df_setores_geral[df_setores_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_setor_emp).strip().lower()]
      if not df_setores_geral.empty:
        if "sel_id_setor_geral" not in st.session_state:
          st.session_state["sel_id_setor_geral"] = None
        df_setores_geral["_id_banco"] = df_setores_geral["id"]
        df_setores_geral["Selecionar"] = df_setores_geral["_id_banco"] == st.session_state["sel_id_setor_geral"]
        df_setores_geral = df_setores_geral[["Selecionar", "_id_banco", "empresa", "setor"]]
        df_setores_ex = formatar_colunas_tabela(df_setores_geral)
        df_setores_ex = adicionar_numeracao(df_setores_ex)
        edit_setores = st.data_editor(df_setores_ex, hide_index=True, num_rows="fixed", key="edit_setores_tbl", use_container_width=True, column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True), "_id_banco": None, "Nº": st.column_config.NumberColumn("Nº", disabled=True)})
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
          with engine.begin() as conn:
            for _, row in edit_setores.iterrows():
              s_id, e_val, st_val = row.get("_id_banco"), row.get("Empresa"), row.get("Setor")
              if pd.notna(e_val) and pd.notna(st_val) and str(st_val).strip() and pd.notna(s_id):
                conn.execute(
                    text("UPDATE cad_setores SET empresa = :emp, setor = :s WHERE id = :id"),
                    {"emp": str(e_val).strip(), "s": formatar_titulo(st_val), "id": int(s_id)}
                )
          if "edit_setores_tbl" in st.session_state:
            del st.session_state["edit_setores_tbl"]
          st.session_state["sel_id_setor_geral"] = None
          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de setores")
          st.rerun()
        if col_st_2.button("🗑️ Excluir Setor Selecionado", use_container_width=True):
          if len(linhas_sel_setor) == 1:
            try:
              with engine.begin() as conn:
                conn.execute(text("DELETE FROM cad_setores WHERE id = :id"), {"id": int(linhas_sel_setor.iloc[0]["_id_banco"])})
              if "edit_setores_tbl" in st.session_state:
                del st.session_state["edit_setores_tbl"]
              st.session_state["sel_id_setor_geral"] = None
              st.session_state["msg_sucesso"] = "🗑️ Setor excluído com sucesso!"
              st.rerun()
            except Exception as e:
              st.error(f"Erro ao excluir: {e}")
          else:
            st.warning("⚠️ Selecione um setor marcando o quadradinho.")

    with aba_g2:
      st.subheader("Gerenciar Tipos de Serviços")
      with st.form("form_cad_servico_unico"):
        novo_serv = st.text_input("Novo Tipo de Serviço")
        btn_add_salvar_serv = st.form_submit_button("Adicionar e Salvar Serviço")
        if btn_add_salvar_serv:
          if novo_serv.strip():
            serv_fmt = formatar_titulo(novo_serv)
            try:
              with engine.begin() as conn:
                conn.execute(text("INSERT INTO cad_servicos (servico) VALUES (:s)"), {"s": serv_fmt})
              if "edit_serv_tbl" in st.session_state:
                del st.session_state["edit_serv_tbl"]
              st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
              registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", f"Adicionou serviço: {serv_fmt}")
              st.rerun()
            except Exception as e:
              st.error(f"Este serviço já está cadastrado ou ocorreu um erro: {e}")
          else:
            st.error("Preencha o nome do serviço.")
      st.markdown("---")
      try:
        df_serv_geral = pd.read_sql("SELECT id, servico FROM cad_servicos ORDER BY servico ASC", engine)
      except:
        df_serv_geral = pd.DataFrame()
      if not df_serv_geral.empty:
        if "sel_id_serv_geral" not in st.session_state:
          st.session_state["sel_id_serv_geral"] = None
        df_serv_geral["_id_banco"] = df_serv_geral["id"]
        df_serv_geral["Selecionar"] = df_serv_geral["_id_banco"] == st.session_state["sel_id_serv_geral"]
        df_serv_geral = df_serv_geral[["Selecionar", "_id_banco", "servico"]]
        df_serv_ex = formatar_colunas_tabela(df_serv_geral)
        df_serv_ex = adicionar_numeracao(df_serv_ex)
        edit_serv = st.data_editor(df_serv_ex, hide_index=True, num_rows="fixed", key="edit_serv_tbl", use_container_width=True, column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True), "_id_banco": None, "Nº": st.column_config.NumberColumn("Nº", disabled=True)})
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
          with engine.begin() as conn:
            for _, row in edit_serv.iterrows():
              s_id, s_val = row.get("_id_banco"), row.get("Serviço Executado")
              if pd.notna(s_val) and str(s_val).strip() and pd.notna(s_id):
                conn.execute(text("UPDATE cad_servicos SET servico = :s WHERE id = :id"), {"s": formatar_titulo(s_val), "id": int(s_id)})
          if "edit_serv_tbl" in st.session_state:
            del st.session_state["edit_serv_tbl"]
          st.session_state["sel_id_serv_geral"] = None
          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de tipos de serviços")
          st.rerun()
        if col_sv_2.button("🗑️ Excluir Serviço Selecionado", use_container_width=True):
          if len(linhas_sel_serv) == 1:
            try:
              with engine.begin() as conn:
                conn.execute(text("DELETE FROM cad_servicos WHERE id = :id"), {"id": int(linhas_sel_serv.iloc[0]["_id_banco"])})
              if "edit_serv_tbl" in st.session_state:
                del st.session_state["edit_serv_tbl"]
              st.session_state["sel_id_serv_geral"] = None
              st.session_state["msg_sucesso"] = "🗑️ Serviço excluído com sucesso!"
              st.rerun()
            except Exception as e:
              st.error(f"Erro ao excluir: {e}")
          else:
            st.warning("⚠️ Selecione um serviço marcando o quadradinho.")

    with aba_g3:
      st.subheader("Gerenciar Tipos de Treinamentos e Carga Horária")
      with st.form("form_cad_treinamento_unico"):
        c_tr_1, c_tr_2 = st.columns(2)
        novo_trein = c_tr_1.text_input("Novo Treinamento")
        nova_carga = c_tr_2.text_input("Carga Horária (ex: 16 horas, 8 horas)")
        btn_add_salvar_trein = c_tr_1.form_submit_button("Adicionar e Salvar Treinamento")
        if btn_add_salvar_trein:
          if novo_trein.strip():
            trein_fmt = formatar_titulo(novo_trein)
            try:
              with engine.begin() as conn:
                conn.execute(text("INSERT INTO cad_treinamentos (treinamento, carga_horaria) VALUES (:t, :ch)"), {"t": trein_fmt, "ch": nova_carga.strip()})
              if "edit_trein_tbl" in st.session_state:
                del st.session_state["edit_trein_tbl"]
              st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
              registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", f"Adicionou treinamento: {trein_fmt}")
              st.rerun()
            except Exception as e:
              st.error(f"Este treinamento já está cadastrado ou ocorreu um erro: {e}")
          else:
            st.error("Preencha o nome do treinamento.")
      st.markdown("---")
      try:
        df_trein_geral = pd.read_sql("SELECT id, treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", engine)
      except:
        df_trein_geral = pd.DataFrame()
      if not df_trein_geral.empty:
        if "sel_id_tr_geral" not in st.session_state:
          st.session_state["sel_id_tr_geral"] = None
        df_trein_geral["_id_banco"] = df_trein_geral["id"]
        df_trein_geral["Selecionar"] = df_trein_geral["_id_banco"] == st.session_state["sel_id_tr_geral"]
        df_trein_geral = df_trein_geral[["Selecionar", "_id_banco", "treinamento", "carga_horaria"]]
        df_trein_ex = formatar_colunas_tabela(df_trein_geral)
        df_trein_ex = adicionar_numeracao(df_trein_ex)
        edit_trein = st.data_editor(df_trein_ex, hide_index=True, num_rows="fixed", key="edit_trein_tbl", use_container_width=True, column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True), "_id_banco": None, "Nº": st.column_config.NumberColumn("Nº", disabled=True)})
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
          with engine.begin() as conn:
            for _, row in edit_trein.iterrows():
              t_id, t_val, ch_val = row.get("_id_banco"), row.get("Treinamento"), row.get("Carga Horária", "")
              if pd.notna(t_val) and str(t_val).strip() and pd.notna(t_id):
                conn.execute(
                    text("UPDATE cad_treinamentos SET treinamento = :t, carga_horaria = :ch WHERE id = :id"),
                    {"t": formatar_titulo(t_val), "ch": str(ch_val).strip(), "id": int(t_id)}
                )
          if "edit_trein_tbl" in st.session_state:
            del st.session_state["edit_trein_tbl"]
          st.session_state["sel_id_tr_geral"] = None
          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de tipos de treinamentos")
          st.rerun()
        if col_tr_2.button("🗑️ Excluir Treinamento Selecionado", use_container_width=True):
          if len(linhas_sel_tr_geral) == 1:
            try:
              with engine.begin() as conn:
                conn.execute(text("DELETE FROM cad_treinamentos WHERE id = :id"), {"id": int(linhas_sel_tr_geral.iloc[0]["_id_banco"])})
              if "edit_trein_tbl" in st.session_state:
                del st.session_state["edit_trein_tbl"]
              st.session_state["sel_id_tr_geral"] = None
              st.session_state["msg_sucesso"] = "🗑️ Treinamento excluído com sucesso!"
              st.rerun()
            except Exception as e:
              st.error(f"Erro ao excluir: {e}")
          else:
            st.warning("⚠️ Selecione um treinamento marcando o quadradinho.")

    with aba_g4:
      st.subheader("Gerenciar EPIs por Empresa (com CA)")
      with st.form("form_cad_epi_unico"):
        empresa_epi_sel = st.selectbox("Selecione a Empresa", empresas_cadastradas if empresas_cadastradas else ["Nenhuma"], key="sel_emp_epi_geral")
        c_epi_1, c_epi_2 = st.columns(2)
        novo_epi_nome = c_epi_1.text_input("Nome do EPI")
        novo_epi_ca = c_epi_2.text_input("Número do CA")
        btn_add_salvar_epi = c_epi_1.form_submit_button("Adicionar e Salvar EPI e CA")
        if btn_add_salvar_epi:
          if empresa_epi_sel != "Nenhuma" and novo_epi_nome.strip():
            epi_fmt = formatar_titulo(novo_epi_nome)
            try:
              with engine.begin() as conn:
                conn.execute(text("INSERT INTO cad_epis (empresa, epi, ca) VALUES (:emp, :epi, :ca)"), {"emp": empresa_epi_sel, "epi": epi_fmt, "ca": novo_epi_ca.strip()})
              if "edit_epis_tbl" in st.session_state:
                del st.session_state["edit_epis_tbl"]
              st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
              registrar_log(st.session_state.get("nome_usuario", "Administrador"), empresa_epi_sel, f"Adicionou EPI: {epi_fmt} (CA: {novo_epi_ca})")
              st.rerun()
            except Exception as e:
              st.error(f"Este EPI já está cadastrado para esta empresa ou ocorreu um erro: {e}")
          else:
            st.error("Selecione a empresa e preencha o nome do EPI.")
      st.markdown("---")
      filtro_epi_geral_emp = st.selectbox("Filtrar por Empresa", ["Todas as Empresas"] + empresas_cadastradas, key="filtro_epi_geral_emp_view")
      try:
        df_epis_geral = pd.read_sql("SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC", engine)
      except:
        df_epis_geral = pd.DataFrame()
      if filtro_epi_geral_emp != "Todas as Empresas" and not df_epis_geral.empty:
        df_epis_geral = df_epis_geral[df_epis_geral["empresa"].astype(str).str.strip().str.lower() == str(filtro_epi_geral_emp).strip().lower()]
      if not df_epis_geral.empty:
        if "sel_id_epi_geral" not in st.session_state:
          st.session_state["sel_id_epi_geral"] = None
        df_epis_geral["_id_banco"] = df_epis_geral["id"]
        df_epis_geral["Selecionar"] = df_epis_geral["_id_banco"] == st.session_state["sel_id_epi_geral"]
        df_epis_geral = df_epis_geral[["Selecionar", "_id_banco", "empresa", "epi", "ca"]]
        df_epis_ex = formatar_colunas_tabela(df_epis_geral)
        df_epis_ex = adicionar_numeracao(df_epis_ex)
        edit_epis = st.data_editor(df_epis_ex, hide_index=True, num_rows="fixed", key="edit_epis_tbl", use_container_width=True, column_config={"Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True), "_id_banco": None, "Nº": st.column_config.NumberColumn("Nº", disabled=True)})
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
          with engine.begin() as conn:
            for _, row in edit_epis.iterrows():
              epi_id, e_val, epi_val, ca_val = row.get("_id_banco"), row.get("Empresa"), row.get("EPI"), row.get("CA")
              if pd.notna(e_val) and pd.notna(epi_val) and str(epi_val).strip() and pd.notna(epi_id):
                conn.execute(
                    text("UPDATE cad_epis SET empresa = :emp, epi = :epi, ca = :ca WHERE id = :id"),
                    {"emp": str(e_val).strip(), "epi": formatar_titulo(epi_val), "ca": str(ca_val).strip(), "id": int(epi_id)}
                )
          if "edit_epis_tbl" in st.session_state:
            del st.session_state["edit_epis_tbl"]
          st.session_state["sel_id_epi_geral"] = None
          st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
          registrar_log(st.session_state.get("nome_usuario", "Administrador"), "Todas", "Atualização na tabela de EPIs cadastrados")
          st.rerun()
        if col_ep_2.button("🗑️ Excluir EPI Selecionado", use_container_width=True):
          if len(linhas_sel_epi_geral) == 1:
            try:
              with engine.begin() as conn:
                conn.execute(text("DELETE FROM cad_epis WHERE id = :id"), {"id": int(linhas_sel_epi_geral.iloc[0]["_id_banco"])})
              if "edit_epis_tbl" in st.session_state:
                del st.session_state["edit_epis_tbl"]
              st.session_state["sel_id_epi_geral"] = None
              st.session_state["msg_sucesso"] = "🗑️ EPI excluído com sucesso!"
              st.rerun()
            except Exception as e:
              st.error(f"Erro ao excluir: {e}")
          else:
            st.warning("⚠️ Selecione um EPI marcando o quadradinho.")

# ==========================================
# 3. GESTÃO DE FUNCIONÁRIOS
# ==========================================
elif menu == "Gestão de Funcionários":
  renderizar_aba_funcionarios(
      engine,
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
      engine,
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
      engine,
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
      engine, is_admin, emp_usuario, get_empresas, registrar_log
  )

# ==========================================
# 7. CONTROLE DE EPIS
# ==========================================
elif menu == "Controle de EPIs":
  renderizar_aba_epis(
      engine,
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
      engine,
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
      engine,
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
      engine, is_admin, enviar_email_smtp, adicionar_numeracao, registrar_log
  )

# ==========================================
# 11. RELATÓRIOS CONSOLIDADOS
# ==========================================
elif menu == "Relatórios Consolidados":
  renderizar_aba_relatorios(
      engine, is_admin, emp_usuario, get_empresas, formatar_colunas_tabela, adicionar_numeracao
  )

# ==========================================
# 12. ELABORAÇÃO DE OS (ORDEM DE SERVIÇO)
# ==========================================
elif menu == "Elaboração de OS (Ordem de Serviço)":
  renderizar_aba_os(engine, get_empresas, registrar_log)

# ==========================================
# 13. LISTA DE PRESENÇA
# ==========================================
elif menu == "Lista de Presença":
  renderizar_aba_lista_presenca(engine, is_admin, emp_usuario, get_empresas, registrar_log)