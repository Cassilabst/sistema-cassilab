import base64
import html
import io
import os
import sqlite3
import unicodedata
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
    "usuario comum",
    "usuário comum",
    "visualizador",
    "leitura",
    "somente leitura",
    "convidado",
}


def _normalizar_texto(texto):
    s = str(texto or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())


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
            perfis.append(_normalizar_texto(val))
        elif isinstance(val, dict):
            perfis.extend(
                _normalizar_texto(v)
                for v in val.values()
                if isinstance(v, str) and v.strip()
            )

    for chave in CHAVES_ACESSO:
        val = st.session_state.get(chave)
        if isinstance(val, str) and val.strip():
            acessos.append(_normalizar_texto(val))
        elif isinstance(val, dict):
            acessos.extend(
                _normalizar_texto(v)
                for v in val.values()
                if isinstance(v, str) and v.strip()
            )

    for a in acessos:
        if any(
            termo in a
            for termo in ("fazer tudo", "administrador", "admin", "total", "gerenciar")
        ):
            return True

    for p in perfis:
        if p in PERFIS_BLOQUEADOS:
            return False
        if any(
            termo in p
            for termo in (
                "administrador",
                "admin",
                "gestor",
                "diretor",
                "proprietario",
            )
        ):
            return True

    return False


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
    t = _normalizar_texto(texto)
    return t in ("", "todas", "todas as empresas", "geral", "nenhuma")


def _obter_empresa_especifica(empresa_do_arquivo=""):
    for chave in (
        "empresa_global",
        "empresa_selecionada",
        "empresa_ativa",
        "empresa_usuario",
        "empresa_cliente",
        "empresa_logada",
        "empresa",
    ):
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
    return sorted(empresas, key=lambda x: _normalizar_texto(x))


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
        if raw.startswith(b"\xff\xd8\xff"):
            return raw, "image/jpeg"
        if raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a"):
            return raw, "image/gif"
        if raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
            return raw, "image/webp"
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
        caminhos.append(os.path.join(base_dir, "assets", s))
        caminhos.append(os.path.join(base_dir, "logos", s))
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

    alvo_norm = _normalizar_texto(nome_empresa)
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

        tabelas_ordenadas = sorted(
            tabelas, key=lambda t: (0 if "empresa" in t.lower() else 1, t)
        )

        for tab in tabelas_ordenadas:
            if tab == "checklist_arquivos":
                continue

            cur.execute(f'PRAGMA table_info("{tab}")')
            cols = [c[1] for c in cur.fetchall()]
            cols_low = {c.lower(): c for c in cols}

            col_logo = next((cols_low[k] for k in candidatos_logo if k in cols_low), None)
            if not col_logo:
                col_logo = next(
                    (
                        c
                        for c in cols
                        if any(p in c.lower() for p in ("logo", "logotipo", "imagem", "img"))
                    ),
                    None,
                )
            if not col_logo:
                continue

            cols_busca = [cols_low[k] for k in candidatos_nome if k in cols_low]
            if not cols_busca and "empresa" in tab.lower():
                cols_busca = [
                    c for c in cols if c != col_logo and "id" not in c.lower()
                ]
            if not cols_busca:
                continue

            cols_sel = cols_busca + [col_logo]
            cols_sql = ", ".join(f'"{c}"' for c in cols_sel)
            cur.execute(f'SELECT {cols_sql} FROM "{tab}" WHERE "{col_logo}" IS NOT NULL')
            linhas = cur.fetchall()

            for row in linhas:
                val_logo = row[-1]
                if not val_logo:
                    continue
                for val_nome in row[:-1]:
                    nome_norm = _normalizar_texto(val_nome)
                    if nome_norm and (
                        nome_norm == alvo_norm
                        or alvo_norm in nome_norm
                        or nome_norm in alvo_norm
                    ):
                        return val_logo
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


def _extrair_texto_docx_html(blob_dados):
    if not TEM_DOCX:
        return "<p><em>Instale <code>python-docx</code> para visualizar o conteúdo do DOCX.</em></p>"
    try:
        doc = python_docx.Document(io.BytesIO(bytes(blob_dados)))
        partes = []

        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                partes.append("<p style='margin:6px 0;'>" + html.escape(txt) + "</p>")

        for tab in doc.tables:
            linhas_html = []
            for row in tab.rows:
                celulas = []
                for cell in row.cells:
                    texto_cel = html.escape(cell.text.strip()).replace("\n", "<br/>")
                    celulas.append(
                        "<td style='border:1px solid #888;padding:6px;font-size:11px;vertical-align:top;'>"
                        + texto_cel
                        + "</td>"
                    )
                linhas_html.append("<tr>" + "".join(celulas) + "</tr>")
            if linhas_html:
                partes.append(
                    "<div style='overflow-x:auto;max-width:100%;margin:10px 0;'>"
                    "<table style='width:100%;border-collapse:collapse;'>"
                    + "".join(linhas_html)
                    + "</table></div>"
                )

        return (
            "\n".join(partes)
            if partes
            else "<p><em>Documento DOCX sem conteúdo extraível.</em></p>"
        )
    except Exception as e:
        return "<p>Erro ao ler DOCX: " + html.escape(str(e)) + "</p>"


def _renderizar_visualizador_direto(
    db_name, titulo_arq, empresa_especifica, nome_arq, arquivo_preparado
):
    ext = _extens
