import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import os
from PIL import Image

# Função de segurança para senhas
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Configuração da página
st.set_page_config(page_title="Sistema CASSILAB SST", layout="wide")

# Conexão com o banco de dados
def conectar_db():
    return sqlite3.connect('cassilab_gestao.db')

# --- INÍCIO DO CÓDIGO DO SISTEMA ---
# (Aqui entram as funções de criar tabelas e importar planilhas que já tínhamos)

# Lógica de Login e LGPD
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

if not st.session_state['logado']:
    st.title("Sistema Cassilab SST — Acesso Restrito")
    
    aba_login, aba_cadastro = st.tabs(["🔑 Entrar", "📝 Primeiro Acesso (LGPD)"])
    
    with aba_login:
        with st.form("form_login"):
            usuario = st.text_input("Usuário ou CPF")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                # (Lógica de autenticação...)
                st.session_state['logado'] = True
                st.rerun()

    with aba_cadastro:
        st.markdown("### 📝 Termo de Consentimento LGPD")
        st.info("Para sua segurança, ao cadastrar-se, você autoriza o tratamento dos dados estritamente para gestão de SST (Normas Regulamentadoras).")
        
        with st.form("form_cadastro"):
            # ... campos de cadastro ...
            aceite_lgpd = st.checkbox("Declaro que li e aceito que meus dados serão tratados pela Cassilab para fins de SST (LGPD).")
            if st.form_submit_button("Cadastrar com Consentimento"):
                if aceite_lgpd:
                    st.success("Cadastro realizado com sucesso sob conformidade LGPD!")
                else:
                    st.error("Você precisa aceitar os termos LGPD para prosseguir.")

# --- Área do Administrador (Com exclusão LGPD) ---
if st.session_state['logado']:
    # ... código das abas de gestão ...
    
    if menu == "Funcionários":
        st.markdown("---")
        st.markdown("### 🔒 Gestão de Dados (LGPD)")
        cpf_excluir = st.text_input("Digite o CPF do funcionário para exclusão definitiva:")
        if st.button("🗑️ Excluir Colaborador (Direito ao Esquecimento)"):
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM funcionarios WHERE cpf = ?", (cpf_excluir,))
            conn.commit()
            conn.close()
            st.warning("Dados do colaborador removidos do sistema conforme diretrizes LGPD.")