import streamlit as st
import pandas as pd
import sqlite3 as sqlite_original

def init_db_ca(db_name):
    conn = sqlite_original.connect(db_name, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS base_ca_oficial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ca TEXT UNIQUE,
            equipamento TEXT,
            descricao TEXT,
            validade TEXT,
            fabricante TEXT
        );
    """)
    conn.commit()
    conn.close()

def consultar_dados_ca(db_name, numero_ca):
    """Função utilitária para buscar dados do CA de forma programática."""
    if not numero_ca:
        return None
    conn = sqlite_original.connect(db_name, timeout=10.0)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT equipamento, validade, fabricante FROM base_ca_oficial WHERE ca = ?", (str(numero_ca).strip(),))
        res = cursor.fetchone()
        conn.close()
        return res
    except:
        conn.close()
        return None

def renderizar_modulo_ca(db_name, is_admin):
    init_db_ca(db_name)
    
    st.markdown("### 🛡️ Gestão e Consulta de CAs Oficiais (MTE)")
    st.markdown("Consulte os Certificados de Aprovação oficiais ou atualize a base de dados do sistema.")

    # 1. Área de Atualização da Base (Exclusivo para Administradores)
    if is_admin:
        with st.expander("📥 Importar / Atualizar Base de CAs (Área Administrativa)"):
            st.markdown("Faça o upload do arquivo CSV contendo os dados abertos de CAs do Ministério do Trabalho.")
            arquivo_csv = st.file_uploader("Selecionar Arquivo CSV de CAs", type=["csv"], key="upload_csv_ca")
            if arquivo_csv is not None:
                if st.button("Processar e Atualizar Base Local", key="btn_processar_csv_ca"):
                    try:
                        # Lê o CSV usando pandas (detecta separador automaticamente)
                        df_upload = pd.read_csv(arquivo_csv, sep=None, engine='python', dtype=str)
                        
                        # Limpa nomes das colunas para evitar erros de espaços
                        df_upload.columns = [str(c).strip().lower() for c in df_upload.columns]
                        
                        conn = sqlite_original.connect(db_name, timeout=10.0)
                        df_upload.to_sql("base_ca_oficial", conn, if_exists="replace", index=False)
                        conn.commit()
                        conn.close()
                        
                        st.success("✅ Base de CAs atualizada e salva com sucesso no banco de dados!")
                    except Exception as e:
                        st.error(f"❌ Erro ao processar o arquivo: {e}")

    st.markdown("---")

    col_s1, col_s2 = st.columns([2, 1])
    ca_pesquisa = col_s1.text_input("🔍 Digite o número do CA para pesquisar na base oficial:", key="input_pesquisa_ca_geral")
    
    if col_s2.write("") or col_s2.button("Consultar CA", use_container_width=True, key="btn_exec_pesquisa_ca_geral"):
        if ca_pesquisa.strip():
            conn = sqlite_original.connect(db_name, timeout=10.0)
            try:
                df_res = pd.read_sql("SELECT * FROM base_ca_oficial WHERE ca LIKE ?", conn, params=(f"%{ca_pesquisa.strip()}%",))
            except:
                df_res = pd.DataFrame()
            conn.close()
            
            if not df_res.empty:
                st.success(f"✅ Encontrado(s) {len(df_res)} registro(s):")
                st.dataframe(df_res, use_container_width=True)
            else:
                st.warning("⚠️ Nenhum CA encontrado com esse número na base local.")
        else:
            st.error("⚠️ Por favor, digite um número de CA para pesquisar.")