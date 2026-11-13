import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import base64

def renderizar_aba_lista_presenca(*args, **kwargs):
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
        if st.button("🔄 Nova Lista / Limpar Campos", key="btn_atualizar_lp"):
            for k in ["lp_treinamento_txt", "lp_carga_txt", "lp_data_txt", "lp_local_txt", "lp_horario_txt", "lp_tema_txt", "lp_detalhe_txt"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

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

    lista_treinamentos_opcoes = ["-- Digitar ou Selecionar --"] + (df_cad_tr["treinamento"].tolist() if not df_cad_tr.empty else [])
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
        
        sel_trein = c_p3.selectbox("Treinamento Cadastrado", lista_treinamentos_opcoes, key="lp_sel_treinamento")
        
        default_trein_val = "" if sel_trein == "-- Digitar ou Selecionar --" else sel_trein
        default_carga_val = "" if sel_trein == "-- Digitar ou Selecionar --" else str(mapa_carga_horaria.get(sel_trein, ""))

        treinamento_nome = c_p3.text_input("Nome do Treinamento", value=default_trein_val, placeholder="Ex: Integração / DDS", key="lp_treinamento_txt")
        carga_horaria = c_p4.text_input("Carga Horária", value=default_carga_val, placeholder="Ex: 4 horas", key="lp_carga_txt")
        
        data_treinamento = c_p5.text_input("Data do Treinamento", value="", placeholder="Ex: 15/10/2026 ou em branco", key="lp_data_txt")

        c_p6, c_p7 = st.columns(2)
        local_treinamento = c_p6.text_input("Local", value="", placeholder="Ex: Sala de Reuniões", key="lp_local_txt")
        horario_treinamento = c_p7.text_input("Horário", value="", placeholder="Ex: 08:00 às 12:00", key="lp_horario_txt")

        tema_treinamento = st.text_area("Tema (Descrição longa)", value="", placeholder="Digite o tema ou descrição do treinamento...", height=70, key="lp_tema_txt")

        c_p9, c_p10 = st.columns(2)
        tipo_instrutor = c_p9.selectbox("Instrutores", ["( X ) Interno    (    ) Externo", "(    ) Interno    ( X ) Externo"])
        classificacao_trein = c_p10.selectbox("Classificação", ["( X ) Técnico    (    ) Comportamental", "(    ) Técnico    ( X ) Comportamental"])

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
            value="",
            placeholder="Digite os tópicos abordados (cada linha virará um item da lista)...",
            height=120,
            key="lp_detalhe_txt"
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
                logo_html = f'<img src="data:image/{tipo_arquivo};base64,{encoded_logo}" style="max-height: 55px; max-width: 150px; object-fit: contain;" />'
            else:
                logo_html = '<div style="border: 1px dashed #ccc; padding: 6px; font-size: 10px; color: #666; text-align: center;">[ Logo da Empresa ]</div>'

            lista_participantes_rows = list(participantes_selecionados.iterrows())
            total_participantes = len(lista_participantes_rows)
            paginas_html = ""
            
            limite_pagina_unica = 17
            if total_participantes <= limite_pagina_unica:
                bloco_linhas_html = ""
                for j in range(limite_pagina_unica):
                    idx_atual = j
                    num_linha = idx_atual + 1
                    
                    if idx_atual < total_participantes:
                        _, row = lista_participantes_rows[idx_atual]
                        mat = str(row["MATRÍCULA"]) if pd.notna(row["MATRÍCULA"]) else ""
                        nome = str(row["NOME COMPLETO"]) if pd.notna(row["NOME COMPLETO"]) else ""
                        area = str(row["ÁREA"]) if pd.notna(row["ÁREA"]) else ""
                        cpf = str(row["RG/CPF"]) if pd.notna(row["RG/CPF"]) else ""
                    else:
                        mat, nome, area, cpf = "", "", "", ""

                    bloco_linhas_html += (
                        "<tr>"
                        f'<td style="text-align: center; width: 4%;">{num_linha}</td>'
                        f'<td style="text-align: center; width: 10%;">{mat}</td>'
                        f'<td style="text-align: left; width: 26%; padding-left: 6px;">{nome}</td>'
                        f'<td style="text-align: left; width: 16%; padding-left: 6px;">{area}</td>'
                        f'<td style="text-align: center; width: 14%;">{cpf}</td>'
                        f'<td style="text-align: center; width: 30%; height: 25px;"></td>'
                        "</tr>"
                    )

                data_hoje_str = datetime.today().strftime('%d/%m/%Y')
                data_trein_str = data_treinamento if data_treinamento else ""
                tema_fmt = tema_treinamento.replace("\n", "<br>")

                itens_detalhe_html = ""
                for item in detalhamento_conteudo.split("\n"):
                    if item.strip():
                        itens_detalhe_html += f"<li>{item.strip()}</li>"

                paginas_html += (
                    '<div class="sheet">'
                    '<table class="cabecalho-principal"><tr>'
                    f'<td style="width: 20%; text-align: center;">{logo_html}</td>'
                    '<td style="width: 45%; text-align: center; font-size: 13px; font-weight: bold;">LISTA DE PRESENÇA</td>'
                    f'<td style="width: 35%; font-size: 9px;"><b>Empresa:</b> {empresa_selecionada}<br><b>Data Emissão:</b> {data_hoje_str}<br><b>Revisão:</b> _____/_____/_________</td>'
                    '</tr></table>'
                    '<table class="borda-tabela">'
                    f'<tr><td colspan="4"><b>Treinamento:</b> {treinamento_nome}</td><td colspan="2"><b>Carga Horária:</b> {carga_horaria}</td></tr>'
                    f'<tr><td colspan="3"><b>Data:</b> {data_trein_str}</td><td colspan="3"><b>Local:</b> {local_treinamento}</td></tr>'
                    f'<tr><td colspan="3"><b>Tema:</b> {tema_fmt}</td><td colspan="3"><b>Horário:</b> {horario_treinamento}</td></tr>'
                    f'<tr><td colspan="3"><b>Instrutores:</b> {tipo_instrutor}</td><td colspan="3"><b>Classificação:</b> {classificacao_trein}</td></tr>'
                    '</table>'
                    '<table class="borda-tabela" style="margin-top: 3px;">'
                    '<thead><tr>'
                    '<th style="width: 4%;">N°</th>'
                    '<th style="width: 10%;">MATRÍCULA</th>'
                    '<th style="width: 26%;">NOME COMPLETO</th>'
                    '<th style="width: 16%;">ÁREA</th>'
                    '<th style="width: 14%;">RG/CPF</th>'
                    '<th style="width: 30%;">ASSINATURA</th>'
                    '</tr></thead>'
                    f'<tbody>{bloco_linhas_html}</tbody>'
                    '</table>'
                    '<div class="secao-titulo" style="margin-top: 3px; font-size: 8px; padding: 2px 4px;">DETALHAMENTO DE CONTEÚDO:</div>'
                    '<div
