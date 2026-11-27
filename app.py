import base64
import io
import os
import sqlite3
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

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

try:
    from pypdf import PdfReader, PdfWriter
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False


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
    """Cria uma página PDF apenas com a faixa de cabeçalho (logo + nome da empresa) no topo."""
    if not TEM_REPORTLAB:
        return None

    buf = io.BytesIO()
    from reportlab.pdfgen import canvas as rl_canvas
    c = rl_canvas.Canvas(buf, pagesize=(largura_pag, altura_pag))

    tem_empresa = not _eh_valor_todas(empresa_especifica)
    nome_exib = empresa_especifica.strip() if tem_empresa else "Todas as Empresas"

    margem_x = 36
    topo_y = altura_pag - 28
    altura_faixa = 54

    # Fundo branco no topo para cobrir eventual cabeçalho antigo
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


def _preparar_pdf_para_impressao(db_name, empresa_especifica, nome_arq, blob_dados):
    """
    Para PDF: mantém o arquivo original enviado e, quando há empresa específica,
    aplica a logo + nome da empresa no cabeçalho da 1ª página (se pypdf estiver disponível).
    Para outros arquivos: retorna os bytes originais.
    """
    raw = bytes(blob_dados)
    ext = _extensao_arquivo(nome_arq)
    if ext != "pdf" or not TEM_PYPDF:
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


def _renderizar_visualizador_html_impressao(titulo_arq, empresa_especifica, nome_arq, pdf_bytes, key_suffix):
    """Renderiza visualização com botão Imprimir / Baixar (HTML + PDF embutido)."""
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    emp_txt = empresa_especifica.strip() if not _eh_valor_todas(empresa_especifica) else "Todas as Empresas"

    html_code = f"""
    <div style="border:1px solid #d0d7de;border-radius:8px;padding:12px;background:#ffffff;font-family:Arial,sans-serif;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
            <div>
                <strong style="font-size:15px;color:#1B365D;">{titulo_arq}</strong><br/>
                <span style="font-size:12px;color:#57606a;">Empresa: {emp_txt} • Arquivo: {nome_arq}</span>
            </div>
            <div style="display:flex;gap:8px;">
                <button onclick="imprimirFrame_{key_suffix}()" style="background:#1B365D;color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-weight:bold;">
                    🖨️ Imprimir / Salvar PDF
                </button>
                <a download="{nome_arq}" href="data:application/pdf;base64,{b64_pdf}" style="background:#f6f8fa;color:#24292f;border:1px solid #d0d7de;padding:8px 14px;border-radius:6px;text-decoration:none;font-weight:bold;">
                    ⬇️ Baixar Arquivo
                </a>
            </div>
        </div>
        <iframe id="pdfFrame_{key_suffix}" src="data:application/pdf;base64,{b64_pdf}" width="100%" height="520px" style="border:1px solid #e1e4e8;border-radius:6px;"></iframe>
    </div>
    <script>
        function imprimirFrame_{key_suffix}() {{
            var frame = document.getElementById("pdfFrame_{key_suffix}");
            if (frame && frame.contentWindow) {{
                frame.contentWindow.focus();
                frame.contentWindow.print();
            }} else {{
                window.print();
            }}
        }}
    </script>
    """
    components.html(html_code, height=600, scrolling=False)


def renderizar_modulo_checklist(db_name, registrar_log_callback=None):
    try:
        _garantir_tabela_arquivos_checklist(db_name)

        st.title("Checklists")
        st.markdown("Checklists cadastrados para visualização, download e impressão")

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
            ext_arq = _extensao_arquivo(nome_arq)
            mime_download = MIME_POR_EXTENSAO.get(ext_arq, mime_arq or "application/octet-stream")
            arquivo_preparado = _preparar_pdf_para_impressao(db_name, empresa_especifica, nome_arq, blob_dados)

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
                        label="⬇️ Baixar / Imprimir",
                        data=arquivo_preparado,
                        file_name=nome_arq,
                        mime=mime_download,
                        key=f"dl_print_{arq_id}",
                        use_container_width=True,
                    )

                    if ext_arq == "pdf":
                        esta_aberto = st.session_state[item_aberto_key] == arq_id
                        btn_txt = "🔼 Fechar Visualização" if esta_aberto else "👁️ Visualizar / Imprimir"
                        if st.button(btn_txt, key=f"view_html_{arq_id}", use_container_width=True):
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

            if ext_arq == "pdf" and st.session_state[item_aberto_key] == arq_id:
                _renderizar_visualizador_html_impressao(
                    titulo_arq=titulo_arq,
                    empresa_especifica=empresa_especifica,
                    nome_arq=nome_arq,
                    pdf_bytes=arquivo_preparado,
                    key_suffix=str(arq_id),
                )
    except Exception as erro_checklist:
        st.error(f"Erro ao renderizar o módulo Checklists: {erro_checklist}")
        st.exception(erro_checklist)
