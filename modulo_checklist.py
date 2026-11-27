import base64
import html
import io
import os
import sqlite3
import zipfile
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


def _extrair_imagens_docx_html(blob_dados):
    imagens_html = []
    try:
        with zipfile.ZipFile(io.BytesIO(bytes(blob_dados)), "r") as zf:
            arquivos_media = sorted(
                [
                    n
                    for n in zf.namelist()
                    if n.lower().startswith("word/media/")
                    and os.path.splitext(n)[1].lower()
                    in (".png", ".jpg", ".jpeg", ".gif", ".webp")
                ]
            )
            for arq_img in arquivos_media:
                ext = os.path.splitext(arq_img)[1].lstrip(".").lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                dados_img = zf.read(arq_img)
                if len(dados_img) > 200:
                    b64_img = base64.b64encode(dados_img).decode("utf-8")
                    imagens_html.append(
                        f'<div style="margin:12px 0;text-align:center;">'
                        f'<img src="data:{mime};base64,{b64_img}" '
                        f'style="max-width:100%;max-height:340px;height:auto;border:1px solid #d0d7de;border-radius:4px;padding:4px;" />'
                        f'</div>'
                    )
    except Exception:
        pass
    return "\n".join(imagens_html)


def _extrair_texto_docx_html(blob_dados):
    imagens_bloco = _extrair_imagens_docx_html(blob_dados)
    if not TEM_DOCX:
        return (
            imagens_bloco
            + "<p><em>Instale <code>python-docx</code> para visualizar o texto do DOCX.</em></p>"
        )
    try:
        doc = python_docx.Document(io.BytesIO(bytes(blob_dados)))
        partes = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                partes.append(f"<p style='margin:6px 0;'>{html.escape(txt)}</p>")
        for tab in doc.tables:
            linhas_html = []
            for row in tab.rows:
                celulas = "".join(
                    f"<td style='border:1px solid #888;padding:6px;font-size:12px;'>{html.escape(c.text.strip())}</td>"
                    for c in row.cells
                )
                linhas_html.append(f"<tr>{celulas}</tr>")
            if linhas_html:
                partes.append(
                    f"<table style='width:100%;border-collapse:collapse;margin:12px 0;'>{''.join(linhas_html)}</table>"
                )
        conteudo = "\n".join(partes) if partes else "<p><em>Documento DOCX sem texto extraível.</em></p>"
        if imagens_bloco:
            return f"<div style='display:grid;grid-template-columns:260px 1fr;gap:16px;align-items:start;'><div>{imagens_bloco}</div><div>{conteudo}</div></div>"
        return conteudo
    except Exception as e:
        return f"<p>Erro ao ler DOCX: {html.escape(str(e))}</p>"


def _renderizar_visualizador_direto(
    db_name, titulo_arq, empresa_especifica, nome_arq, arquivo_preparado
):
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
                  border-radius: 6px; max-height: 620px; overflow-y: auto;
                }}
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
            components.html(html_doc, height=700, scrolling=True)


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

        pode_gerenciar = _pode_gerenciar_checklists()

        if pode_gerenciar:
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
                                mime_final = MIME_POR_EXTENSAO.get(
                                    ext, arquivo_up.type or "application/octet-stream"
                                )

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

        for (
            arq_id,
            emp_arq,
            titulo_arq,
            desc_arq,
            nome_arq,
            mime_arq,
            tam_bytes,
            blob_dados,
            dt_up,
        ) in arquivos:
            empresa_efetiva = _obter_empresa_especifica(emp_arq)
            arquivo_preparado = _preparar_arquivo_para_baixar(
                db_name, empresa_efetiva, nome_arq, blob_dados
            )

            with st.container(border=True):
                col_info, col_acao = st.columns([4, 1.8])

                with col_info:
                    escopo_txt = (
                        emp_arq.strip()
                        if emp_arq and emp_arq.strip()
                        else "Todas as empresas"
                    )
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

                    if pode_gerenciar:
                        if st.button(
                            "🗑️ Remover",
                            key=f"del_checklist_{arq_id}",
                            use_container_width=True,
                        ):
                            conn_del = sqlite3.connect(db_name, timeout=10.0)
                            conn_del.execute(
                                "DELETE FROM checklist_arquivos WHERE id = ?", (arq_id,)
                            )
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
                    empresa_especifica=empresa_efetiva,
                    nome_arq=nome_arq,
                    arquivo_preparado=arquivo_preparado,
                )
    except Exception as erro_checklist:
        st.error(f"Erro ao renderizar o módulo Checklists: {erro_checklist}")
        st.exception(erro_checklist)
