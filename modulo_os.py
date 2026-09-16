import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import base64

def renderizar_aba_os(DB_NAME, get_empresas_func, registrar_log_callback):
    st.title("📝 Elaboração de Ordem de Serviço (OS) - Conforme NR")
    st.markdown("Selecione a empresa e o funcionário abaixo. O cargo e o setor serão preenchidos automaticamente. Você pode enviar a logo do cliente, editar o conteúdo e imprimi-la perfeitamente em formato A4.")

    empresas = get_empresas_func()
    emp_os_sel = st.selectbox("Selecione a Empresa", ["-- Selecione --"] + empresas, key="os_empresa_sel")

    if emp_os_sel != "-- Selecione --":
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_funcs_os = pd.read_sql("SELECT funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC", conn, params=(emp_os_sel,))
        conn.close()

        if not df_funcs_os.empty:
            lista_funcs_os = df_funcs_os["funcionario"].tolist()
            func_os_sel = st.selectbox("Selecione o Funcionário", ["-- Selecione o Funcionário --"] + lista_funcs_os, key="os_func_sel")

            if func_os_sel != "-- Selecione o Funcionário --":
                dados_func = df_funcs_os[df_funcs_os["funcionario"] == func_os_sel].iloc[0]
                cargo_auto = str(dados_func["cargo"]) if pd.notna(dados_func["cargo"]) else ""
                setor_auto = str(dados_func["setor"]) if pd.notna(dados_func["setor"]) else ""

                st.markdown("---")
                st.subheader(f"📄 Ordem de Serviço para: {func_os_sel}")
                
                with st.form("form_edicao_os"):
                    logo_arquivo = st.file_uploader("🖼️ Inserir Logo do Cliente (PNG, JPG)", type=["png", "jpg", "jpeg"])
                    
                    col_h1, col_h2 = st.columns(2)
                    os_empresa_nome = col_h1.text_input("Empresa", value=emp_os_sel)
                    os_func_nome = col_h2.text_input("Nome do Colaborador", value=func_os_sel)
                    
                    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                    os_cargo = col_c1.text_input("Cargo", value=cargo_auto)
                    os_setor = col_c2.text_input("Setor", value=setor_auto)
                    os_dt_elab = col_c3.text_input("Data Elaboração", value=datetime.today().strftime("%d/%m/%Y"))
                    os_dt_rev = col_c4.text_input("Data Revisão", value=datetime.today().strftime("%d/%m/%Y"))

                    st.markdown("### 1. Descrição da Atividade / Função")
                    os_descricao = st.text_area(
                        "Descrição detalhada das atividades executadas pelo colaborador",
                        value="Manutenção preventiva e corretiva, inspeção e execução de rotinas operacionais inerentes ao cargo, seguindo rigorosamente os procedimentos de segurança da empresa e normas regulamentadoras aplicáveis.",
                        height=150
                    )

                    st.markdown("### 2. Agentes Associados às Atividades (Riscos)")
                    os_riscos = st.text_area(
                        "Riscos Físicos, Químicos, Biológicos, Ergonômicos e de Acidentes",
                        value="Riscos Físicos - Ruído gerado nos ambientes de trabalho.\nRiscos de Acidentes - Queda de altura, ferimentos com ferramentas manuais e elétricas, choque elétrico, riscos de acidentes no deslocamento.",
                        height=100
                    )

                    st.markdown("### 3. EPIs de Uso Obrigatório")
                    os_epis = st.text_area(
                        "Equipamentos de Proteção Individual fornecidos e de uso obrigatório",
                        value="Uso geral: Calçado de Segurança, luvas de proteção, proteção auditiva, óculos de segurança.\nTrabalho em altura (quando aplicável): Cinto de segurança tipo paraquedista, talabarte, capacete com jugular.",
                        height=100
                    )

                    st.markdown("### 4. Recomendações de Segurança")
                    os_recomendacoes = st.text_area(
                        "Orientações e cuidados gerais para prevenção de acidentes",
                        value="Cuidados nos deslocamentos pela fábrica e setores; utilize os EPIs apenas para a finalidade a que se destinam e mantenha-os sob guarda e conservação; observe atentamente o meio ambiente de trabalho e informe condições inseguras imediatamente.",
                        height=100
                    )

                    st.markdown("### 5. Procedimentos em Caso de Acidentes")
                    os_acidentes = st.text_area(
                        "Condutas em caso de ocorrências ou incidentes",
                        value="Todo e qualquer acidente de trabalho, por mais leve que seja, deverá ser comunicado imediatamente ao superior direto e ao SESMT.\nO acidente não comunicado não será considerado para efeitos legais.",
                        height=100
                    )

                    st.markdown("### 6. Observações e Disposições Legais")
                    os_observacoes = st.text_area(
                        "Advertências, treinamentos e penalidades",
                        value="Mantenha em dia seus treinamentos obrigatórios (Nrs).\nNão executar qualquer atividade sem treinamento e pleno conhecimento dos riscos.\nO não cumprimento ao disposto nesta Ordem de Serviço sujeita o trabalhador às penalidades cabíveis previstas na legislação trabalhista e normas da empresa.",
                        height=100
                    )

                    btn_gerar_os = st.form_submit_button("🖨️ Gerar Ordem de Serviço", use_container_width=True)

                if btn_gerar_os:
                    logo_base64 = ""
                    if logo_arquivo is not None:
                        bytes_logo = logo_arquivo.read()
                        logo_base64 = f"data:image/jpeg;base64,{base64.b64encode(bytes_logo).decode()}"

                    st.session_state["os_gerada_data"] = {
                        "empresa": os_empresa_nome,
                        "funcionario": os_func_nome,
                        "cargo": os_cargo,
                        "setor": os_setor,
                        "dt_elab": os_dt_elab,
                        "dt_rev": os_dt_rev,
                        "descricao": os_descricao,
                        "riscos": os_riscos,
                        "epis": os_epis,
                        "recomendacoes": os_recomendacoes,
                        "acidentes": os_acidentes,
                        "observacoes": os_observacoes,
                        "logo": logo_base64
                    }
                    st.success("✅ Ordem de Serviço gerada com sucesso abaixo!")

            if "os_gerada_data" in st.session_state:
                d = st.session_state["os_gerada_data"]
                st.markdown("---")
                
                tag_logo = f'<img src="{d["logo"]}" style="max-height: 50px; max-width: 150px; object-fit: contain;">' if d.get("logo") else '<b style="color: #023e8a; font-size: 18px;">CASSILAB SST</b>'

                html_conteudo_os = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Ordem de Serviço - {d['funcionario']}</title>
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
                                <h2 style="margin: 0; font-size: 14px; background: #333; color: #fff; padding: 4px 10px;">ORDEM DE SERVIÇO (O.S.)</h2>
                                <small style="font-size: 11px;">Elaboração: {d['dt_elab']} | Revisão: {d['dt_rev']}</small>
                            </div>
                        </div>

                        <p style="font-size: 14px; margin-bottom: 10px;"><b>Empresa:</b> {d['empresa']}</p>
                        
                        <table class="header-tabela">
                            <tr>
                                <td><b>Nome do Colaborador:</b> {d['funcionario']}</td>
                                <td><b>Cargo:</b> {d['cargo']}</td>
                                <td><b>Setor:</b> {d['setor']}</td>
                            </tr>
                        </table>

                        <div class="secao-titulo">1. Descrição da Função / Atividades</div>
                        <div class="secao-texto">{d['descricao']}</div>

                        <div class="secao-titulo">2. Agentes Associados às Atividades (Riscos)</div>
                        <div class="secao-texto">{d['riscos']}</div>

                        <div class="secao-titulo">3. EPI's de Uso Obrigatório</div>
                        <div class="secao-texto">{d['epis']}</div>

                        <div class="secao-titulo">4. Recomendações</div>
                        <div class="secao-texto">{d['recomendacoes']}</div>

                        <div class="secao-titulo">5. Procedimentos em Caso de Acidentes</div>
                        <div class="secao-texto">{d['acidentes']}</div>

                        <div class="secao-titulo">6. Observações e Disposições</div>
                        <div class="secao-texto" style="margin-bottom: 20px;">{d['observacoes']}</div>

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

                st.components.v1.html(html_conteudo_os, height=800, scrolling=True)
        else:
            st.warning("⚠️ Nenhum funcionário cadastrado para esta empresa. Cadastre funcionários na aba 'Gestão de Funcionários' para emitir a OS.")
    else:
        st.info("ℹ️ Selecione uma empresa acima para iniciar a emissão da Ordem de Serviço.")