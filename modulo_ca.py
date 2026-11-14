import streamlit as st
import sqlite3
import pandas as pd

def inicializar_banco_ca(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS base_ca_oficial (
            ca INTEGER PRIMARY KEY,
            validade TEXT,
            equipamento TEXT,
            fabricante TEXT
        )
    ''')
    conn.commit()
    conn.close()

def consultar_dados_ca(db_name, numero_ca):
    try:
        inicializar_banco_ca(db_name)
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT ca, validade, equipamento, fabricante FROM base_ca_oficial WHERE ca = ?", (int(numero_ca),))
        resultado = cursor.fetchone()
        conn.close()
        return resultado
    except Exception:
        return None

def renderizar_modulo_ca(db_name, is_admin):
    st.subheader("Gerenciamento e Consulta de CAs (Oficial MTE)")
    inicializar_banco_ca(db_name)
    
    # Contar total de registros na base local
    try:
        conn = sqlite3.connect(db_name)
        df_count = pd.read_sql("SELECT COUNT(*) as total FROM base_ca_oficial", conn)
        conn.close()
        total_registros = df_count['total'].iloc[0]
    except Exception:
        total_registros = 0
        
    st.info(f"📊 Registros oficiais de CA carregados no banco local: **{total_registros}**")
    
    if is_admin:
        st.markdown("### Atualizar Base de Dados via CSV")
        st.write("Faça o upload do arquivo CSV oficial obtido no portal de dados abertos do MTE.")
        
        # O campo de upload que estava a faltar na interface!
        arquivo_submetido = st.file_uploader("Selecione o arquivo CSV do MTE", type=["csv", "txt"])
        
        if arquivo_submetido is not None:
            if st.button("Processar e Importar Base de CAs"):
                with st.spinner("Importando dados oficiais para o banco... Aguarde."):
                    try:
                        # Tenta ler o CSV lidando com diferentes codificações comuns do governo
                        try:
                            df = pd.read_csv(arquivo_submetido, sep=';', encoding='utf-8', low_memory=False)
                        except UnicodeDecodeError:
                            arquivo_submetido.seek(0)
                            df = pd.read_csv(arquivo_submetido, sep=';', encoding='latin1', low_memory=False)
                        
                        colunas_lower = {str(c).lower().strip(): c for c in df.columns}
                        
                        # Identificação flexível das colunas do MTE
                        col_ca = next((colunas_lower[c] for c in colunas_lower if 'ca' in c or 'certificado' in c), df.columns[0])
                        col_val = next((colunas_lower[c] for c in colunas_lower if 'validade' in c), df.columns[1] if len(df.columns) > 1 else None)
                        col_eq = next((colunas_lower[c] for c in colunas_lower if 'equipamento' in c or 'descricao' in c), None)
                        col_fab = next((colunas_lower[c] for c in colunas_lower if 'fabricante' in c or 'empresa' in c), None)
                        
                        conn = sqlite3.connect(db_name)
                        cursor = conn.cursor()
                        
                        importados = 0
                        for _, row in df.iterrows():
                            try:
                                val_ca = int(row[col_ca])
                                val_data = str(row[col_val]).strip() if col_val else ""
                                val_eq = str(row[col_eq]).strip() if col_eq else ""
                                val_fab = str(row[col_fab]).strip() if col_fab else ""
                                
                                cursor.execute('''
                                    INSERT OR REPLACE INTO base_ca_oficial (ca, validade, equipamento, fabricante)
                                    VALUES (?, ?, ?, ?)
                                ''', (val_ca, val_data, val_eq, val_fab))
                                importados += 1
                            except Exception:
                                continue
                                
                        conn.commit()
                        conn.close()
                        st.success(f"Sucesso! {importados} registros de CA foram importados/atualizados.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao processar o arquivo CSV: {e}")
    else:
        st.warning("Apenas administradores podem atualizar a base de dados oficial de CAs.")
        
    st.markdown("---")
    st.markdown("### Consulta Rápida de CA")
    busca_ca = st.text_input("Digite o número do CA para testar a consulta:")
    if busca_ca:
        res = consultar_dados_ca(db_name, busca_ca)
        if res:
            st.success(f"**CA:** {res[0]} | **Validade:** {res[1]} | **Equipamento:** {res[2]} | **Fabricante:** {res[3]}")
        else:
            st.error("CA não encontrado na base oficial local.")
