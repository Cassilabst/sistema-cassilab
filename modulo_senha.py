import streamlit as st
import sqlite3

def renderizar_aba_alterar_senha(DB_NAME, nome_usuario):
    st.subheader("🔑 Alterar Minha Senha de Acesso")
    st.markdown("Preencha os campos abaixo para atualizar a sua senha de acesso ao sistema:")
    
    with st.form("form_alterar_senha_usuario"):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        confirma_senha = st.text_input("Confirmar Nova Senha", type="password")
        
        btn_salvar_nova_senha = st.form_submit_button("💾 Salvar Nova Senha", use_container_width=True)
        
        if btn_salvar_nova_senha:
            if not senha_atual or not nova_senha or not confirma_senha:
                st.warning("⚠️ Todos os campos devem ser preenchidos.")
            elif nova_senha != confirma_senha:
                st.error("❌ A nova senha e a confirmação não coincidem.")
            else:
                conn = sqlite3.connect(DB_NAME, timeout=10.0)
                cursor = conn.cursor()
                # Verifica a senha atual do utilizador autenticado
                cursor.execute(
                    "SELECT id, senha FROM usuarios_sistema WHERE nome = ? AND senha = ?",
                    (nome_usuario, senha_atual)
                )
                user_record = cursor.fetchone()
                
                if user_record:
                    cursor.execute(
                        "UPDATE usuarios_sistema SET senha = ? WHERE id = ?",
                        (nova_senha, user_record[0])
                    )
                    conn.commit()
                    conn.close()
                    st.success("✅ Senha alterada com sucesso! Utilize esta nova senha nos próximos acessos.")
                else:
                    conn.close()
                    st.error("❌ A senha atual informada está incorreta.")
