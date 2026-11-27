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
            perfis.extend(str(v).strip().lower() for v in val.values() if isinstance(v, str) and v.strip())

    for chave in CHAVES_ACESSO:
        val = st.session_state.get(chave)
        if isinstance(val, str) and val.strip():
            acessos.append(val.strip().lower())
        elif isinstance(val, dict):
            acessos.extend(str(v).strip().lower() for v in val.values() if isinstance(v, str) and v.strip())

    todos = perfis + acessos
    if not todos:
        return False

    for txt in todos:
        if txt in PERFIS_BLOQUEADOS or "usuário" in txt or "usuario" in txt:
            return False

    tem_perfil_admin = any(p in ("administrador", "admin") for p in perfis)
    tem_acesso_admin = any(a in ("fazer tudo", "administrador", "admin", "total") for a in acessos)

    if perfis and acessos:
        return tem_perfil_admin and tem_acesso_admin
    if perfis:
        return tem_perfil_admin
    return tem_acesso_admin


def _pode_gerenciar_checklists():
    """Retorna True apenas para Administrador; bloqueia qualquer usuário comum."""
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


def _obter_empresa_especifica():
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
            if "empresa" not in tab.lower():
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
                    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext or 'png'}"
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
    candidatos_nome = ["nome_empresa", "empresa", "nome", "razao_social", "nome_fantasia"]
    candidatos_logo = ["logo_empresa", "logo", "logotipo", "logo_path", "caminho_logo", "imagem_logo", "img_logo"]

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
                col_logo = next((c for c in cols if any(p in c.lower() for p in ("logo", "img", "imagem", "foto"))), None)
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
    if not TEM_REPORTLAB:
        return None

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(largura_pag, altura_pag))

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    nome_exib = empresa_especifica.strip() if tem_empresa else "Todas as Empresas"

    margem_x = 36
    topo_y = altura_pag - 24
    altura_faixa = 52

    c.setFillColor(colors.white)
    c.rect(0, topo_y - altura_faixa, largura_pag, altura_faixa + 24, stroke=0, fill=1)

    x_texto = margem_x
    if img_reader is not None:
        try:
            iw, ih = img_reader.getSize()
            max_w = 95
            max_h = 42
            escala = min(max_w / float(iw), max_h / float(ih), 1.0)
            w_draw = float(iw) * escala
            h_draw = float(ih) * escala
            y_logo = topo_y - (altura_faixa + h_draw) / 2.0
            c.drawImage(img_reader, margem_x, y_logo, width=w_draw, height=h_draw, mask="auto", preserveAspectRatio=True)
            x_texto = margem_x + w_draw + 12
        except Exception:
            x_texto = margem_x

    c.setFillColor(colors.HexColor("#1B365D"))
    c.setFont("Helvetica-Bold", 11.5)
    c.drawString(x_texto, topo_y - 21, nome_exib[:72])

    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 8)
    c.drawString(x_texto, topo_y - 35, f"Checklist SST — Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    c.setStrokeColor(colors.HexColor("#1B365D"))
    c.setLineWidth(1.0)
    c.line(margem_x, topo_y - altura_faixa, largura_pag - margem_x, topo_y - altura_faixa)

    c.save()
    buf.seek(0)
    return buf


def _preparar_arquivo_para_baixar(db_name, empresa_especifica, nome_arq, blob_dados):
    raw = bytes(blob_dados)
    ext = _extensao_arquivo(nome_arq)
    tem_empresa = not _eh_valor_todas(empresa_especifica)
    valor_logo = _buscar_logo_empresa(db_name, empresa_especifica) if tem_empresa else None
    logo_bytes, _ = _extrair_bytes_e_mime_logo(valor_logo)

    if ext == "pdf" and TEM_PYPDF and TEM_REPORTLAB:
        img_reader = _converter_para_image_reader(valor_logo) if tem_empresa else None
        if not tem_empresa and img_reader is None:
            return raw

        try:
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) == 0:
                return raw

            writer = PdfWriter()
            primeira_pag = reader.pages[0]
            largura = float(primeira_pag.mediabox.width)
            altura = float(primeira_pag.mediabox.height)

            overlay_buf = _criar_faixa_cabecalho_pdf(empresa_especifica, img_reader, largura, altura)
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
                paragrafo = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
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
        return "<p><em>Instale <code>python-docx</code> para visualizar o conteúdo do arquivo DOCX direto na tela.</em></p>"
    try:
        doc = python_docx.Document(io.BytesIO(bytes(blob_dados)))
        partes = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                partes.append(f"<p>{html.escape(txt)}</p>")
        for tab in doc.tables:
            linhas_html = []
            for row in tab.rows:
                celulas = "".join(f"<td>{html.escape(c.text.strip())}</td>" for c in row.cells)
                linhas_html.append(f"<tr>{celulas}</tr>")
            if linhas_html:
                partes.append(f"<table border='1' cellspacing='0' cellpadding='6'>{''.join(linhas_html)}</table>")
        return "\n".join(partes) if partes else "<p><em>Documento DOCX sem texto extraível.</em></p>"
    except Exception as e:
        return f"<p>Erro ao ler DOCX: {html.escape(str(e))}</p>"


def _renderizar_visualizador_direto(db_name, titulo_arq, empresa_especifica, nome_arq, arquivo_preparado):
    ext = _extensao_arquivo(nome_arq)
    titulo_seguro = html.escape(titulo_arq or nome_arq)
    tem_empresa = not _eh_valor_todas(empresa_especifica)
    empresa_segura = html.escape(empresa_especifica) if tem_empresa else "Todas as empresas"
    data_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    logo_html = ""
    if tem_empresa:
        valor_logo = _buscar_logo_empresa(db_name, empresa_especifica)
        logo_bytes, mime_logo = _extrair_bytes_e_mime_logo(valor_logo)
        if logo_bytes:
            b64_logo = base64.b64encode(logo_bytes).decode("utf-8")
            logo_html = (
                f'<img src="data:{html.escape(mime_logo)};base64,{b64_logo}" '
                f'alt="Logo {empresa_segura}" style="max-height:52px;max-width:140px;object-fit:contain;" />'
            )

    with st.container(border=True):
        st.markdown(f"#### 📄 {titulo_seguro}")
        st.caption(f"Empresa: **{empresa_segura}** • Arquivo: `{html.escape(nome_arq)}`")

        if ext == "pdf":
            b64_pdf = base64.b64encode(bytes(arquivo_preparado)).decode("utf-8")

            html_doc = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8" />
              <style>
                body {{
                  margin: 0;
                  padding: 10px;
                  font-family: Arial, sans-serif;
