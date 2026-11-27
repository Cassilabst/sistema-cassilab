import base64
import io
import os
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
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


def _converter_para_image_reader(valor_logo):
    if valor_logo is None:
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

            # Busca parcial caso o nome tenha sufixos/prefixos
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


def _extrair_itens_docx(blob_bytes):
    itens = []
    try:
        with zipfile.ZipFile(io.BytesIO(blob_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return itens
            xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

            # Extrai linhas de tabelas
            for tr in root.findall(".//w:tr", ns):
                celulas = []
                for tc in tr.findall(".//w:tc", ns):
                    textos_tc = ["".join(t.itertext()).strip() for t in tc.findall(".//w:p", ns)]
                    texto_cel = " ".join([x for x in textos_tc if x]).strip()
                    celulas.append(texto_cel)
                linha_unida = " | ".join([c for c in celulas if c]).strip()
                if linha_unida and linha_unida.lower() not in ("item", "descrição", "descricao", "c", "nc", "n/a", "observações", "observacoes"):
                    itens.append(linha_unida)

            # Se não houver tabelas ou além delas, extrai parágrafos relevantes
            for p in root.findall(".//w:p", ns):
                # Evita duplicar parágrafos já dentro de tabela
                txt = "".join(p.itertext()).strip()
                if txt and txt not in itens:
                    itens.append(txt)
    except Exception:
        pass
    return itens


def _extrair_itens_pdf(blob_bytes):
    itens = []

    # 1) Tenta bibliotecas PDF caso existam no ambiente
    for mod_name in ("pypdf", "PyPDF2", "pdfplumber", "fitz"):
        try:
            if mod_name == "pypdf":
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(blob_bytes))
                texto_total = "\n".join([(page.extract_text() or "") for page in reader.pages])
            elif mod_name == "PyPDF2":
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(blob_bytes))
                texto_total = "\n".join([(page.extract_text() or "") for page in reader.pages])
            elif mod_name == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(io.BytesIO(blob_bytes)) as pdf:
                    texto_total = "\n".join([(p.extract_text() or "") for p in pdf.pages])
            elif mod_name == "fitz":
                import fitz
                doc = fitz.open(stream=blob_bytes, filetype="pdf")
                texto_total = "\n".join([(page.get_text("text") or "") for page in doc])

            for linha in texto_total.splitlines():
                limpa = re.sub(r"\s+", " ", linha).strip()
                if len(limpa) >= 3:
                    itens.append(limpa)
            if itens:
                return itens
        except Exception:
            continue

    # 2) Fallback nativo para streams de texto de PDF simples
    try:
        raw = blob_bytes.decode("latin-1", errors="ignore")
        for match in re.findall(r"\(([^()]{2,200})\)\s*Tj", raw):
            limpa = re.sub(r"\\[nr]|[^\x20-\x7E\u00C0-\u00FF]", " ", match)
            limpa = re.sub(r"\s+", " ", limpa).strip()
            if len(limpa) >= 3:
                itens.append(limpa)
    except Exception:
        pass

    return itens


def _extrair_itens_do_arquivo(nome_arq, blob_dados):
    ext = _extensao_arquivo(nome_arq)
    if not blob_dados:
        return []
    raw = bytes(blob_dados)
    if ext == "docx":
        return _extrair_itens_docx(raw)
    if ext == "pdf":
        return _extrair_itens_pdf(raw)
    return []


def _escapar_xml(texto):
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _gerar_pdf_checklist_com_logo(db_name, empresa_especifica, titulo_arq, desc_arq, nome_arq, dt_up, blob_dados):
    if not TEM_REPORTLAB:
        return None

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    empresa_exibicao = empresa_especifica.strip() if tem_empresa else "Todas as Empresas (Modelo Geral)"
    img_reader = _converter_para_image_reader(_buscar_logo_empresa(db_name, empresa_especifica)) if tem_empresa else None

    itens_extraidos = _extrair_itens_do_arquivo(nome_arq, blob_dados)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )

    styles = getSampleStyleSheet()
    style_empresa = ParagraphStyle(
        "EmpresaHeader",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1B365D"),
        spaceAfter=2,
    )
    style_sub = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#555555"),
    )
    style_titulo = ParagraphStyle(
        "TituloChecklist",
        parent=styles["Heading1"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#111111"),
        spaceBefore=6,
        spaceAfter=6,
    )
    style_corpo = ParagraphStyle(
        "CorpoChecklist",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#222222"),
    )
    style_item = ParagraphStyle(
        "ItemChecklist",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1A1A1A"),
    )

    elementos = []

    info_empresa = [
        Paragraph(f"<b>{_escapar_xml(empresa_exibicao)}</b>", style_empresa),
        Paragraph("Checklist para Impressão — SST", style_sub),
        Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", style_sub),
    ]

    if img_reader is not None:
        try:
            iw, ih = img_reader.getSize()
            max_w = 4.2 * cm
            max_h = 2.0 * cm
            escala = min(max_w / float(iw), max_h / float(ih), 1.0)
            rl_logo = RLImage(img_reader, width=float(iw) * escala, height=float(ih) * escala)
            tabela_cab = Table([[rl_logo, info_empresa]], colWidths=[4.8 * cm, 13.0 * cm])
        except Exception:
            tabela_cab = Table([[info_empresa]], colWidths=[17.8 * cm])
    else:
        tabela_cab = Table([[info_empresa]], colWidths=[17.8 * cm])

    tabela_cab.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#1B365D")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elementos.append(tabela_cab)
    elementos.append(Spacer(1, 0.4 * cm))

    elementos.append(Paragraph(f"CHECKLIST: {_escapar_xml(titulo_arq)}", style_titulo))

    if desc_arq and desc_arq.strip():
        elementos.append(Paragraph(f"<b>Descrição:</b> {_escapar_xml(desc_arq.strip())}", style_corpo))
        elementos.append(Spacer(1, 0.25 * cm))

    elementos.append(
        Paragraph(
            f"<b>Arquivo base:</b> {_escapar_xml(nome_arq)} &nbsp;|&nbsp; <b>Data:</b> {_escapar_xml(dt_up or '—')}",
            style_sub,
        )
    )
    elementos.append(Spacer(1, 0.4 * cm))

    if itens_extraidos:
        dados_grade = [
            [
                Paragraph("<b>#</b>", style_item),
                Paragraph("<b>Item / Verificação do Checklist</b>", style_item),
                Paragraph("<b>C</b>", style_item),
                Paragraph("<b>NC</b>", style_item),
                Paragraph("<b>N/A</b>", style_item),
                Paragraph("<b>Observações</b>", style_item),
            ]
        ]
        for idx, texto_item in enumerate(itens_extraidos, start=1):
            dados_grade.append(
                [
                    Paragraph(f"{idx:02d}", style_item),
                    Paragraph(_escapar_xml(texto_item), style_item),
                    Paragraph("[  ]", style_item),
                    Paragraph("[  ]", style_item),
                    Paragraph("[  ]", style_item),
                    Paragraph("", style_item),
                ]
            )

        tabela_itens = Table(
            dados_grade,
            colWidths=[1.0 * cm, 8.6 * cm, 0.9 * cm, 1.0 * cm, 1.0 * cm, 4.3 * cm],
            repeatRows=1,
        )
        tabela_itens.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (2, 0), (4, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elementos.append(tabela_itens)
    else:
        elementos.append(
            Paragraph(
                "Não foi possível extrair itens em texto deste arquivo (por exemplo, PDF escaneado apenas como imagem). "
                "Preencha os pontos de inspeção abaixo conforme o modelo enviado:",
                style_corpo,
            )
        )
        elementos.append(Spacer(1, 0.3 * cm))
        dados_vazios = [[Paragraph("<b>#</b>", style_item), Paragraph("<b>Item de Inspeção</b>", style_item), Paragraph("<b>C / NC / N/A</b>", style_item), Paragraph("<b>Observações</b>", style_item)]]
        for idx in range(1, 11):
            dados_vazios.append([Paragraph(f"{idx:02d}", style_item), Paragraph("", style_item), Paragraph("[ ] C  [ ] NC  [ ] N/A", style_item), Paragraph("", style_item)])
        tab_vazia = Table(dados_vazios, colWidths=[1.0 * cm, 8.2 * cm, 3.6 * cm, 5.0 * cm], repeatRows=1)
        tab_vazia.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (2, 0), (2, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tab_vazia)

    elementos.append(Spacer(1, 0.8 * cm))

    assinaturas = Table(
        [
            ["________________________________________", "________________________________________"],
            ["Responsável pela Inspeção / Assinatura", "Validação / Supervisor ou SST"],
        ],
        colWidths=[8.9 * cm, 8.9 * cm],
    )
    assinaturas.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
            ]
        )
    )
    elementos.append(assinaturas)

    doc.build(elementos)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def renderizar_modulo_checklist(db_name, registrar_log_callback=None):
    _garantir_tabela_arquivos_checklist(db_name)

    st.title("Checklists")
    st.markdown("Modelos de checklist disponíveis para impressão (a partir de arquivos PDF e DOCX)")

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
                    ext = _extensao_arquivo(arquivo_up.name) if arquivo_up is not None else ""
                    if not titulo.strip():
                        st.error("Informe o título do checklist.")
                    elif arquivo_up is None:
                        st.error("Selecione um arquivo PDF ou DOCX para enviar.")
                    elif ext not in EXTENSOES_PERMITIDAS:
                        st.error("Formato não permitido. Envie apenas arquivos .PDF ou .DOCX.")
                    else:
                        dados_bytes = arquivo_up.getvalue()
                        empresa_alvo = "" if escopo_empresa.startswith("Todas") else escopo_empresa
                        data_agora = datetime.now().strftime("%d/%m/%Y %H:%M")

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
                                arquivo_up.type or "application/octet-stream",
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
    st.subheader("Checklists para Impressão")

    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    if empresa_especifica:
        cur.execute(
            """
            SELECT id, empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload
            FROM checklist_arquivos
            WHERE TRIM(COALESCE(empresa, '')) = ''
               OR LOWER(TRIM(empresa)) = LOWER(TRIM(?))
            ORDER BY id DESC
            """,
            (empresa_especifica,),
        )
    else:
        cur.execute(
            """
            SELECT id, empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload
            FROM checklist_arquivos
            ORDER BY id DESC
            """
        )
    arquivos = cur.fetchall()
    conn.close()

    if not arquivos:
        st.info("Nenhum arquivo de checklist disponível no momento.")
        return

    for arq_id, emp_arq, titulo_arq, desc_arq, nome_arq, mime_arq, tam_bytes, blob_dados, dt_up in arquivos:
        with st.container(border=True):
            col_info, col_acao = st.columns([4, 1.8])

            with col_info:
                escopo_txt = emp_arq.strip() if emp_arq and emp_arq.strip() else "Todas as empresas"
                st.markdown(f"**{titulo_arq}**")
                if desc_arq and desc_arq.strip():
                    st.write(desc_arq.strip())
                st.caption(
                    f"Arquivo base: `{nome_arq}` • Tamanho: {_formatar_tamanho(tam_bytes)} • Escopo: {escopo_txt} • Enviado em: {dt_up or '—'}"
                )

            with col_acao:
                if TEM_REPORTLAB:
                    pdf_impressao = _gerar_pdf_checklist_com_logo(
                        db_name=db_name,
                        empresa_especifica=empresa_especifica,
                        titulo_arq=titulo_arq,
                        desc_arq=desc_arq or "",
                        nome_arq=nome_arq,
                        dt_up=dt_up or "",
                        blob_dados=blob_dados,
                    )
                    if pdf_impressao:
                        nome_base = os.path.splitext(nome_arq)[0] or "checklist"
                        sufixo = "_empresa" if empresa_especifica else "_geral"
                        st.download_button(
                            label="🖨️ Baixar / Imprimir",
                            data=pdf_impressao,
                            file_name=f"{nome_base}{sufixo}.pdf",
                            mime="application/pdf",
                            key=f"print_checklist_{arq_id}",
                            use_container_width=True,
                        )
                    else:
                        st.warning("ReportLab indisponível para gerar PDF.")

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
