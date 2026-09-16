import streamlit as st
import sqlite3
import pandas as pd
import streamlit.components.v1 as components

def obter_cnpj_empresa(DB_NAME, empresa_nome):
    if not empresa_nome or empresa_nome == "Todas as Empresas":
        return "Consolidado Geral / Múltiplas Empresas"
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cnpj = "Não informado"
    try:
        cursor = conn.cursor()
        for tabela in ["empresas", "clientes", "cad_empresas", "base_empresas"]:
            try:
                cursor.execute(f"SELECT * FROM {tabela}")
                rows = cursor.fetchall()
                col_names = [description[0].lower() for description in cursor.description]
                name_idx = next((i for i, c in enumerate(col_names) if any(k in c for k in ['nome', 'razao', 'empresa'])), None)
                cnpj_idx = next((i for i, c in enumerate(col_names) if 'cnpj' in c), None)
                if name_idx is not None and cnpj_idx is not None:
                    for row in rows:
                        if str(row[name_idx]).strip().lower() == str(empresa_nome).strip().lower():
                            cnpj = str(row[cnpj_idx])
                            break
                if cnpj != "Não informado": break
            except: continue
    except: pass
    finally: conn.close()
    return cnpj

def renderizar_aba_relatorios(DB_NAME, is_admin, emp_usuario, get_empresas_func, formatar_colunas_func, adicionar_numeracao_func):
    st.markdown("""
        <style>
        .print-header { display: none; }
        .tabela-container { width: 100%; overflow-x: auto; margin-bottom: 20px; }
        .tabela-relatorio { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 11px; background-color: #ffffff; }
        .tabela-relatorio th { background-color: #e9ecef; color: #000000 !important; font-weight: bold; border: 1px solid #444444; padding: 8px; text-align: left; }
        .tabela-relatorio td { color: #000000 !important; border: 1px solid #bbbbbb; padding: 6px; }
        .tabela-relatorio tr:nth-child(even) { background-color: #f8f9fa; }

        /* Ajuste fino para alinhar perfeitamente o botão nativo do Streamlit ao lado do componente */
        div.stButton > button {
            height: 38px !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
            margin-top: 0px !important;
        }

        @media print {
            @page { size: A4 landscape; margin: 10mm; }
            
            section[data-testid="stSidebar"],
            div[data-testid="stSidebar"],
            header,
            footer,
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stDecoration"],
            .stButton,
            .stCheckbox,
            .stSelectbox,
            .stAlert,
            iframe,
            div[data-testid="stIFrame"],
            .print-hide,
            h1,
            label {
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                width: 0 !important;
                overflow: hidden !important;
                margin: 0 !important;
                padding: 0 !important;
                border: none !important;
            }

            body, html, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
                background-color: #ffffff !important;
                color: #000000 !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }

            .print-header {
                display: block !important;
                margin-bottom: 20px !important;
                font-family: Arial, sans-serif !important;
                color: #000000 !important;
            }
            .print-header h2, .print-header p {
                color: #000000 !important;
            }

            .tabela-container {
                overflow: visible !important;
                width: 100% !important;
                height: auto !important;
                display: block !important;
                margin-bottom: 25px !important;
            }
            .tabela-relatorio {
                width: 100% !important;
                background-color: #ffffff !important;
            }
            .tabela-relatorio tr {
                page-break-inside: avoid;
                page-break-after: auto;
            }
            .tabela-relatorio th {
                background-color: #cccccc !important;
                color: #000000 !important;
                font-weight: bold !important;
                border: 1px solid #000000 !important;
                padding: 8px !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            .tabela-relatorio td {
                color: #000000 !important;
                background-color: #ffffff !important;
                border: 1px solid #000000 !important;
                padding: 6px !important;
                font-weight: 500 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    col_h1, col_h2, col_h3 = st.columns([0.5, 0.25, 0.25])
    with col_h1: st.title("📈 Relatórios Consolidados")
    with col_h2:
        # Removido o st.write("") extra para nivelar perfeitamente com o título
        components.html("""
            <div style="font-family: Source Sans Pro, sans-serif; margin: 0; padding-top: 5px;">
                <button onclick="parent.window.print();" style="
                    display: inline-flex; align-items: center; justify-content: center;
                    background-color: rgb(255, 255, 255); color: rgb(49, 51, 63);
                    border: 1px solid rgb(230, 234, 241); padding: 0px 0.75rem;
                    border-radius: 0.5rem; font-weight: 400; font-size: 14px;
                    cursor: pointer; width: 100%; height: 38px; font-family: inherit;
                    box-shadow: rgba(0, 0, 0, 0.05) 0px 1px 2px 0px;
                ">
                    🖨️ Imprimir Relatórios
                </button>
            </div>
        """, height=44)
    with col_h3:
        # Espaçamento idêntico aplicado ao botão nativo do Streamlit
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_rel", use_container_width=True): st.rerun()

    st.markdown('<p style="font-weight: bold; margin-bottom: 5px;" class="print-hide">Selecione os relatórios que deseja visualizar:</p>', unsafe_allow_html=True)
    c_chk1, c_chk2, c_chk3, c_chk4 = st.columns(4)
    show_funcs = c_chk1.checkbox("Funcionários", value=True)
    show_ex = c_chk1.checkbox("Exames", value=True)
    show_tr = c_chk2.checkbox("Treinamentos", value=True)
    show_epi = c_chk2.checkbox("EPIs", value=False)
    show_doc = c_chk3.checkbox("Documentos", value=False)
    show_serv = c_chk3.checkbox("Serviços", value=True)
    show_abs = c_chk4.checkbox("Absenteísmo", value=True)

    empresas = get_empresas_func()
    opcoes_filtro = ["Todas as Empresas"] + (empresas if empresas else [])

    if is_admin:
        st.markdown('<p style="margin-bottom: 0px; font-size:14px;" class="print-hide">Filtrar por Empresa</p>', unsafe_allow_html=True)
        empresa_filtro = st.selectbox("", opcoes_filtro, key="filtro_rel_emp", label_visibility="collapsed")
    else:
        empresa_filtro = emp_usuario

    st.markdown("---")

    cnpj_empresa_atual = obter_cnpj_empresa(DB_NAME, empresa_filtro)
    st.markdown(f"""
        <div class="print-header">
            <h2 style="margin:0; font-size:18pt; color:#000000;">Cassilab - Gestão em SST</h2>
            <p style="margin:6px 0 2px 0; font-size:12pt; color:#000000;"><b>Empresa:</b> {empresa_filtro}</p>
            <p style="margin:0 0 15px 0; font-size:12pt; color:#000000;"><b>CNPJ:</b> {cnpj_empresa_atual}</p>
            <hr style="border: 1px solid #000000; margin-bottom: 20px;"/>
        </div>
    """, unsafe_allow_html=True)

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
        df_funcs = pd.read_sql("SELECT * FROM base_funcionarios", conn)
        df_exames = pd.read_sql("SELECT * FROM exames", conn)
        df_trein = pd.read_sql("SELECT * FROM treinamentos", conn)
        df_epis = pd.read_sql("SELECT * FROM epis", conn)
        df_docs = pd.read_sql("SELECT * FROM documentos", conn)
        df_serv = pd.read_sql("SELECT * FROM servicos_realizados", conn)
        df_abs = pd.read_sql("SELECT * FROM absenteismo", conn)
    except:
        df_funcs, df_exames, df_trein, df_epis, df_docs, df_serv, df_abs = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    conn.close()

    # Filtragem por empresa
    if is_admin and empresa_filtro != "Todas as Empresas":
        emp_lower = str(empresa_filtro).strip().lower()
        if not df_funcs.empty and "empresa" in df_funcs.columns: df_funcs = df_funcs[df_funcs["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_exames.empty and "empresa" in df_exames.columns: df_exames = df_exames[df_exames["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_trein.empty and "empresa" in df_trein.columns: df_trein = df_trein[df_trein["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_epis.empty and "empresa" in df_epis.columns: df_epis = df_epis[df_epis["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_docs.empty and "empresa" in df_docs.columns: df_docs = df_docs[df_docs["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_serv.empty and "empresa" in df_serv.columns: df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_abs.empty and "empresa" in df_abs.columns: df_abs = df_abs[df_abs["empresa"].astype(str).str.strip().str.lower() == emp_lower]
    elif not is_admin:
        emp_lower = str(emp_usuario).strip().lower()
        if not df_funcs.empty and "empresa" in df_funcs.columns: df_funcs = df_funcs[df_funcs["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_exames.empty and "empresa" in df_exames.columns: df_exames = df_exames[df_exames["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_trein.empty and "empresa" in df_trein.columns: df_trein = df_trein[df_trein["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_epis.empty and "empresa" in df_epis.columns: df_epis = df_epis[df_epis["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_docs.empty and "empresa" in df_docs.columns: df_docs = df_docs[df_docs["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_serv.empty and "empresa" in df_serv.columns: df_serv = df_serv[df_serv["empresa"].astype(str).str.strip().str.lower() == emp_lower]
        if not df_abs.empty and "empresa" in df_abs.columns: df_abs = df_abs[df_abs["empresa"].astype(str).str.strip().str.lower() == emp_lower]

    # Ordenação alfabética
    if not df_funcs.empty and "funcionario" in df_funcs.columns: df_funcs = df_funcs.sort_values(by="funcionario", ascending=True)
    if not df_exames.empty and "funcionario" in df_exames.columns: df_exames = df_exames.sort_values(by="funcionario", ascending=True)
    if not df_trein.empty and "funcionario" in df_trein.columns: df_trein = df_trein.sort_values(by="funcionario", ascending=True)
    if not df_epis.empty and "funcionario" in df_epis.columns: df_epis = df_epis.sort_values(by="funcionario", ascending=True)
    if not df_docs.empty and "documento" in df_docs.columns: df_docs = df_docs.sort_values(by="documento", ascending=True)
    if not df_serv.empty and "servico" in df_serv.columns: df_serv = df_serv.sort_values(by="servico", ascending=True)
    if not df_abs.empty and "nome" in df_abs.columns: df_abs = df_abs.sort_values(by="nome", ascending=True)

    def renderizar_tabela_html(df, titulo, csv_nome):
        st.subheader(titulo)
        if not df.empty:
            df_view = adicionar_numeracao_func_local(formatar_colunas_func(df))
            html_tabela = df_view.to_html(classes='tabela-relatorio', index=False, escape=False)
            st.markdown(f'<div class="tabela-container">{html_tabela}</div>', unsafe_allow_html=True)
            csv_data = df_view.to_csv(index=False).encode('utf-8')
            st.download_button(f"📥 Baixar {titulo} (CSV)", data=csv_data, file_name=csv_nome, mime="text/csv", key=f"dl_{csv_nome}")
        else:
            st.info(f"Nenhum registro encontrado para {titulo.lower()}.")
        st.markdown("---")

    if show_funcs: renderizar_tabela_html(df_funcs, "👥 Relatório de Funcionários", "relatorio_funcionarios.csv")
    if show_ex: renderizar_tabela_html(df_exames, "🩺 Relatório de Exames Ocupacionais", "relatorio_exames.csv")
    if show_tr: renderizar_tabela_html(df_trein, "📚 Relatório de Treinamentos", "relatorio_treinamentos.csv")
    if show_epi: renderizar_tabela_html(df_epis, "🦺 Relatório de EPIs", "relatorio_epis.csv")
    if show_doc: renderizar_tabela_html(df_docs, "📄 Relatório de Documentos", "relatorio_documentos.csv")
    if show_serv: renderizar_tabela_html(df_serv, "🛠️ Relatório de Serviços Realizados", "relatorio_servicos.csv")
    if show_abs: renderizar_tabela_html(df_abs, "📊 Relatório de Absenteísmo", "relatorio_absenteismo.csv")

def adicionar_numeracao_func_local(df):
    if df is None or df.empty: return df
    df = df.copy()
    if "Nº" in df.columns: df = df.drop(columns=["Nº"])
    df.insert(0, "Nº", range(1, len(df) + 1))
    return df