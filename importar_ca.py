import sqlite3
import pandas as pd

csv_file = 'RelatorioCA_20261113_223822.csv'
db_file = 'cassilab_sst.db'

print("A ler o arquivo CSV do MTE...")
try:
    df = pd.read_csv(csv_file, sep=';', encoding='utf-8', low_memory=False)
except UnicodeDecodeError:
    df = pd.read_csv(csv_file, sep=';', encoding='latin1', low_memory=False)

print(f"Total de linhas no CSV: {len(df)}")
df.columns = [str(c).strip().lower() for c in df.columns]

col_ca = next((c for c in df.columns if 'ca' in c or 'certificado' in c), df.columns[0])
col_val = next((c for c in df.columns if 'validade' in c), df.columns[1] if len(df.columns) > 1 else None)
col_eq = next((c for c in df.columns if 'equipamento' in c or 'descricao' in c), None)
col_fab = next((c for c in df.columns if 'fabricante' in c or 'empresa' in c), None)

print("A gravar os dados no banco SQLite (cassilab_sst.db)...")
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS base_ca_oficial;")
cursor.execute('''
    CREATE TABLE base_ca_oficial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ca TEXT UNIQUE,
        equipamento TEXT,
        descricao TEXT,
        validade TEXT,
        fabricante TEXT
    )
''')

importados = 0
for _, row in df.iterrows():
    try:
        val_ca = str(row[col_ca]).strip()
        if not val_ca or val_ca.lower() == 'nan':
            continue
        val_data = str(row[col_val]).strip() if col_val and pd.notna(row[col_val]) else ""
        val_eq = str(row[col_eq]).strip() if col_eq and pd.notna(row[col_eq]) else ""
        val_fab = str(row[col_fab]).strip() if col_fab and pd.notna(row[col_fab]) else ""
        
        cursor.execute('''
            INSERT OR IGNORE INTO base_ca_oficial (ca, equipamento, descricao, validade, fabricante)
            VALUES (?, ?, ?, ?, ?)
        ''', (val_ca, val_eq, "", val_data, val_fab))
        importados += 1
    except Exception:
        continue

conn.commit()
conn.close()
print(f"Sucesso! {importados} CAs oficiais importados para {db_file}.")