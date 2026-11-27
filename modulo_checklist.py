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


def _gerar_pdf_checklist_com_logo(db_name, empresa_especifica, titulo_arq, desc_arq, nome_arq, dt_up):
    if not TEM_REPORTLAB:
        return None

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    empresa_exibicao = empresa_especifica.strip() if tem_empresa else "Todas as Empresas (Modelo Geral)"
    img_reader = _converter_para_image_reader(_buscar_logo_empresa(db_name, empresa_especifica)) if tem_empresa else None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
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
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#111111"),
        spaceBefore=6,
        spaceAfter=8,
    )
    style_corpo = ParagraphStyle(
        "CorpoChecklist",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#222222"),
    )

    elementos = []

    info_empresa = [
        Paragraph(f"<b>{empresa_exibicao}</b>", style_empresa),
        Paragraph("Documento para Impressão — Modelo de Checklist SST", style_sub),
        Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", style_sub),
    ]

    if img_reader is not None:
        try:
            iw, ih = img_reader.getSize()
            max_w = 4.2 * cm
            max_h = 2.0 * cm
            escala = min(max_w / float(iw), max_h / float(ih), 1.0)
            rl_logo = RLImage(img_reader, width=float(iw) * escala, height=float(ih) * escala)
            tabela_cab = Table([[rl_logo, info_empresa]], colWidths=[4.8 * cm, 12.6 * cm])
        except Exception:
            tabela_cab = Table([[info_empresa]], colWidths=[17.4 * cm])
    else:
        tabela_cab = Table([[info_empresa]], colWidths=[17.4 * cm])

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
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph(f"CHECKLIST: {titulo_arq}", style_titulo))

    desc_limpa = desc_arq.strip() if desc_arq and desc_arq.strip() else "Modelo padronizado para conferência operacional."
    elementos.append(Paragraph(f"<b>Descrição / Orientações:</b><br/>{desc_limpa}", style_corpo))
    elementos.append(Spacer(1, 0.35 * cm))
    elementos.append(Paragraph(f"<b>Arquivo de referência:</b> {nome_arq} &nbsp;|&nbsp; <b>Publicado em:</b> {dt_up or '—'}", style_sub))
    elementos.append(Spacer(1, 0.5 * cm))

    dados_grade = [["Item", "Descrição da Verificação", "C", "NC", "N/A", "Observações"]]
    for i in range(1, 11):
        dados_grade.append([f"{i:02d}", "", "[  ]", "[  ]", "[  ]", ""])

    tabela_itens = Table(
        dados_grade,
        colWidths=[1.2 * cm, 7.2 * cm, 1.0 * cm, 1.1 * cm, 1.1 * cm, 5.8 * cm],
        repeatRows=1,
    )
    tabela_itens.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (4, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
            ]
        )
    )
    elementos.append(tabela_itens)
    elementos.append(Spacer(1, 0.8 * cm))

    assinaturas = Table(
        [
            ["________________________________________", "________________________________________"],
            ["Responsável pela Inspeção / Assinatura", "Validação / Supervisor ou SST"],
        ],
        colWidths=[8.7 * cm, 8.7 * cm],
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
    st.markdown("Modelos de checklist disponíveis para download e impressão (PDF e DOCX)")

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
                    placeholder="Ex.: Checklist de Segurança em Altura / NR-35",
                )
                descricao = st.text_area(
                    "Descrição (opcional)",
                    placeholder="Ex.: Modelo em Word (.docx) ou PDF para preenchimento.",
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
    st.subheader("Arquivos para Download / Impressão")

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
        ext_arq = _extensao_arquivo(nome_arq)
        mime_download = MIME_POR_EXTENSAO.get(ext_arq, mime_arq or "application/octet-stream")

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
                st.download_button(
                    label="⬇️ Baixar Original",
                    data=bytes(blob_dados),
                    file_name=nome_arq,
                    mime=mime_download,
                    key=f"dl_checklist_{arq_id}",
                    use_container_width=True,
                )

                if TEM_REPORT
