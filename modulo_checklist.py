import base64
import io
import os
import sqlite3
from datetime import datetime
import streamlit as st

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    TEM_REPORTLAB = True
except ImportError:
    TEM_REPORTLAB = False


EXTENSOES_PERMITIDAS = {"pdf", "docx"}

MIME_POR_EXTENSAO = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _garantir_tabela_arquivos_checklist(db_name):
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_arquivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            nome_arquivo TEXT NOT NULL,
            tipo_mime TEXT,
            tamanho_bytes INTEGER,
            conteudo_arquivo BLOB NOT NULL,
            data_upload TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _eh_admin():
    perfil = str(st.session_state.get("perfil_usuario", st.session_state.get("perfil", ""))).strip().lower()
    acesso = str(st.session_state.get("acesso_usuario", st.session_state.get("acesso", ""))).strip().lower()
    if "admin" in perfil or "fazer tudo" in acesso:
        return True
    if not perfil and not acesso:
        return True
    return False


def _formatar_tamanho(num_bytes):
    if not num_bytes:
        return "—"
    kb = num_bytes / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    return f"{kb / 1024.0:.2f} MB"


def _extensao_arquivo(nome_arquivo):
    if not nome_arquivo:
        return ""
    return os.path.splitext(str(nome_arquivo))[1].lstrip(".").lower()


def _eh_valor_todas(texto):
    t = str(texto or "").strip().lower()
    return t in ("", "todas", "todas as empresas", "geral", "nenhuma")


def _obter_empresa_especifica():
    """
    Retorna o nome da empresa específica quando selecionada ou do usuário comum.
    Se estiver em 'Todas' / 'Todas as empresas', retorna ''.
    """
    empresa_global = str(st.session_state.get("empresa_global", "")).strip()
    if not _eh_valor_todas(empresa_global):
        return empresa_global

    if not _eh_admin():
        for chave in ("empresa_usuario", "empresa_cliente", "empresa_logada", "empresa"):
            val = str(st.session_state.get(chave, "")).strip()
            if not _eh_valor_todas(val):
                return val

    return ""


def _listar_empresas_banco(db_name):
    empresas = []
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [r[0] for r in cur.fetchall()]
        for tab in tabelas:
            tab_low = tab.lower()
            if "empresa" not in tab_low:
                continue
            cur.execute(f'PRAGMA table_info("{tab}")')
            cols = [c[1] for c in cur.fetchall()]
            for col_cand in ("empresa", "nome", "nome_fantasia", "razao_social"):
                if col_cand in [c.lower() for c in cols]:
                    col_real = next(c for c in cols if c.lower() == col_cand)
                    cur.execute(f'SELECT DISTINCT "{col_real}" FROM "{tab}" WHERE "{col_real}" IS NOT NULL')
                    for (nome_emp,) in cur.fetchall():
                        s = str(nome_emp or "").strip()
                        if not _eh_valor_todas(s) and s not in empresas:
                            empresas.append(s)
                    break
    except Exception:
        pass
    finally:
        conn.close()
    return sorted(empresas, key=lambda x: x.lower())


def _converter_para_image_reader(valor_logo):
    if valor_logo is None:
        return None

    if isinstance(valor_logo, (bytes, bytearray, memoryview)):
        raw = bytes(valor_logo)
        if not raw:
            return None
        try:
            texto = raw.decode("utf-8").strip()
            if texto.startswith("data:image") and "," in texto:
                return ImageReader(io.BytesIO(base64.b64decode(texto.split(",", 1)[1])))
        except Exception:
            pass
        return ImageReader(io.BytesIO(raw))

    if isinstance(valor_logo, str):
        s = valor_logo.strip()
        if not s:
            return None
        if s.startswith("data:image") and "," in s:
            try:
                return ImageReader(io.BytesIO(base64.b64decode(s.split(",", 1)[1])))
            except Exception:
                return None
        if os.path.isfile(s):
            try:
                return ImageReader(s)
            except Exception:
                return None
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(base_dir, s)
        if os.path.isfile(cand):
            try:
                return ImageReader(cand)
            except Exception:
                return None
        try:
            decoded = base64.b64decode(s, validate=True)
            if len(decoded) > 100:
                return ImageReader(io.BytesIO(decoded))
        except Exception:
            return None

    return None


def _buscar_logo_empresa(db_name, nome_empresa):
    if _eh_valor_todas(nome_empresa):
        return None

    alvo = nome_empresa.strip().lower()
    candidatos_nome = ["empresa", "nome", "razao_social", "nome_fantasia"]
    candidatos_logo = ["logo", "logotipo", "logo_empresa", "logo_path", "caminho_logo", "imagem_logo", "img_logo"]

    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [r[0] for r in cur.fetchall()]

        for tab in tabelas:
            if "empresa" not in tab.lower():
                continue

            cur.execute(f'PRAGMA table_info("{tab}")')
            cols = [c[1] for c in cur.fetchall()]
            cols_low = {c.lower(): c for c in cols}

            col_logo = next((cols_low[k] for k in candidatos_logo if k in cols_low), None)
            if not col_logo:
                col_logo = next((c for c in cols if "logo" in c.lower()), None)
            if not col_logo:
                continue

            cols_busca = [cols_low[k] for k in candidatos_nome if k in cols_low]
            if not cols_busca:
                continue

            where_clauses = [f'LOWER(TRIM(COALESCE("{c}", \'\'))) = ?' for c in cols_busca]
            params = [alvo for _ in cols_busca]

            cur.execute(
                f'SELECT "{col_logo}" FROM "{tab}" WHERE ' + " OR ".join(where_clauses) + " LIMIT 1",
                params,
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    finally:
        conn.close()

    return None
