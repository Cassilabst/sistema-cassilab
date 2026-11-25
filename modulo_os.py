import base64
from datetime import datetime
import html
import sqlite3
import pandas as pd
import streamlit as st


def _garantir_tabela_os(db_name):
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            funcionario TEXT NOT NULL,
            cargo TEXT,
            setor TEXT,
            revisao INTEGER DEFAULT 0,
            dt_elab TEXT,
            dt_rev TEXT,
            data_registro TEXT,
            descricao TEXT,
            riscos TEXT,
            epis TEXT,
            orientacoes_gerais TEXT,
            recomendacoes TEXT,
            acidentes TEXT,
            observacoes TEXT,
            logo_base64 TEXT
        )
        """
    )
    cur.execute("PRAGMA table_info(ordens_servico)")
    colunas = [col[1] for col in cur.fetchall()]
    if "orientacoes_gerais" not in colunas:
        cur.execute("ALTER TABLE ordens_servico ADD COLUMN orientacoes_gerais TEXT")

    conn.commit()
    conn.close()


def _buscar_logo_empresa_cadastro(db_name, empresa):
    try:
        conn = sqlite3.connect(db_name, timeout=10.0)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(empresas)")
        colunas = [col[1] for col in cur.fetchall()]
        if "logo_empresa" not in colunas:
            conn.close()
            return ""
        cur.execute(
            """
            SELECT logo_empresa
            FROM empresas
            WHERE LOWER(TRIM(nome_empresa)) = LOWER(TRIM(?))
            LIMIT 1
            """,
            (empresa,),
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0] and str(row[0]).strip():
            return str(row[0]).strip()
    except Exception:
        pass
    return ""


def _proxima_revisao_os(db_name, empresa, funcionario):
    _garantir_tabela_os(db_name)
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(MAX(revisao), -1)
        FROM ordens_servico
        WHERE LOWER(TRIM(empresa)) = LOWER(TRIM(?))
          AND LOWER(TRIM(funcionario)) = LOWER(TRIM(?))
        """,
        (empresa, funcionario),
    )
    max_rev = cur.fetchone()[0]
    conn.close()
    return int(max_rev) + 1


def _salvar_nova_revisao_os(db_name, dados_os):
    _garantir_tabela_os(db_name)
    proxima_rev = _proxima_revisao_os(
        db_name, dados_os["empresa"], dados_os["funcionario"]
    )
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ordens_servico (
            empresa, funcionario, cargo, setor, revisao,
            dt_elab, dt_rev, data_registro,
            descricao, riscos, epis, orientacoes_gerais,
            recomendacoes, acidentes, observacoes,
            logo_base64
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dados_os["empresa"],
            dados_os["funcionario"],
            dados_os["cargo"],
            dados_os["setor"],
            proxima_rev,
            dados_os.get("dt_elab") or data_hoje,
            data_hoje,
            agora_str,
            dados_os["descricao"],
            dados_os["riscos"],
            dados_os["epis"],
            dados_os["orientacoes_gerais"],
            dados_os["recomendacoes"],
            dados_os["acidentes"],
            dados_os["observacoes"],
            dados_os.get("logo", ""),
        ),
    )
    novo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return novo_id, proxima_rev, data_hoje, agora_str


def _excluir_os_por_id(db_name, os_id):
    _garantir_tabela_os(db_name)
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute("DELETE FROM ordens_servico WHERE id = ?", (int(os_id),))
    conn.commit()
    conn.close()


def _listar_historico_empresa_os(db_name, empresa, funcionario=None):
    _garantir_tabela_os(db_name)
    conn = sqlite3.connect(db_name, timeout=10.0)
    if funcionario:
        df_hist = pd.read_sql(
            """
            SELECT id, funcionario, cargo, setor, revisao, dt_elab, dt_rev, data_registro
            FROM ordens_servico
            WHERE LOWER(TRIM(empresa)) = LOWER(TRIM(?))
              AND LOWER(TRIM(funcionario)) = LOWER(TRIM(?))
            ORDER BY revisao DESC, id DESC
            """,
            conn,
            params=(empresa, funcionario),
        )
    else:
        df_hist = pd.read_sql(
            """
            SELECT id, funcionario, cargo, setor, revisao, dt_elab, dt_rev, data_registro
            FROM ordens_servico
            WHERE LOWER(TRIM(empresa)) = LOWER(TRIM(?))
            ORDER BY id DESC
            """,
            conn,
            params=(empresa,),
        )
    conn.close()
    return df_hist


def _buscar_os_por_id(db_name, os_id):
    _garantir_tabela_os(db_name)
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, empresa, funcionario, cargo, setor, revisao,
               dt_elab, dt_rev, data_registro,
               descricao, riscos, epis, orientacoes_gerais,
               recomendacoes, acidentes, observacoes,
               logo_base64
        FROM ordens_servico
        WHERE id = ?
        """,
        (int(os_id),),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "empresa": row[1] or "",
        "funcionario": row[2] or "",
        "cargo": row[3] or "",
        "setor": row[4] or "",
        "revisao": int(row[5] or 0),
        "dt_elab": row[6] or "",
        "dt_rev": row[7] or "",
        "data_registro": row[8] or "",
        "descricao": row[9] or "",
        "riscos": row[10] or "",
        "epis": row[11] or "",
        "orientacoes_gerais": row[12] or "",
        "recomendacoes": row[13] or "",
        "acidentes": row[14] or "",
        "observacoes": row[15] or "",
        "logo": row[16] or "",
    }


def _renderizar_html_os(d):
    rev_num = int(d.get("revisao", 0))
    rev_label = f"Rev. {rev_num:02d}"
    nome_emp_seguro = html.escape(str(d.get("empresa") or "EMPRESA"))
    nome_func_seguro = html.escape(str(d.get("funcionario") or ""))

    if d.get("logo"):
        tag_logo = (
            f'<img src="{d["logo"]}" alt="Logo {nome_emp_seguro}" '
            'style="max-height: 55px; max-width: 180px; object-fit: contain;">'
        )
    else:
        tag_logo = (
            f'<b style="color: #023e8a; font-size: 16px;">{nome_emp_seguro}</b>'
        )

    orientacoes_txt = str(d.get("orientacoes_gerais") or "").strip()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Ordem de Serviço - {nome_func_seguro} ({rev_label})</title>
        <style>
            @page {{
                size: A4;
                margin: 15mm;
            }}
            body {{
                font-family: Arial, sans-serif;
                color: #000;
                background: #fff;
                margin: 0;
                padding: 0;
            }}
            .os-container {{
                border: 2px solid #333;
                padding: 20px;
                width: 100%;
                box-sizing: border-box;
                background: #fff;
            }}
            .header-tabela {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            .header-tabela td {{
                border: 1px solid #999;
                padding: 8px;
                background: #f8f9fa;
                font-size: 13px;
            }}
            .secao-titulo {{
                background: #e9ecef;
                padding: 5px;
                margin: 0 0 5px 0;
                font-size: 13px;
                font-weight: bold;
            }}
            .secao-texto {{
                white-space: pre-wrap;
                font-size: 12px;
                margin: 0 0 10px 0;
                padding: 4px;
            }}
            .assinaturas {{
                display: flex;
                justify-content: space-between;
                margin-top: 40px;
                text-align: center;
            }}
            .linha-assinatura {{
                width: 45%;
                border-top: 1px solid #000;
                padding-top: 5px;
                font-size: 12px;
            }}
            @media print {{
                body {{ background: #fff; }}
                .os-container {{ border: none; padding: 0; width: 100%; }}
                .nao-imprimir {{ display: none !important; }}
            }}
        </style>
    </head>
    <body>
        <div style="text-align: center; margin-bottom: 20px;" class="nao-imprimir">
            <button onclick="window.print();" style="background: #023e8a; color: #fff; border: none; padding: 12px 25px; font-size: 16px; border-radius: 6px; cursor: pointer; font-weight: bold;">
                🖨️ Imprimir / Salvar em PDF agora (Formato A4)
            </button>
        </div>

        <div class="os-container">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px;">
                <div>
                    {tag_logo}
                </div>
                <div style="text-align: right;">
                    <h2 style="margin: 0; font-size: 14px; background: #333; color: #fff; padding: 4px 10px;">ORDEM DE SERVIÇO (O.S.) — {rev_label}</h2>
                    <small style="font-size: 11px;">Elaboração: {d['dt_elab']} | Revisão: {d['dt_rev']} | {rev_label}</small>
                </div>
            </div>

            <p style="font-size: 14px; margin-bottom: 10px;"><b>Empresa:</b> {nome_emp_seguro}</p>
            
            <table class="header-tabela">
                <tr>
                    <td><b>Nome do Colaborador:</b> {nome_func_seguro}</td>
                    <td><b>Cargo:</b> {html.escape(str(d.get('cargo') or ''))}</td>
                    <td><b>Setor:</b> {html.escape(str(d.get('setor') or ''))}</td>
                </tr>
            </table>

            <div class="secao-titulo">1. Descrição da Função / Atividades</div>
            <div class="secao-texto">{html.escape(str(d.get('descricao') or ''))}</div>

            <div class="secao-titulo">2. Agentes Associados às Atividades (Riscos)</div>
            <div class="secao-texto">{html.escape(str(d.get('riscos') or ''))}</div>

            <div class="secao-titulo">3. EPI's de Uso Obrigatório</div>
            <div class="secao-texto">{html.escape(str(d.get('epis') or ''))}</div>

            <div class="secao-titulo">4. Orientações Gerais e Medidas Preventivas</div>
            <div class="secao-texto">{html.escape(orientacoes_txt)}</div>

            <div class="secao-titulo">5. Recomendações</div>
            <div class="secao-texto">{html.escape(str(d.get('recomendacoes') or ''))}</div>

            <div class="secao-titulo">6. Procedimentos em Caso de Acidentes</div>
            <div class="secao-texto">{html.escape(str(d.get('acidentes') or ''))}</div>

            <div class="secao-titulo">7. Observações e Disposições</div>
            <div class="secao-texto" style="margin-bottom: 20px;">{html.escape(str(d.get('observacoes') or ''))}</div>

            <div class="assinaturas">
                <div class="linha-assinatura">
                    <b>Assinatura do Colaborador</b><br><small>Data: ____/____/________</small>
                </div>
                <div class="linha-assinatura">
                    <b>Responsável Técnico / Emissor</b><br><small>Data: ____/____/________</small>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def _bloco_historico_os(df_hist, titulo_secao, key_prefix, db_name, registrar_log_callback=None):
    st.markdown("---")
    st.markdown(f"### {titulo_secao}")
    if df_hist.empty:
        st.caption("Nenhuma Ordem de Serviço emitida e salva ainda para este filtro.")
        return

    df_exibir = df_hist.copy()
    df_exibir["Revisão"] = df_exibir["revisao"].apply(lambda r: f"Rev. {int(r):02d}")
    df_exibir = df_exibir[
        ["id", "funcionario", "Revisão", "dt_elab", "dt_rev", "data_registro", "cargo", "setor"]
    ].rename(
        columns={
            "id": "ID",
            "funcionario": "Colaborador",
            "dt_elab": "Elaboração",
            "dt_rev": "Data Revisão",
            "data_registro": "Salvo em (Data/Hora)",
            "cargo": "Cargo",
            "setor": "Setor",
        }
    )
    st.dataframe(df_exibir, use_container_width=True, hide_index=True)

    opcoes_hist = {
        f"{row['funcionario']} — Rev. {int(row['revisao']):02d} | Revisão: {row['dt_rev']} ({row['data_registro']}) [ID {int(row['id'])}]": int(row["id"])
        for _, row in df_hist.iterrows()
    }
    escolha_hist = st.selectbox(
        "Escolha uma Ordem de Serviço salva",
        list(opcoes_hist.keys()),
        key=f"sel_hist_{key_prefix}",
    )
    os_id_sel = opcoes_hist[escolha_hist]

    col_b1, col_b2, col_b3 = st.columns(3)
    with col_b1:
        if st.button("👁️ Visualizar / Imprimir", key=f"btn_ver_hist_{
