import sqlite3
import pandas as pd

# Nome exato do arquivo CSV que você baixou
csv_file = 'RelatorioCA_20261113_223822.csv' 
db_file = 'cassilab_gestao.db'

print("Lendo o arquivo CSV do MTE (isso pode levar alguns segundos)...")
try:
    df = pd.read_csv(csv_file, sep=';', encoding='utf-8', low_memory=False)
except UnicodeDecodeError:
    df = pd.read_csv(csv_file, sep=';', encoding='latin1', low_memory=False)

print(f"Total de linhas no CSV: {len(df)}")
colunas_lower = {str(c).lower().strip(): c for c in df.columns}

col_ca = next((colunas_lower[c] for c in colunas_lower if 'ca' in c or 'certificado' in c), df.columns[0])
col_val = next((colunas_lower[c] for c in colunas_lower if 'validade' in c), df.columns[1] if len(df.columns) > 1 else None)
col_eq = next((colunas_lower[c] for c in colunas_lower if 'equipamento' in c or 'descricao' in c), None)
col_fab = next((colunas_lower[c] for c in colunas_lower if 'fabricante' in c or 'empresa' in c), None)

print("Gravando os dados organizados no banco SQLite local...")
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS base_ca_oficial (
        ca INTEGER PRIMARY KEY,
        validade TEXT,
        equipamento TEXT,
        fabricante TEXT
    )
''')

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
print(f"Sucesso! {importados} CAs oficiais foram importados para o banco de dados com sucesso.")