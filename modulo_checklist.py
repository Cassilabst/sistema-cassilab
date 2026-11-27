import base64
import html
import io
import os
import sqlite3
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

try:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    TEM_REPORTLAB = True
except ImportError:
    TEM_REPORTLAB = False

try:
    from pypdf import PdfReader, PdfWriter
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False

try:
    import docx as python_docx
    from docx.shared import Inches
    TEM_DOCX = True
except ImportError:
    TEM_DOCX = False


EXTENSOES_PERMITIDAS = {"pdf", "docx"}

MIME_POR_EXTENSAO = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

CHAVES_PERFIL = (
    "perfil_usuario",
    "perfil",
    "tipo_perfil",
    "nivel_acesso",
    "tipo_usuario",
    "cargo_sistema",
    "funcao_usuario",
)

CHAVES_ACESSO = (
    "acesso_usuario",
    "acesso",
    "permissao",
    "permissoes",
)

PERFIS_BLOQUEADOS = {
    "usuario",
    "usuário",
    "usuario comum",
    "usuário comum",
    "user",
    "visualizador",
    "leitura",
    "somente leitura",
    "cliente",
    "empresa",
    "operador",
    "convidado",
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
    perfis = []
    acessos = []

    for chave in CHAVES_PERFIL:
        val = st.session_state.get(chave)
        if isinstance(val, str) and val.strip():
            perfis.append(val.strip().lower())
        elif isinstance(val, dict):
            perfis.extend(
                str(v).strip().lower()
                for v in val.values()
                if isinstance(v, str) and v.strip()
            )

    for chave in CHAVES_ACESSO:
        val = st.session_state.get(chave)
        if isinstance(val, str) and val.strip():
            acessos.append(val.strip().lower())
        elif isinstance(val, dict):
            acessos.extend(
                str(v).strip().lower()
                for v in val.values()
                if isinstance(v, str) and v.strip()
            )

    todos = perfis + acessos
    if not todos:
        return False

    for txt in todos:
        if txt in PERFIS_BLOQUEADOS or "usuário" in txt or "usuario" in txt:
            return False

    tem_perfil_admin = any(p in ("administrador", "admin") for p in perfis)
    tem_acesso_admin = any(
        a in ("fazer tudo", "administrador", "admin", "total") for a in acessos
    )

    if perfis and acessos:
        return tem_perfil_admin and tem_acesso_admin
    if perfis:
        return tem_perfil_admin
    return tem_acesso_admin


def _pode_gerenciar_checklists():
    return _eh_admin()


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


def _obter_empresa_especifica(empresa_do_arquivo=""):
    empresa_global = str(st.session_state.get("empresa_global", "")).strip()
    if not _eh_valor_todas(empresa_global):
        return empresa_global

    for chave in ("empresa_usuario", "empresa_cliente", "empresa_logada", "empresa"):
        val = str(st.session_state.get(chave, "")).strip()
        if not _eh_valor_todas(val):
            return val

    if not _eh_valor_todas(empresa_do_arquivo):
        return str(empresa_do_arquivo).strip()

    return ""


def _listar_empresas_banco(db_name):
    empresas = []
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
            for col_cand in ("empresa", "nome", "nome_fantasia", "razao_social"):
                if col_cand in [c.lower() for c in cols]:
                    col_real = next(c for c in cols if c.lower() == col_cand)
                    cur.execute(
                        f'SELECT DISTINCT "{col_real}" FROM "{tab}" WHERE "{col_real}" IS NOT NULL'
                    )
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


def _extrair_bytes_e_mime_logo(valor_logo):
    if valor_logo is None:
        return None, "image/png"

    if isinstance(valor_logo, (bytes, bytearray, memoryview)):
        raw = bytes(valor_logo)
        if not raw:
            return None, "image/png"
        try:
            texto = raw.decode("utf-8", errors="ignore").strip()
            if texto.startswith("data:image") and "," in texto:
                cab, b64_part = texto.split(",", 1)
                mime = cab.split(";")[0].replace("data:", "").strip() or "image/png"
                return base64.b64decode(b64_part), mime
        except Exception:
            pass
        return raw, "image/png"

    if isinstance(valor_logo, str):
        s = valor_logo.strip()
        if not s:
            return None, "image/png"

        if s.startswith("data:image") and "," in s:
            try:
                cab, b64_part = s.split(",", 1)
                mime = cab.split(";")[0].replace("data:", "").strip() or "image/png"
                return base64.b64decode(b64_part), mime
            except Exception:
                return None, "image/png"

        caminhos = [s]
        base_dir = os.path.dirname(os.path.abspath(__file__))
        caminhos.append(os.path.join(base_dir, s))
        for p in caminhos:
            if os.path.isfile(p):
                try:
                    ext = os.path.splitext(p)[1].lstrip(".").lower()
                    mime = (
                        "image/jpeg"
                        if ext in ("jpg", "jpeg")
                        else f"image/{ext or 'png'}"
                    )
                    with open(p, "rb") as f:
                        return f.read(), mime
                except Exception:
                    return None, "image/png"

        try:
            decoded = base64.b64decode(s, validate=True)
            if len(decoded) > 50:
                return decoded, "image/png"
        except Exception:
            return None, "image/png"

    return None, "image/png"


def _converter_para_image_reader(valor_logo):
    if not TEM_REPORTLAB:
        return None
    logo_bytes, _ = _extrair_bytes_e_mime_logo(valor_logo)
    if not logo_bytes:
        return None
    try:
        return ImageReader(io.BytesIO(logo_bytes))
    except Exception:
        return None


def _buscar_logo_empresa(db_name, nome_empresa):
    if _eh_valor_todas(nome_empresa):
        return None

    alvo = str(nome_empresa).strip().lower()
    candidatos_nome = [
        "nome_empresa",
        "empresa",
        "nome",
        "razao_social",
        "nome_fantasia",
    ]
    candidatos_logo = [
        "logo_empresa",
        "logo",
        "logotipo",
        "logo_path",
        "caminho_logo",
        "imagem_logo",
        "img_logo",
    ]

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
                col_logo = next(
                    (c for c in cols if any(p in c.lower() for p in ("logo", "img", "imagem", "foto"))),
                    None,
                )
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

            where_like = [f'LOWER(COALESCE("{c}", \'\')) LIKE ?' for c in cols_busca]
            params_like = [f"%{alvo}%" for _ in cols_busca]
            cur.execute(
                f'SELECT "{col_logo}" FROM "{tab}" WHERE ' + " OR ".join(where_like) + " LIMIT 1",
                params_like,
            )
            row_like = cur.fetchone()
            if row_like and row_like[0]:
                return row_like[0]
    except Exception:
        pass
    finally:
        conn.close()

    return None


def _criar_faixa_cabecalho_pdf(empresa_especifica, img_reader, largura_pag, altura_pag):
    if not TEM_REPORTLAB or img_reader is None:
        return None

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(largura_pag, altura_pag))

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    nome_exib = empresa_especifica.strip() if tem_empresa else ""

    margem_x = 32
    topo_y = altura_pag - 16
    altura_faixa = 44

    c.setFillColor(colors.white)
    c.rect(0, topo_y - altura_faixa, largura_pag, altura_faixa + 16, stroke=0, fill=1)

    try:
        iw, ih = img_reader.getSize()
        max_w = 110
        max_h = 38
        escala = min(max_w / float(iw), max_h / float(ih), 1.0)
        w_draw = float(iw) * escala
        h_draw = float(ih) * escala
        x_logo = largura_pag - margem_x - w_draw
        y_logo = topo_y - (altura_faixa + h_draw) / 2.0
        c.drawImage(
            img_reader,
            x_logo,
            y_logo,
            width=w_draw,
            height=h_draw,
            mask="auto",
            preserveAspectRatio=True,
        )
    except Exception:
        pass

    if nome_exib:
        c.setFillColor(colors.HexColor("#1B365D"))
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(margem_x, topo_y - 20, nome_exib[:65])
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("Helvetica", 7.5)
        c.drawString(
            margem_x,
            topo_y - 32,
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        )

    c.save()
    buf.seek(0)
    return buf


def _preparar_arquivo_para_baixar(db_name, empresa_especifica, nome_arq, blob_dados):
    raw = bytes(blob_dados)
    ext = _extensao_arquivo(nome_arq)
    tem_empresa = not _eh_valor_todas(empresa_especifica)
    valor_logo = _buscar_logo_empresa(db_name, empresa_especifica) if tem_empresa else None
    logo_bytes, _ = _extrair_bytes_e_mime_logo(valor_logo)

    if ext == "pdf" and TEM_PYPDF and TEM_REPORTLAB and logo_bytes:
        img_reader = _converter_para_image_reader(valor_logo)
        if img_reader is None:
            return raw

        try:
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) == 0:
                return raw

            writer = PdfWriter()
            primeira_pag = reader.pages[0]
            largura = float(primeira_pag.mediabox.width)
            altura = float(primeira_pag.mediabox.height)

            overlay_buf = _criar_faixa_cabecalho_pdf(
                empresa_especifica, img_reader, largura, altura
            )
            if overlay_buf is not None:
                overlay_reader = PdfReader(overlay_buf)
                primeira_pag.merge_page(overlay_reader.pages[0])

            writer.add_page(primeira_pag)
            for pag in reader.pages[1:]:
                writer.add_page(pag)

            out = io.BytesIO()
            writer.write(out)
            return out.getvalue()
        except Exception:
            return raw

    if ext == "docx" and TEM_DOCX and logo_bytes:
        try:
            doc = python_docx.Document(io.BytesIO(raw))
            if doc.sections:
                header = doc.sections[0].header
                paragrafo = (
                    header.paragraphs[0] if header.paragraphs else header.add_paragraph()
                )
                run = paragrafo.add_run()
                run.add_picture(io.BytesIO(logo_bytes), width=Inches(1.1))
            out = io.BytesIO()
            doc.save(out)
            return out.getvalue()
        except Exception:
            return raw

    return raw


def _renderizar_blip_html(part, blip_elem, max_h=260, max_w=240):
    try:
        ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        r_embed = blip_elem.get(f"{{{ns_r}}}embed")
        if not r_embed or r_embed not in part.related_parts:
            return ""
        img_part = part.related_parts[r_embed]
        dados_img = img_part.blob
        if not dados_img or len(dados_img) < 200:
            return ""
        content_type = getattr(img_part, "content_type", "") or "image/png"
        if "jpeg" in content_type or "jpg" in content_type:
            mime = "image/jpeg"
        elif "gif" in content_type:
            mime = "image/gif"
        elif "webp" in content_type:
            mime = "image/webp"
        else:
            mime = "image/png"
        b64_img = base64.b64encode(dados_img).decode("utf-8")
        return (
            f'<img src="data:{mime};base64,{b64_img}" '
            f'style="max-width:{max_w}px;max-height:{max_h}px;width:auto;height:auto;display:block;margin:6px auto;" />'
        )
    except Exception:
        return ""


def _paragrafo_xml_para_html(p_elem, part, em_tabela=False):
    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ns_a = "http://schemas.openxmlformats.org/drawingml/2006/main"

    pedacos = []
    for child in p_elem:
        tag = child.tag.split("}")[-1]
        if tag == "r":
            r_pr = child.find(f"{{{ns_w}}}rPr")
            negrito = r_pr is not None and r_pr.find(f"{{{ns_w}}}b") is not None
            italico = r_pr is not None and r_pr.find(f
