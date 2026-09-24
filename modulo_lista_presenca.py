import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import base64

def renderizar_aba_lista_presenca(*args, **kwargs):
    # Mapeamento flexível e seguro para os argumentos recebidos do app.py
    DB_NAME = kwargs.get("DB_NAME") or (args[0] if len(args) > 0 else "cassilab_gestao.db")
    is_admin = kwargs.get("is_admin") if "is_admin" in kwargs else (args[1] if len(args) > 1 else False)
    emp_usuario = kwargs.get("emp_usuario") or (args[2] if len(args) > 2 else "")
    
    if len(args) >= 5:
        get_empresas_func = args[3]
        raw_registrar_log_func = args[4]
    elif len(args) == 3:
        get_empresas_func = args[1]
        raw_registrar_log_func = args[2]
    else:
        get_empresas_func = kwargs.get("get_empresas_func") or (lambda: [])
        raw_registrar_log_func = kwargs.get("registrar_log_func") or None

    def registrar_log_func(*l_args, **l_kwargs):
        if not callable(raw_registrar_log_func):
            return
        try:
            return raw_registrar_log_func(*l_args, **l_kwargs)
        except Exception:
            try:
                if len(l_args) >= 2:
                    return raw_registrar_log_func(l_args[0], l_args[1])
            except Exception:
                pass

    col_h1, col_h2 = st.columns([0.8, 0.2])
    with col_h1: st.title("📋 Gerador de Lista de Presença de Treinamento")
    with col_h2:
        st.write("")
        if st.button("🔄 Atualizar Aba", key="btn_atualizar_lp"): st.rerun()

    empresas = get_empresas_func() if callable(get_empresas_func) else []
    
    if not empresas:
        st.warning("⚠️ Nenhuma empresa cadastrada no sistema.")
        return

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
        df_cad_tr = pd.read_sql("SELECT treinamento, carga_horaria FROM cad_treinamentos ORDER BY treinamento ASC", conn)
    except:
        df_cad_tr = pd.DataFrame()
    conn.close()

    lista_treinamentos_opcoes = df_cad_tr["treinamento"].tolist() if not df_cad_tr.empty else []
    mapa_carga_horaria = dict(zip(df_cad_tr["treinamento"], df_cad_tr["carga_horaria"])) if not df_cad_tr.empty else {}

    with st.expander("⚙️ Configurações da Lista de Presença", expanded=True):
        c_p1, c_p2 = st.columns(2)
        if is_admin:
            empresa_selecionada = c_p1.selectbox("Selecione a Empresa Cliente", empresas, key="lp_empresa")
        else:
            empresa_selecionada = emp_usuario if emp_usuario in empresas else (empresas[0] if empresas else "")
            c_p1.markdown(f"**Empresa Cliente:** {empresa_selecionada}")

        logo_file = c_p2.file_uploader("📂 Inserir Logo da Empresa (Opcional)", type=["png", "jpg", "jpeg"])

        c_p3, c_p4, c_p5 = st.columns(3)
        
        if lista_treinamentos_opcoes:
            treinamento_nome = c_p3.selectbox("Treinamento", lista_treinamentos_opcoes, key="lp_sel_treinamento")
            carga_sugerida = mapa_carga_horaria.get(treinamento_nome, "4 horas")
        else:
            treinamento_nome = c_p3.text_input("Treinamento", value="Treinamento de Integração / NR")
            carga_sugerida = "4 horas"

        carga_horaria = c_p4.text_input("Carga Horária", value=str(carga_sugerida))
        data_treinamento = c_p5.date_input("Data do Treinamento", value=datetime.today())

        c_p6, c_p7 = st.columns(2)
        local_treinamento = c_p6.text_input("Local", value="Sala de Treinamentos / Refeitório")
        horario_treinamento = c_p7.text_input("Horário", value="08:00 às 12:00")

        tema_treinamento = st.text_area("Tema (Descrição longa)", value="Abordagem prática sobre segurança preventiva, diretrizes operacionais e uso adequado dos dispositivos de proteção.", height=70)

        c_p9, c_p10 = st.columns(2)
        tipo_instrutor = c_p9.selectbox("Instrutores", ["( X ) Interno    (   ) Externo", "(   ) Interno    ( X ) Externo"])
        classificacao_trein = c_p10.selectbox("Classificação", ["( X ) Técnico    (   ) Comportamental", "(   ) Técnico    ( X ) Comportamental"])

        st.markdown("---")
        st.markdown("##### ✏️ Assinatura da Contratante, Instrutor e Conteúdo")
        
        opcoes_contratante = ["-- Selecionar da lista de empresas --", "Outra (Digitar manualmente)"] + empresas
        escolha_contratante = st.selectbox("Empresa Contratante (para Assinatura)", opcoes_contratante, key="sel_contratante_lp")
        if escolha_contratante == "Outra (Digitar manualmente)":
            contratante_nome_final = st.text_input("Digite o nome da Contratante / Representante", value=empresa_selecionada)
        elif escolha_contratante != "-- Selecionar da lista de empresas --":
            contratante_nome_final = escolha_contratante
        else:
            contratante_nome_final = empresa_selecionada

        c_i1, c_i2 = st.columns(2)
        instrutor_nome = c_i1.text_input("Nome e Registro do Instrutor", value="Luiz Marcelo Fontana (Técnico em Segurança do Trabalho - Reg. MTE 12.054 - PR)")
        instrutor_area = c_i2.text_input("Área do Instrutor", value="Técnico / SST")

        detalhamento_conteudo = st.text_area(
            "Detalhamento de Conteúdo (Itens do Treinamento - Editável)",
            value="Norma Regulamentadora;\nDescrição e características dos equipamentos e seus componentes;\nRisco ocupacional contra o qual o item oferece proteção;\nConceitos e Legislação;\nObrigações do empregador e dos empregados;\nRestrições e limitações de proteção;\nForma adequada de uso e ajustes necessários;\nManutenção, substituição, limpeza e descarte correto.",
            height=120
        )

    st.markdown("---")
    st.subheader(f"👥 Participantes da Empresa: {empresa_selecionada}")
    
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    try:
        df_funcs = pd.read_sql("SELECT matricula, funcionario, setor, cpf FROM base_funcionarios WHERE empresa = ? AND status LIKE '%Ativo%' ORDER BY funcionario ASC", conn, params=(empresa_selecionada,))
    except:
        df_funcs = pd.DataFrame()
    conn.close()

    if not df_funcs.empty:
        df_funcs["Selecionar"] = True
        df_funcs["Nº"] = range(1, len(df_funcs) + 1)
        
        df_editado_participantes = st.data_editor(
            df_funcs[["Selecionar", "Nº", "matricula", "funcionario", "setor", "cpf"]].rename(columns={
                "matricula": "MATRÍCULA",
                "funcionario": "NOME COMPLETO",
                "setor": "ÁREA",
                "cpf": "RG/CPF"
            }),
            hide_index=True,
            use_container_width=True,
            key="editor_participantes_lp"
        )

        participantes_selecionados = df_editado_participantes[df_editado_participantes["Selecionar"] == True]

        st.markdown("---")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        gerar_doc = col_btn1.button("📄 Atualizar / Gerar Visualização Oficial", type="primary", use_container_width=True)

        if gerar_doc or "mostrar_doc_lp" in st.session_state:
            st.session_state["mostrar_doc_lp"] = True
            registrar_log_func(st.session_state.get("nome_usuario", "Desconhecido"), empresa_selecionada, f"Gerou lista de presença para: {treinamento_nome}")
            
            st.success("✅ Documento gerado com sucesso! Utilize o botão de impressão logo abaixo.")

            logo_html = ""
            if logo_file:
                bytes_logo = logo_file.getvalue()
                encoded_logo = base64.b64encode(bytes_logo).decode()
                tipo_arquivo = logo_file.type.split("/")[-1]
                logo_html = f'<img src="data:image/{tipo_arquivo};base64,{encoded_logo}" style="max-height: 70px; max-width: 180px; object-fit: contain;" />'
            else:
                logo_html = '<div style="border: 1px dashed #ccc; padding: 10px; font-size: 11px; color: #666; text-align: center;">[ Logo da Empresa ]</div>'

            linhas_tabela_html = ""
            for i, (_, row) in enumerate(participantes_selecionados.iterrows(), start=1):
                mat = str(row["MATRÍCULA"]) if pd.notna(row["MATRÍCULA"]) else ""
                nome = str(row["NOME COMPLETO"]) if pd.notna(row["NOME COMPLETO"]) else ""
                area = str(row["ÁREA"]) if pd.notna(row["ÁREA"]) else ""
                cpf = str(row["RG/CPF"]) if pd.notna(row["RG/CPF"]) else ""
                
                linhas_tabela_html += f"""
                <tr>
                    <td style="text-align: center; width: 4%;">{i}</td>
                    <td style="text-align: center; width: 10%;">{mat}</td>
                    <td style="text-align: left; width: 26%; padding-left: 6px;">{nome}</td>
                    <td style="text-align: left; width: 16%; padding-left: 6px;">{area}</td>
                    <td style="text-align: center; width: 14%;">{cpf}</td>
                    <td style="text-align: center; width: 30%; height: 26px;"></td>
                </tr>
                """

            itens_detalhe_html = ""
            for item in detalhamento_conteudo.split("\n"):
                if item.strip():
                    itens_detalhe_html += f"<li>{item.strip()}</li>"

            html_documento = f"""
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <style>
                    @page {{
                        size: A4 landscape;
                        margin: 10mm;
                    }}
                    body {{
                        font-family: Arial, sans-serif;
                        font-size: 11px;
                        color: #000;
                        margin: 0;
                        padding: 0;
                        background-color: #fff;
                    }}
                    .sheet {{
                        width: 100%;
                        box-sizing: border-box;
                    }}
                    table.borda-tabela {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 5px;
                    }}
                    table.borda-tabela th, table.borda-tabela td {{
                        border: 1px solid #000;
                        padding: 4px 6px;
                        font-size: 11px;
                    }}
                    table.borda-tabela th {{
                        background-color: #f2f2f2;
                        text-align: center;
                        font-weight: bold;
                    }}
                    .cabecalho-principal {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 8px;
                    }}
                    .cabecalho-principal td {{
                        border: 1px solid #000;
                        padding: 6px;
                        vertical-align: middle;
                    }}
                    .secao-titulo {{
                        background-color: #e6e6e6;
                        font-weight: bold;
                        padding: 4px 6px;
                        border: 1px solid #000;
                        margin-top: 8px;
                        margin-bottom: 0px;
                        font-size: 11px;
                    }}
                    .detalhes-box {{
                        border: 1px solid #000;
                        border-top: none;
                        padding: 6px;
                        font-size: 10.5px;
                        margin-bottom: 8px;
                    }}
                    .detalhes-box ul {{
                        margin: 0;
                        padding-left: 20px;
                    }}
                    .detalhes-box li {{
                        margin-bottom: 2px;
                    }}
                    .rodape-assinaturas {{
                        width: 100%;
                        margin-top: 15px;
                        border-collapse: collapse;
                    }}
                    .rodape-assinaturas td {{
                        border: 1px solid #000;
                        padding: 6px;
                        vertical-align: top;
                        font-size: 10.5px;
                    }}
                    @media print {{
                        body {{
                            -webkit-print-color-adjust: exact;
                        }}
                        .no-print {{
                            display: none !important;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="no-print" style="background: #e9ecef; padding: 12px; margin-bottom: 15px; border-radius: 6px; text-align: center;">
                    <button onclick="window.print()" style="background-color: #28a745; color: white; border: none; padding: 12px 25px; font-size: 15px; font-weight: bold; border-radius: 4px; cursor: pointer;">
                        🖨️ IMPRIMIR / SALVAR EM PDF (A4 PAISAGEM)
                    </button>
                    <p style="margin: 5px 0 0 0; font-size: 12px; color: #555;">Dica: Na janela de impressão, certifique-se de configurar o Destino como <b>"Salvar como PDF"</b> e Layout como <b>"Paisagem"</b>.</p>
                </div>

                <div class="sheet">
                    <!-- CABEÇALHO -->
                    <table class="cabecalho-principal">
                        <tr>
                            <td style="width: 20%; text-align: center;">
                                {logo_html}
                            </td>
                            <td style="width: 45%; text-align: center; font-size: 15px; font-weight: bold;">
                                LISTA DE TREINAMENTO
                            </td>
                            <td style="width: 35%;">
                                <b>Empresa:</b> {empresa_selecionada}<br>
                                <b>Data Emissão:</b> {datetime.today().strftime('%d/%m/%Y')}<br>
                                <b>Revisão:</b> _____/_____/_________
                            </td>
                        </tr>
                    </table>

                    <!-- DADOS DO TREINAMENTO -->
                    <table class="borda-tabela">
                        <tr>
                            <td colspan="4"><b>Treinamento:</b> {treinamento_nome}</td>
                            <td colspan="2"><b>Carga Horária:</b> {carga_horaria}</td>
                        </tr>
                        <tr>
                            <td colspan="3"><b>Data:</b> {data_treinamento.strftime('%d/%m/%Y')}</td>
                            <td colspan="3"><b>Local:</b> {local_treinamento}</td>
                        </tr>
                        <tr>
                            <td colspan="3"><b>Tema:</b> {tema_treinamento.replace(chr(10), '<br>')}</td>
                            <td colspan="3"><b>Horário:</b> {horario_treinamento}</td>
                        </tr>
                        <tr>
                            <td colspan="3"><b>Instrutores:</b> {tipo_instrutor}</td>
                            <td colspan="3"><b>Classificação:</b> {classificacao_trein}</td>
                        </tr>
                    </table>

                    <!-- TABELA DE PARTICIPANTES -->
                    <table class="borda-tabela" style="margin-top: 8px;">
                        <thead>
                            <tr>
                                <th style="width: 4%;">N°</th>
                                <th style="width: 10%;">MATRÍCULA</th>
                                <th style="width: 26%;">NOME COMPLETO</th>
                                <th style="width: 16%;">ÁREA</th>
                                <th style="width: 14%;">RG/CPF</th>
                                <th style="width: 30%;">ASSINATURA</th>
                            </tr>
                        </thead>
                        <tbody>
                            {linhas_tabela_html}
                        </tbody>
                    </table>

                    <!-- DETALHAMENTO DE CONTEÚDO -->
                    <div class="secao-titulo">DETALHAMENTO DE CONTEÚDO:</div>
                    <div class="detalhes-box">
                        <ul>
                            {itens_detalhe_html}
                        </ul>
                    </div>

                    <!-- REGISTRO DE INSTRUTORES E CONTRATANTE -->
                    <div class="secao-titulo">REGISTRO DE INSTRUTORES E CONTRATANTE:</div>
                    <table class="rodape-assinaturas">
                        <tr>
                            <td style="width: 50%;">
                                <b>INSTRUTOR:</b> {instrutor_nome}<br>
                                <b>ÁREA:</b> {instrutor_area}
                            </td>
                            <td style="width: 50%;">
                                <b>CONTRATANTE / REPRESENTANTE:</b> {contratante_nome_final}<br>
                                <b>ASSINATURA:</b><br><br>
                            </td>
                        </tr>
                    </table>
                </div>
            </body>
            </html>
            """

            st.components.v1.html(html_documento, height=900, scrolling=True)

    else:
        st.info("ℹ️ Nenhum funcionário ativo cadastrado para esta empresa. Cadastre colaboradores na aba de Funcionários para preencher a lista automaticamente.")