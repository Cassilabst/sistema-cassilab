import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

def renderizar_aba_admin(
    DB_NAME,
    is_admin,
    enviar_email_smtp_func,
    adicionar_numeracao_func,
    registrar_log_func
):
    if not is_admin:
        st.warning("🔒 Área exclusiva para o Administrador.")
    else:
        # Garante a criação automática das tabelas essenciais para evitar erros
        conn_init = sqlite3.connect(DB_NAME, timeout=10.0)
        cursor_init = conn_init.cursor()
        cursor_init.execute('''
            CREATE TABLE IF NOT EXISTS configuracoes_email (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                senha_app TEXT
            )
        ''')
        cursor_init.execute('''
            CREATE TABLE IF NOT EXISTS usuarios_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                cpf TEXT,
                empresa TEXT,
                email TEXT,
                celular TEXT,
                senha TEXT,
                status TEXT,
                nivel_permissao TEXT
            )
        ''')
        conn_init.commit()
        conn_init.close()

        col_h1, col_h2 = st.columns([0.8, 0.2])
        with col_h1: st.title("🛠️ Painel Administrativo e Configurações")
        with col_h2:
            st.write("")
            if st.button("🔄 Atualizar Aba", key="btn_atualizar_admin"): st.rerun()

        st.subheader("📧 Configuração de E-mail (Gmail - Senha de App)")
        st.markdown("Insira o seu e-mail do Gmail e a **Senha de Aplicativo** gerada na sua conta Google para habilitar o envio de e-mails.")
        
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
            df_cfg_mail = pd.read_sql("SELECT email, senha_app FROM configuracoes_email LIMIT 1", conn)
        except Exception:
            df_cfg_mail = pd.DataFrame()
        conn.close()
        
        val_email = df_cfg_mail.iloc[0]["email"] if not df_cfg_mail.empty and "email" in df_cfg_mail.columns and pd.notna(df_cfg_mail.iloc[0]["email"]) else ""
        email_salvo = str(val_email) if val_email is not None and str(val_email).lower() != "nan" else ""

        val_senha = df_cfg_mail.iloc[0]["senha_app"] if not df_cfg_mail.empty and "senha_app" in df_cfg_mail.columns and pd.notna(df_cfg_mail.iloc[0]["senha_app"]) else ""
        senha_salva = str(val_senha) if val_senha is not None and str(val_senha).lower() != "nan" else ""
        
        with st.form("form_config_email"):
            c_em1, c_em2 = st.columns(2)
            input_email_remetente = c_em1.text_input("E-mail do Remetente (Gmail)", value=email_salvo)
            input_senha_app = c_em2.text_input("Senha de Aplicativo (16 dígitos)", value=senha_salva, type="password")
            btn_salvar_config_email = c_em1.form_submit_button("💾 Salvar Configurações de E-mail", use_container_width=True)
            
            if btn_salvar_config_email:
                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM configuracoes_email")
                cursor.execute("INSERT INTO configuracoes_email (email, senha_app) VALUES (?, ?)", (input_email_remetente.strip(), input_senha_app.strip()))
                conn.commit()
                conn.close()
                st.session_state["msg_sucesso"] = "✅ Configurações de e-mail salvas com sucesso!"
                registrar_log_func("Administrador", "Todas", "Atualizou configurações de e-mail SMTP")
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Histórico de Alertas Enviados (Controle Anti-Duplicidade)")
        st.markdown("Aqui você pode visualizar diretamente os registros de itens que já foram notificados por e-mail para evitar envios duplicados:")
        
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
            df_alertas_hist = pd.read_sql("SELECT id, empresa, tipo_item, item_id, data_vencimento, data_envio FROM alertas_enviados ORDER BY id DESC LIMIT 100", conn)
        except Exception:
            df_alertas_hist = pd.DataFrame()
        conn.close()
        
        if not df_alertas_hist.empty:
            df_alertas_exib = df_alertas_hist.rename(columns={
                "id": "ID", "empresa": "Empresa", "tipo_item": "Tipo de Item",
                "item_id": "ID do Item", "data_vencimento": "Data de Vencimento", "data_envio": "Data/Hora do Envio"
            })
            df_alertas_exib = adicionar_numeracao_func(df_alertas_exib)
            st.dataframe(df_alertas_exib, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum alerta enviado registrado no histórico ainda.")

        st.markdown("---")
        st.subheader("👥 Controle de Acessos e Níveis de Permissão")
        st.markdown("Defina o nível de permissão de cada usuário diretamente na tabela abaixo e clique em salvar.")
        
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        try:
            df_users = pd.read_sql("SELECT id, nome, cpf, empresa, email, celular, status, nivel_permissao FROM usuarios_sistema", conn)
        except Exception:
            df_users = pd.DataFrame()
        conn.close()

        if not df_users.empty:
            if "sel_id_user" not in st.session_state: st.session_state["sel_id_user"] = None
            df_users["_id_banco"] = df_users["id"]
            df_users["Selecionar"] = df_users["_id_banco"] == st.session_state["sel_id_user"]
            df_users_exib = df_users[["Selecionar", "_id_banco", "nome", "cpf", "empresa", "email", "celular", "nivel_permissao", "status"]].rename(columns={
                "nome": "Nome", "cpf": "CPF", "empresa": "Empresa", "email": "E-mail", "celular": "Celular", "nivel_permissao": "Nível de Acesso", "status": "Status"
            })
            df_users_exib = adicionar_numeracao_func(df_users_exib)
            
            edit_users = st.data_editor(
                df_users_exib,
                hide_index=True,
                num_rows="fixed",
                key="edit_users_acesso",
                use_container_width=True,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                    "_id_banco": None,
                    "Nº": st.column_config.NumberColumn
