# ... (restante do seu menu na barra lateral)

    st.markdown("---")
    
    # --- ÁREA DISCRETA DE BACKUP (APENAS PARA O ADMIN) ---
    if tipo_usuario == "Admin":
        with st.expander("⚙️ Administração"):
            if os.path.exists('cassilab_gestao.db'):
                with open('cassilab_gestao.db', 'rb') as f:
                    st.download_button(
                        label="📥 Baixar Backup",
                        data=f,
                        file_name=f"backup_cassilab_{datetime.datetime.now().strftime('%Y%m%d')}.db",
                        mime="application/octet-stream"
                    )
            else:
                st.warning("Banco de dados não encontrado.")
    
    # Botão de sair
    if st.button("🚪 Sair do Sistema"):
        st.session_state['logado'] = False
        st.rerun()