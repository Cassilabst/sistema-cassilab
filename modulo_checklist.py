import os
import sqlite3
from datetime import datetime
import streamlit as st


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


def renderizar_modulo_checklist(db_name, registrar_log_callback=None):
    _garantir_tabela_arquivos_checklist(db_name)

    st.title("Checklists")
    st.markdown("Arquivos e modelos de checklist disponíveis para download (PDF e DOCX)")

    empresa_global = str(st.session_state.get("empresa_global", "")).strip()
    emp_ativa = (
        empresa_global
        if empresa_global and empresa_global.lower() not in ("todas", "todas as empresas")
        else ""
    )

    if emp_ativa:
        st.caption(f"Empresa ativa no menu: **{emp_ativa}**")

    admin_mode = _eh_admin()

    # --- ÁREA DO ADMINISTRADOR: ENVIAR NOVOS ARQUIVOS ---
    if admin_mode:
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
                escopo_empresa = st.selectbox(
                    "Disponível para",
                    ["Todas as empresas (Geral)"] + ([emp_ativa] if emp_ativa else []),
                )
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
    st.subheader("Arquivos para Download")

    # --- CONSULTA DOS ARQUIVOS DISPONÍVEIS ---
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    if emp_ativa:
        cur.execute(
            """
            SELECT id, empresa, titulo, descricao, nome_arquivo, tipo_mime, tamanho_bytes, conteudo_arquivo, data_upload
            FROM checklist_arquivos
            WHERE TRIM(COALESCE(empresa, '')) = ''
               OR LOWER(TRIM(empresa)) = LOWER(TRIM(?))
            ORDER BY id DESC
            """,
            (emp_ativa,),
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
            col_info, col_acao = st.columns([4, 1.5])

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
                    label="⬇️ Baixar",
                    data=bytes(blob_dados),
                    file_name=nome_arq,
                    mime=mime_download,
                    key=f"dl_checklist_{arq_id}",
                    use_container_width=True,
                )
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
