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
    TEM_DOCX = True
except ImportError:
    TEM_DOCX = False


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
    for valor in st.session_state.values():
        if isinstance(valor, str):
            v = valor.strip().lower()
            if v in ("administrador", "fazer tudo"):
                return True
        elif isinstance(valor, dict):
            for sub in valor.values():
                if isinstance(sub, str) and sub.strip().lower() in ("administrador", "fazer tudo"):
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

def _obter_logo_empresa_bytes(db_name, nome_empresa):
    """Busca e decodifica a logomarca (coluna logo_empresa) da tabela empresas."""
    if not nome_empresa or _eh_valor_todas(nome_empresa):
        return None

    try:
        conn = sqlite3.connect(db_name, timeout=10.0)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT logo_empresa
            FROM empresas
            WHERE LOWER(TRIM(nome_empresa)) = LOWER(TRIM(?))
            LIMIT 1
            """,
            (str(nome_empresa).strip(),),
        )
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return None

        raw_val = str(row[0]).strip()
        if not raw_val:
            return None

        if "," in raw_val:
            raw_val = raw_val.split(",", 1)[1]

        return base64.b64decode(raw_val)
    except Exception:
        return None


def _aplicar_logo_no_pdf(pdf_bytes, logo_bytes):
    """Insere a logomarca no canto superior direito do cabeçalho da 1ª página do PDF."""
    if not logo_bytes or not TEM_REPORTLAB or not TEM_PYPDF:
        return pdf_bytes

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if not reader.pages:
            return pdf_bytes

        primeira_pagina = reader.pages[0]
        largura_pag = float(primeira_pagina.mediabox.width)
        altura_pag = float(primeira_pagina.mediabox.height)

        img_reader = ImageReader(io.BytesIO(logo_bytes))
        img_w, img_h = img_reader.getSize()
        if not img_w or not img_h:
            return pdf_bytes

        # Limita tamanho da logo para caber bem no cabeçalho sem estourar o layout
        max_w = 95.0
        max_h = 36.0
        escala = min(max_w / float(img_w), max_h / float(img_h), 1.0)
        draw_w = float(img_w) * escala
        draw_h = float(img_h) * escala

        # Posição no topo direito da página
        x_pos = largura_pag - draw_w - 28.0
        y_pos = altura_pag - draw_h - 18.0

        packet = io.BytesIO()
        can = rl_canvas.Canvas(packet, pagesize=(largura_pag, altura_pag))
        can.drawImage(
            img_reader,
            x_pos,
            y_pos,
            width=draw_w,
            height=draw_h,
            mask="auto",
            preserveAspectRatio=True,
        )
        can.save()
        packet.seek(0)

        overlay_reader = PdfReader(packet)
        primeira_pagina.merge_page(overlay_reader.pages[0])

        writer = PdfWriter()
        for pagina in reader.pages:
            writer.add_page(pagina)

        saida = io.BytesIO()
        writer.write(saida)
        return saida.getvalue()
    except Exception:
        return pdf_bytes


def _aplicar_logo_no_docx(docx_bytes, logo_bytes):
    """Insere a logomarca no cabeçalho da primeira seção do arquivo .docx."""
    if not logo_bytes or not TEM_DOCX:
        return docx_bytes

    try:
        from docx.shared import Inches

        doc = python_docx.Document(io.BytesIO(docx_bytes))
        if doc.sections:
            header = doc.sections[0].header
            paragrafo = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            run = paragrafo.add_run()
            run.add_picture(io.BytesIO(logo_bytes), width=Inches(1.1))

        saida = io.BytesIO()
        doc.save(saida)
        return saida.getvalue()
    except Exception:
        return docx_bytes


def _converter_para_image_reader(valor_logo):
    if not TEM_REPORTLAB or valor_logo is None:
        return None

    if isinstance(valor_logo, (bytes, bytearray, memoryview)):
        raw = bytes(valor_logo)
        if not raw:
            return None
        try:
            texto = raw.decode("utf-8", errors="ignore").strip()
            if texto.startswith("data:image") and "," in texto:
                return ImageReader(io.BytesIO(base64.b64decode(texto.split(",", 1)[1])))
        except Exception:
            pass
        try:
            return ImageReader(io.BytesIO(raw))
        except Exception:
            return None

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
                col_logo = next((c for c in cols if any(p in c.lower() for p in ("logo", "img", "imagem", "foto", "arquivo"))), None)
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
    topo_y = altura_pag - 28
    altura_faixa = 54

    c.setFillColor(colors.white)
    c.rect(0, topo_y - altura_faixa, largura_pag, altura_faixa + 28, stroke=0, fill=1)

    x_texto = margem_x
    if img_reader is not None:
        try:
            iw, ih = img_reader.getSize()
            max_w = 95
            max_h = 44
            escala = min(max_w / float(iw), max_h / float(ih), 1.0)
            w_draw = float(iw) * escala
            h_draw = float(ih) * escala
            y_logo = topo_y - (altura_faixa + h_draw) / 2.0
            c.drawImage(img_reader, margem_x, y_logo, width=w_draw, height=h_draw, mask="auto")
            x_texto = margem_x + w_draw + 12
        except Exception:
            x_texto = margem_x

    c.setFillColor(colors.HexColor("#1B365D"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_texto, topo_y - 22, nome_exib[:70])

    c.setFillColor(colors.HexColor("#555555"))
    c.setFont("Helvetica", 8)
    c.drawString(x_texto, topo_y - 36, f"Checklist SST — Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    c.setStrokeColor(colors.HexColor("#1B365D"))
    c.setLineWidth(1.0)
    c.line(margem_x, topo_y - altura_faixa, largura_pag - margem_x, topo_y - altura_faixa)

    c.save()
    buf.seek(0)
    return buf


def _preparar_arquivo_para_baixar(db_name, empresa_especifica, nome_arq, blob_dados):
    raw = bytes(blob_dados)
    ext = _extensao_arquivo(nome_arq)
    if ext != "pdf" or not (TEM_PYPDF and TEM_REPORTLAB):
        return raw

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    img_reader = _converter_para_image_reader(_buscar_logo_empresa(db_name, empresa_especifica)) if tem_empresa else None

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

    # 1. BUSCA A LOGO DA EMPRESA PARA O CABEÇALHO DO DOCX (TELA E IMPRESSÃO)
    logo_html = ""
    if tem_empresa:
        valor_logo = _buscar_logo_empresa(db_name, empresa_especifica)
        if valor_logo:
            if isinstance(valor_logo, str) and valor_logo.strip().startswith("data:image"):
                logo_html = (
                    f'<img src="{html.escape(valor_logo.strip())}" '
                    f'alt="Logo {empresa_segura}" style="max-height:52px;max-width:140px;object-fit:contain;" />'
                )
            elif isinstance(valor_logo, (bytes, bytearray, memoryview)):
                b64_logo = base64.b64encode(bytes(valor_logo)).decode("utf-8")
                logo_html = (
                    f'<img src="data:image/png;base64,{b64_logo}" '
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
                  background: #f5f7fa;
                }}
                .barra {{
                  display: flex;
                  justify-content: space-between;
                  align-items: center;
                  background: #1B365D;
                  color: #ffffff;
                  padding: 10px 14px;
                  border-radius: 6px;
                }}
                .btn-acao {{
                  background: #ffffff;
                  color: #1B365D;
                  border: none;
                  padding: 8px 16px;
                  border-radius: 5px;
                  font-weight: bold;
                  cursor: pointer;
                }}
                .btn-acao:hover {{
                  background: #e6eef8;
                }}
                .aviso {{
                  margin-top: 10px;
                  padding: 14px;
                  background: #ffffff;
                  border: 1px solid #d0d7de;
                  border-radius: 6px;
                  color: #333;
                  font-size: 14px;
                }}
              </style>
            </head>
            <body>
              <div class="barra">
                <span><strong>{titulo_seguro}</strong> — {empresa_segura}</span>
                <button class="btn-acao" onclick="abrirPdfNovaAba()">🗗 Visualizar / Imprimir PDF</button>
              </div>
              <div class="aviso">
                Clique em <strong>Visualizar / Imprimir PDF</strong> para abrir o documento completo em uma nova aba e imprimir direto pelo navegador.
              </div>
              <script>
                function abrirPdfNovaAba() {{
                  const b64 = "{b64_pdf}";
                  const byteChars = atob(b64);
                  const byteArrays = [];
                  for (let offset = 0; offset < byteChars.length; offset += 512) {{
                    const slice = byteChars.slice(offset, offset + 512);
                    const byteNumbers = new Array(slice.length);
                    for (let i = 0; i < slice.length; i++) {{
                      byteNumbers[i] = slice.charCodeAt(i);
                    }}
                    byteArrays.push(new Uint8Array(byteNumbers));
                  }}
                  const blob = new Blob(byteArrays, {{ type: "application/pdf" }});
                  const blobUrl = URL.createObjectURL(blob);
                  window.open(blobUrl, "_blank");
                }}
              </script>
            </body>
            </html>
            """
            components.html(html_doc, height=130, scrolling=False)
        else:
            corpo_docx = _extrair_texto_docx_html(arquivo_preparado)
            html_doc = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8" />
              <style>
                body {{ margin: 0; padding: 14px; font-family: Arial, sans-serif; background: #f5f7fa; color: #222; }}
                .barra-topo {{
                  display: flex; justify-content: space-between; align-items: center;
                  background: #1B365D; color: #ffffff; padding: 8px 14px; border-radius: 6px; margin-bottom: 12px;
                }}
                .btn-imprimir {{
                  background: #ffffff; color: #1B365D; border: none; padding: 7px 14px;
                  border-radius: 5px; font-weight: bold; cursor: pointer;
                }}
                .folha {{
                  background: #ffffff; padding: 24px; border: 1px solid #d0d7de;
                  border-radius: 6px; max-height: 580px; overflow-y: auto;
                }}
                /* 2. ESTILO DO CABEÇALHO COM A LOGO NA TELA */
                .cabecalho-doc {{
                  display: flex; justify-content: space-between; align-items: center;
                  gap: 16px; border-bottom: 2px solid #1B365D; padding-bottom: 12px; margin-bottom: 14px;
                }}
                table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
              </style>
            </head>
            <body>
              <div class="barra-topo">
                <span><strong>{titulo_seguro}</strong> — {empresa_segura}</span>
                <button class="btn-imprimir" onclick="imprimirDocx()">🖨️ Imprimir</button>
              </div>
              <div class="folha" id="areaImpressao">
                <!-- 3. LOGO MOSTRADA NO CABEÇALHO DO DOCX -->
                <div class="cabecalho-doc">
                  <div>
                    <h2 style="margin:0 0 4px 0;">{titulo_seguro}</h2>
                    <small>Empresa: {empresa_segura} • Gerado em: {html.escape(data_str)}</small>
                  </div>
                  <div>{logo_html}</div>
                </div>
                {corpo_docx}
              </div>
              <script>
                function imprimirDocx() {{
                  const conteudo = document.getElementById('areaImpressao').innerHTML;
                  const win = window.open("", "_blank");
                  if (win) {{
                    win.document.write(
                      '<html><head><title>{titulo_seguro}</title><style>' +
                      'body{{font-family:Arial,sans-serif;padding:24px;color:#222;}}' +
                      '.cabecalho-doc{{display:flex;justify-content:space-between;align-items:center;gap:16px;border-bottom:2px solid #1B365D;padding-bottom:12px;margin-bottom:14px;}}' +
                      'table{{width:100%;border-collapse:collapse;margin:12px 0;}}' +
                      'td,th{{border:1px solid #888;padding:6px;}}' +
                      '</style></head><body>' + conteudo + '</body></html>'
                    );
                    win.document.close();
                    win.focus();
                    win.print();
                  }} else {{
                    window.print();
                  }}
                }}
              </script>
            </body>
            </html>
            """
            components.html(html_doc, height=680, scrolling=True)
        else:
            corpo_docx = _extrair_texto_docx_html(arquivo_preparado)
            html_doc = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8" />
              <style>
                body {{ margin: 0; padding: 14px; font-family: Arial, sans-serif; background: #f5f7fa; color: #222; }}
                .barra-topo {{
                  display: flex; justify-content: space-between; align-items: center;
                  background: #1B365D; color: #ffffff; padding: 8px 14px; border-radius: 6px; margin-bottom: 12px;
                }}
                .btn-imprimir {{
                  background: #ffffff; color: #1B365D; border: none; padding: 7px 14px;
                  border-radius: 5px; font-weight: bold; cursor: pointer;
                }}
                .folha {{
                  background: #ffffff; padding: 24px; border: 1px solid #d0d7de;
                  border-radius: 6px; max-height: 580px; overflow-y: auto;
                }}
                table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
              </style>
            </head>
            <body>
              <div class="barra-topo">
                <span><strong>{titulo_seguro}</strong> — {empresa_segura}</span>
                <button class="btn-imprimir" onclick="imprimirDocx()">🖨️ Imprimir</button>
              </div>
              <div class="folha" id="areaImpressao">
                <h2>{titulo_seguro}</h2>
                <small>Empresa: {empresa_segura} • Gerado em: {html.escape(data_str)}</small>
                <hr/>
                {corpo_docx}
              </div>
              <script>
                function imprimirDocx() {{
                  const conteudo = document.getElementById('areaImpressao').innerHTML;
                  const win = window.open("", "_blank");
                  if (win) {{
                    win.document.write(
                      '<html><head><title>{titulo_seguro}</title><style>' +
                      'body{{font-family:Arial,sans-serif;padding:24px;color:#222;}}' +
                      'table{{width:100%;border-collapse:collapse;margin:12px 0;}}' +
                      'td,th{{border:1px solid #888;padding:6px;}}' +
                      '</style></head><body>' + conteudo + '</body></html>'
                    );
                    win.document.close();
                    win.focus();
                    win.print();
                  }} else {{
                    window.print();
                  }}
                }}
              </script>
            </body>
            </html>
            """
            components.html(html_doc, height=680, scrolling=True)


def renderizar_modulo_checklist(db_name, registrar_log_callback=None):
    try:
        _garantir_tabela_arquivos_checklist(db_name)

        st.title("Checklists")
        st.markdown("Checklists cadastrados para visualização e impressão direta")

        empresa_especifica = _obter_empresa_especifica()
        if empresa_especifica:
            st.caption(f"Empresa ativa: **{empresa_especifica}**")
        else:
            st.caption("Visualização: **Todas as empresas** (impressão sem logo)")

        admin_mode = _eh_admin()

        if admin_mode:
            opcoes_escopo = ["Todas as empresas (Geral)"] + _listar_empresas_banco(db_name)
            with st.expander("➕ Adicionar novo arquivo de checklist (Admin)", expanded=False):
                with st.form("form_upload_checklist", clear_on_submit=True):
                    titulo = st.text_input(
                        "Título do Checklist",
                        placeholder="Ex.: Checklist Andaimes - Inspeção de Segurança",
                    )
                    descricao = st.text_area(
                        "Descrição (opcional)",
                        placeholder="Ex.: Orientações gerais ou observações do checklist.",
                        height=75,
                    )
                    escopo_empresa = st.selectbox("Disponível para", opcoes_escopo)
                    arquivo_up = st.file_uploader(
                        "Selecione o arquivo (somente PDF ou DOCX)",
                        type=["pdf", "docx"],
                    )
                    btn_enviar = st.form_submit_button("Salvar Arquivo")

                    if btn_enviar:
                        if not titulo.strip():
                            st.error("Informe o título do checklist.")
                        elif arquivo_up is None:
                            st.error("Selecione um arquivo PDF ou DOCX para enviar.")
                        else:
                            ext = _extensao_arquivo(arquivo_up.name)
                            if ext not in EXTENSOES_PERMITIDAS:
                                st.error("Formato não permitido. Envie apenas arquivos .PDF ou .DOCX.")
                            else:
                                dados_bytes = arquivo_up.getvalue()
                                empresa_alvo = "" if escopo_empresa.startswith("Todas") else escopo_empresa
                                data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                                mime_final = MIME_POR_EXTENSAO.get(ext, arquivo_up.type or "application/octet-stream")

                                conn = sqlite3.connect(db_name, timeout=10.0)
                                cur = conn.cursor()
                                cur.execute(
                                    """
                                    INSERT INTO checklist_arquivos
                                        (empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        empresa_alvo,
                                        titulo.strip(),
                                        descricao.strip(),
                                        arquivo_up.name,
                                        mime_final,
                                        len(dados_bytes),
                                        sqlite3.Binary(dados_bytes),
                                        data_agora,
                                    ),
                                )
                                conn.commit()
                                conn.close()

                                if callable(registrar_log_callback):
                                    registrar_log_callback(
                                        st.session_state.get("nome_usuario", "Administrador"),
                                        empresa_alvo or "Geral",
                                        f"Adicionou arquivo de checklist: {titulo.strip()} ({arquivo_up.name})",
                                    )

                                st.success("Arquivo adicionado com sucesso!")
                                st.rerun()

        st.markdown("---")
        st.subheader("Checklists Disponíveis")

        conn = sqlite3.connect(db_name, timeout=10.0)
        cur = conn.cursor()
        if empresa_especifica:
            cur.execute(
                """
                SELECT id, empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload
                FROM checklist_arquivos
                WHERE TRIM(COALESCE(empresa, '')) = ''
                   OR LOWER(TRIM(empresa)) = LOWER(TRIM(?))
                ORDER BY LOWER(TRIM(titulo)) ASC, id DESC
                """,
                (empresa_especifica,),
            )
        else:
            cur.execute(
                """
                SELECT id, empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload
                FROM checklist_arquivos
                ORDER BY LOWER(TRIM(titulo)) ASC, id DESC
                """
            )
        arquivos = cur.fetchall()
        conn.close()

        if not arquivos:
            st.info("Nenhum arquivo de checklist disponível no momento.")
            return

        item_aberto_key = "checklist_visualizar_id"
        if item_aberto_key not in st.session_state:
            st.session_state[item_aberto_key] = None

        for arq_id, emp_arq, titulo_arq, desc_arq, nome_arq, mime_arq, tam_bytes, blob_dados, dt_up in arquivos:
            arquivo_preparado = _preparar_arquivo_para_baixar(db_name, empresa_especifica, nome_arq, blob_dados)

            with st.container(border=True):
                col_info, col_acao = st.columns([4, 1.8])

                with col_info:
                    escopo_txt = emp_arq.strip() if emp_arq and emp_arq.strip() else "Todas as empresas"
                    st.markdown(f"**{titulo_arq}**")
                    if desc_arq and desc_arq.strip():
                        st.write(desc_arq.strip())
                    st.caption(
                        f"Arquivo: `{nome_arq}` • Tamanho: {_formatar_tamanho(tam_bytes)} • Escopo: {escopo_txt} • Enviado em: {dt_up or '—'}"
                    )

                with col_acao:
                    esta_aberto = st.session_state[item_aberto_key] == arq_id
                    btn_txt = "🔼 Fechar" if esta_aberto else "👁️ Visualizar"
                    if st.button(btn_txt, key=f"btn_vis_{arq_id}", use_container_width=True):
                        st.session_state[item_aberto_key] = None if esta_aberto else arq_id
                        st.rerun()

                    if admin_mode:
                        if st.button("🗑️ Remover", key=f"del_checklist_{arq_id}", use_container_width=True):
                            conn_del = sqlite3.connect(db_name, timeout=10.0)
                            conn_del.execute("DELETE FROM checklist_arquivos WHERE id = ?", (arq_id,))
                            conn_del.commit()
                            conn_del.close()

                            if callable(registrar_log_callback):
                                registrar_log_callback(
                                    st.session_state.get("nome_usuario", "Administrador"),
                                    emp_arq or "Geral",
                                    f"Removeu arquivo de checklist: {titulo_arq} ({nome_arq})",
                                )

                            st.success("Arquivo removido!")
                            st.rerun()

            if st.session_state[item_aberto_key] == arq_id:
                _renderizar_visualizador_direto(
                    db_name=db_name,
                    titulo_arq=titulo_arq,
                    empresa_especifica=empresa_especifica,
                    nome_arq=nome_arq,
                    arquivo_preparado=arquivo_preparado,
                )
    except Exception as erro_checklist:
        st.error(f"Erro ao renderizar o módulo Checklists: {erro_checklist}")
        st.exception(erro_checklist)
