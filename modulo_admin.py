import streamlit as st
import sqlite3
import pandas as pd
import os

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
        col_h1, col_h2 = st.columns([0.8, 0.2])
        with col_h1: st.title("🛠️ Painel Administrativo e Configurações")
        with col_h2:
            st.write("")
            if st.button("🔄 Atualizar Aba", key="btn_atualizar_admin"): st.rerun()

        st.subheader("📧 Configuração de E-mail (Gmail - Senha de App)")
        st.markdown("Insira o seu e-mail do Gmail e a **Senha de Aplicativo** gerada na sua conta Google para habilitar o envio de e-mails.")
        
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_cfg_mail = pd.read_sql("SELECT email, senha_app FROM configuracoes_email LIMIT 1", conn)
        conn.close()
        
        email_salvo = df_cfg_mail.iloc[0]["email"] if not df_cfg_mail.empty and pd.notna(df_cfg_mail.iloc[0]["email"]) else ""
        senha_salva = df_cfg_mail.iloc[0]["senha_app"] if not df_cfg_mail.empty and pd.notna(df_cfg_mail.iloc[0]["senha_app"]) else ""
        
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
        df_alertas_hist = pd.read_sql("SELECT id, empresa, tipo_item, item_id, data_vencimento, data_envio FROM alertas_enviados ORDER BY id DESC LIMIT 100", conn)
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
        df_users = pd.read_sql("SELECT id, nome, cpf, empresa, email, celular, status, nivel_permissao FROM usuarios_sistema", conn)
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
                    "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    "Nível de Acesso": st.column_config.SelectboxColumn(
                        "Nível de Acesso",
                        options=["Somente Visualizar", "Lançar", "Editar", "Fazer Tudo"],
                        required=True
                    )
                }
            )
            
            curr_u = edit_users[edit_users["Selecionar"] == True]["_id_banco"].tolist()
            new_u = [uid for uid in curr_u if uid != st.session_state["sel_id_user"]]
            if new_u:
                st.session_state["sel_id_user"] = new_u[-1]
                st.rerun()
            elif not curr_u and st.session_state["sel_id_user"] is not None:
                st.session_state["sel_id_user"] = None
                st.rerun()
                
            sel_users = edit_users[edit_users["Selecionar"] == True]
            col_salvar_niveis, col_esp = st.columns([1, 1])
            
            if col_salvar_niveis.button("💾 Salvar Alterações de Níveis de Acesso", use_container_width=True):
                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                cursor = conn.cursor()
                for _, row in edit_users.iterrows():
                    u_id = row.get("_id_banco")
                    novo_nivel = row.get("Nível de Acesso")
                    if pd.notna(u_id) and pd.notna(novo_nivel):
                        cursor.execute("UPDATE usuarios_sistema SET nivel_permissao = ? WHERE id = ?", (str(novo_nivel), int(u_id)))
                conn.commit()
                conn.close()
                if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                st.session_state["sel_id_user"] = None
                st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                registrar_log_func("Administrador", "Todas", "Atualização de níveis de permissão de usuários")
                st.rerun()
                
            st.markdown("")
            cu1, cu2, cu3 = st.columns(3)
            if cu1.button("✅ Aprovar Acesso Selecionado", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    conn.execute("UPDATE usuarios_sistema SET status = 'Ativo' WHERE id = ?", (uid,))
                    conn.commit()
                    conn.close()
                    if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                    st.session_state["sel_id_user"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log_func("Administrador", "Todas", f"Aprovou acesso do usuário ID {uid}")
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")
                    
            if cu2.button("🚫 Bloquear Acesso Selecionado", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    conn = sqlite3.connect(DB_NAME, timeout=10.0)
                    conn.execute("UPDATE usuarios_sistema SET status = 'Bloqueado' WHERE id = ?", (uid,))
                    conn.commit()
                    conn.close()
                    if "edit_users_acesso" in st.session_state: del st.session_state["edit_users_acesso"]
                    st.session_state["sel_id_user"] = None
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log_func("Administrador", "Todas", f"Bloqueou acesso do usuário ID {uid}")
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")
                    
            if cu3.button("🗑️ Excluir Usuário", use_container_width=True):
                if len(sel_users) == 1:
                    uid = int(sel_users.iloc[0]["_id_banco"])
                    st.session_state["modal_excluir_ativo"] = True
                    st.session_state["modal_excluir_tabela"] = "usuarios_sistema"
                    st.session_state["modal_excluir_id"] = uid
                    st.session_state["modal_excluir_editor_key"] = "edit_users_acesso"
                    st.session_state["sel_id_user"] = None
                    st.rerun()
                else:
                    st.warning("Selecione um usuário marcando o quadradinho.")
        else:
            st.info("Nenhum usuário cadastrado pendente.")

        st.markdown("---")
        st.subheader("📋 Histórico de Logs e Acessos ao Sistema")
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_logs = pd.read_sql("SELECT data_hora, usuario, empresa, acao FROM logs_sistema ORDER BY id DESC LIMIT 100", conn)
        conn.close()
        
        if not df_logs.empty:
            df_logs_exib = df_logs.rename(columns={"data_hora": "Data / Hora", "usuario": "Nome do Usuário", "empresa": "Empresa", "acao": "Ação / Evento"})
            df_logs_exib = adicionar_numeracao_func(df_logs_exib)
            st.dataframe(df_logs_exib, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum log registrado até o momento.")

        st.markdown("---")
        st.subheader("💾 Backup do Banco de Dados")
        col_bk1, col_bk2 = st.columns(2)
        with col_bk1:
            st.markdown("##### Baixar Banco Atual (.db)")
            with open(DB_NAME, "rb") as f:
                st.download_button("📥 Baixar Backup Atual", f, file_name="cassilab_gestao.db", mime="application/octet-stream")
        with col_bk2:
            st.markdown("##### Backups Automáticos Salvos na Pasta")
            backup_dir = "backups"
            if os.path.exists(backup_dir):
                arquivos_backup = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")], reverse=True)
                if arquivos_backup:
                    arq_sel = st.selectbox("Selecione o backup automático:", arquivos_backup)
                    if arq_sel:
                        caminho_arq = os.path.join(backup_dir, arq_sel)
                        with open(caminho_arq, "rb") as fb:
                            st.download_button(f"📥 Baixar {arq_sel}", fb, file_name=arq_sel, mime="application/octet-stream")
                else:
                    st.info("Nenhum backup automático na pasta ainda.")
            else:
                st.info("Pasta de backups será criada automaticamente.")