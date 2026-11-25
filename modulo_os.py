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

    st.caption("Marque o quadradinho da Ordem de Serviço que deseja visualizar, editar ou excluir:")

    ids_marcados = []
    for _, row in df_hist.iterrows():
        os_id = int(row["id"])
        rev_str = f"Rev. {int(row['revisao']):02d}"
        func_str = str(row["funcionario"] or "")
        cargo_str = str(row["cargo"] or "-")
        setor_str = str(row["setor"] or "-")
        elab_str = str(row["dt_elab"] or "-")
        rev_dt_str = str(row["dt_rev"] or "-")
        reg_str = str(row["data_registro"] or "-")

        label_linha = (
            f"**ID {os_id}** | **{func_str}** | **{rev_str}** | "
            f"Cargo: {cargo_str} | Setor: {setor_str} | "
            f"Elab: {elab_str} | Rev: {rev_dt_str} | Salvo: {reg_str}"
        )
        marcado = st.checkbox(
            label_linha,
            value=False,
            key=f"chk_os_item_{key_prefix}_{os_id}",
        )
        if marcado:
            ids_marcados.append(os_id)

    st.markdown("")
    col_b1, col_b2, col_b3 = st.columns(3)

    with col_b1:
        if st.button("👁️ Visualizar / Imprimir", key=f"btn_ver_marc_{key_prefix}", use_container_width=True):
            if len(ids_marcados) == 1:
                os_carregada = _buscar_os_por_id(db_name, ids_marcados[0])
                if os_carregada:
                    st.session_state["os_gerada_data"] = os_carregada
                    st.rerun()
            elif len(ids_marcados) == 0:
                st.warning("Marque o quadradinho de uma OS para visualizar.")
            else:
                st.warning("Marque apenas 1 quadradinho para visualizar.")

    with col_b2:
        if st.button("✏️ Editar", key=f"btn_edit_marc_{key_prefix}", use_container_width=True):
            if len(ids_marcados) == 1:
                os_editar = _buscar_os_por_id(db_name, ids_marcados[0])
                if os_editar:
                    st.session_state["os_em_edicao"] = os_editar
                    st.session_state["os_empresa_sel"] = os_editar["empresa"]
                    st.session_state["os_func_sel"] = os_editar["funcionario"]
                    st.rerun()
            elif len(ids_marcados) == 0:
                st.warning("Marque o quadradinho de uma OS para editar.")
            else:
                st.warning("Marque apenas 1 quadradinho para editar.")

    with col_b3:
        conf_exc = st.checkbox(
            "Confirmar exclusão dos marcados",
            key=f"chk_conf_exc_{key_prefix}",
        )
        if st.button("🗑️ Excluir", key=f"btn_exc_marc_{key_prefix}", use_container_width=True):
            if not ids_marcados:
                st.warning("Marque o quadradinho da OS que deseja excluir.")
            elif not conf_exc:
                st.warning("Marque 'Confirmar exclusão dos marcados' antes de clicar em Excluir.")
            else:
                for alvo_id in ids_marcados:
                    os_alvo = _buscar_os_por_id(db_name, alvo_id)
                    _excluir_os_por_id(db_name, alvo_id)
                    if "os_gerada_data" in st.session_state and st.session_state["os_gerada_data"].get("id") == alvo_id:
                        del st.session_state["os_gerada_data"]
                    if "os_em_edicao" in st.session_state and st.session_state["os_em_edicao"].get("id") == alvo_id:
                        del st.session_state["os_em_edicao"]
                    if callable(registrar_log_callback) and os_alvo:
                        registrar_log_callback(
                            st.session_state.get("nome_usuario", "Desconhecido"),
                            os_alvo.get("empresa", ""),
                            f"Excluiu OS ID {alvo_id} (Rev. {int(os_alvo.get('revisao', 0)):02d}) de {os_alvo.get('funcionario', '')}",
                        )
                st.success(f"✅ OS(s) excluída(s) com sucesso: IDs {ids_marcados}")
                st.rerun()


def renderizar_aba_os(DB_NAME, get_empresas_func, registrar_log_callback):
    _garantir_tabela_os(DB_NAME)
    st.title("📝 Emissor de Ordem de Serviço")
    st.markdown("Emissor de Ordem de Serviço de Acordo com a NR 1")

    data_hoje = datetime.now().strftime("%d/%m/%Y")
    empresas = get_empresas_func()
    emp_os_sel = st.selectbox(
        "Selecione a Empresa", ["-- Selecione --"] + empresas, key="os_empresa_sel"
    )

    if emp_os_sel != "-- Selecione --":
        logo_cadastro_emp = _buscar_logo_empresa_cadastro(DB_NAME, emp_os_sel)

        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_funcs_os = pd.read_sql(
            "SELECT funcionario, cargo, setor FROM base_funcionarios WHERE empresa = ? ORDER BY funcionario ASC",
            conn,
            params=(emp_os_sel,),
        )
        conn.close()

        df_hist_empresa = _listar_historico_empresa_os(DB_NAME, emp_os_sel)
        _bloco_historico_os(
            df_hist_empresa,
            f"📚 Arquivo / Histórico de OSs Emitidas — {emp_os_sel}",
            f"emp_{emp_os_sel}",
            DB_NAME,
            registrar_log_callback,
        )

        if not df_funcs_os.empty:
            lista_funcs_os = df_funcs_os["funcionario"].tolist()
            func_os_sel = st.selectbox(
                "Selecione o Funcionário",
                ["-- Selecione o Funcionário --"] + lista_funcs_os,
                key="os_func_sel",
            )

            if func_os_sel != "-- Selecione o Funcionário --":
                dados_func = df_funcs_os[df_funcs_os["funcionario"] == func_os_sel].iloc[0]
                cargo_auto = str(dados_func["cargo"]) if pd.notna(dados_func["cargo"]) else ""
                setor_auto = str(dados_func["setor"]) if pd.notna(dados_func["setor"]) else ""

                df_hist_func = _listar_historico_empresa_os(DB_NAME, emp_os_sel, func_os_sel)
                ultima_os = None
                if not df_hist_func.empty:
                    ultima_os = _buscar_os_por_id(DB_NAME, int(df_hist_func.iloc[0]["id"]))

                os_edicao = st.session_state.get("os_em_edicao")
                if os_edicao and (
                    os_edicao.get("empresa", "").strip().lower() != emp_os_sel.strip().lower()
                    or os_edicao.get("funcionario", "").strip().lower() != func_os_sel.strip().lower()
                ):
                    os_edicao = None

                base_form = os_edicao or ultima_os

                proxima_rev_preview = _proxima_revisao_os(DB_NAME, emp_os_sel, func_os_sel)
                rev_preview_str = f"Rev. {proxima_rev_preview:02d}"

                st.markdown("---")
                if os_edicao:
                    st.subheader(
                        f"✏️ Editando a partir da Rev. {int(os_edicao['revisao']):02d} de {func_os_sel} → Salvará como {rev_preview_str} ({data_hoje})"
                    )
                    if st.button("Cancelar edição e voltar ao padrão", key="btn_cancelar_edicao_os"):
                        del st.session_state["os_em_edicao"]
                        st.rerun()
                else:
                    st.subheader(
                        f"📄 Ordem de Serviço para: {func_os_sel} ({rev_preview_str} — Data atual: {data_hoje})"
                    )

                if logo_cadastro_emp:
                    st.caption(f"🖼️ Logomarca da empresa **{emp_os_sel}** carregada automaticamente do cadastro.")
                else:
                    st.caption(f"ℹ️ Nenhuma logomarca cadastrada para **{emp_os_sel}** na aba de Empresas; será exibido o nome da empresa no cabeçalho (ou envie uma imagem abaixo).")

                if ultima_os and not os_edicao:
                    st.caption(
                        f"ℹ️ Já existem {len(df_hist_func)} revisão(ões) salva(s) para este colaborador. "
                        f"Ao gerar agora, será criada a **{rev_preview_str}** com data **{data_hoje}**, mantendo as anteriores intactas."
                    )

                texto_padrao_orientacoes = (
                    "- Cumprir rigorosamente as disposições legais e regulamentares sobre Segurança e Saúde no Trabalho (SST), inclusive as Ordens de Serviço expedidas pelo empregador;\n"
                    "- Realizar inspeção visual prévia nas ferramentas, máquinas, equipamentos e no local de trabalho antes de iniciar qualquer atividade;\n"
                    "- Não operar máquinas, veículos ou equipamentos sem habilitação, capacitação específica e autorização formal da empresa;\n"
                    "- Manter a organização, limpeza e sinalização da área de trabalho, respeitando as rotas de fuga e extintores de incêndio;\n"
                    "- Submeter-se aos exames médicos ocupacionais previstos no PCMSO e participar dos treinamentos obrigatórios."
                )

                val_cargo = base_form["cargo"] if base_form else cargo_auto
                val_setor = base_form["setor"] if base_form else setor_auto
                val_dt_elab = base_form["dt_elab"] if base_form else data_hoje
                val_descricao = (
                    base_form["descricao"]
                    if base_form
                    else "Manutenção preventiva e corretiva, inspeção e execução de rotinas operacionais inerentes ao cargo, seguindo rigorosamente os procedimentos de segurança da empresa e normas regulamentadoras aplicáveis."
                )
                val_riscos = (
                    base_form["riscos"]
                    if base_form
                    else "Riscos Físicos - Ruído gerado nos ambientes de trabalho.\nRiscos de Acidentes - Queda de altura, ferimentos com ferramentas manuais e elétricas, choque elétrico, riscos de acidentes no deslocamento."
                )
                val_epis = (
                    base_form["epis"]
                    if base_form
                    else "Uso geral: Calçado de Segurança, luvas de proteção, proteção auditiva, óculos de segurança.\nTrabalho em altura (quando aplicável): Cinto de segurança tipo paraquedista, talabarte, capacete com jugular."
                )
                val_orientacoes_gerais = (
                    base_form["orientacoes_gerais"]
                    if (base_form and base_form.get("orientacoes_gerais"))
                    else texto_padrao_orientacoes
                )
                val_recomendacoes = (
                    base_form["recomendacoes"]
                    if base_form
                    else "Cuidados nos deslocamentos pela fábrica e setores; utilize os EPIs apenas para a finalidade a que se destinam e mantenha-os sob guarda e conservação; observe atentamente o meio ambiente de trabalho e informe condições inseguras imediatamente."
                )
                val_acidentes = (
                    base_form["acidentes"]
                    if base_form
                    else "Todo e qualquer acidente de trabalho, por mais leve que seja, deverá ser comunicado imediatamente ao superior direto e ao SESMT.\nO acidente não comunicado não será considerado para efeitos legais."
                )
                val_observacoes = (
                    base_form["observacoes"]
                    if base_form
                    else "Mantenha em dia seus treinamentos obrigatórios (Nrs).\nNão executar qualquer atividade sem treinamento e pleno conhecimento dos riscos.\nO não cumprimento ao disposto nesta Ordem de Serviço sujeita o trabalhador às penalidades cabíveis previstas na legislação trabalhista e normas da empresa."
                )

                with st.form(f"form_edicao_os_{emp_os_sel}_{func_os_sel}"):
                    logo_arquivo = st.file_uploader(
                        "🖼️ Substituir Logo apenas nesta OS (opcional — já puxa do cadastro da empresa)",
                        type=["png", "jpg", "jpeg"],
                    )

                    col_h1, col_h2 = st.columns(2)
                    os_empresa_nome = col_h1.text_input("Empresa", value=emp_os_sel)
                    os_func_nome = col_h2.text_input("Nome do Colaborador", value=func_os_sel)

                    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                    os_cargo = col_c1.text_input("Cargo", value=val_cargo)
                    os_setor = col_c2.text_input("Setor", value=val_setor)
                    os_dt_elab = col_c3.text_input("Data Elaboração", value=val_dt_elab)
                    os_dt_rev = col_c4.text_input("Data Revisão (Calendário)", value=data_hoje)

                    st.markdown("### 1. Descrição da Atividade / Função")
                    os_descricao = st.text_area(
                        "Descrição detalhada das atividades executadas pelo colaborador",
                        value=val_descricao,
                        height=150,
                    )

                    st.markdown("### 2. Agentes Associados às Atividades (Riscos)")
                    os_riscos = st.text_area(
                        "Riscos Físicos, Químicos, Biológicos, Ergonômicos e de Acidentes",
                        value=val_riscos,
                        height=100,
                    )

                    st.markdown("### 3. EPIs de Uso Obrigatório")
                    os_epis = st.text_area(
                        "Equipamentos de Proteção Individual fornecidos e de uso obrigatório",
                        value=val_epis,
                        height=100,
                    )

                    st.markdown("### 4. Orientações Gerais e Medidas Preventivas")
                    os_orientacoes_gerais = st.text_area(
                        "Medidas de prevenção, normas internas e condutas preventivas obrigatórias",
                        value=val_orientacoes_gerais,
                        height=120,
                    )

                    st.markdown("### 5. Recomendações de Segurança")
                    os_recomendacoes = st.text_area(
                        "Orientações e cuidados gerais para prevenção de acidentes",
                        value=val_recomendacoes,
                        height=100,
                    )

                    st.markdown("### 6. Procedimentos em Caso de Acidentes")
                    os_acidentes = st.text_area(
                        "Condutas em caso de ocorrências ou incidentes",
                        value=val_acidentes,
                        height=100,
                    )

                    st.markdown("### 7. Observações e Disposições Legais")
                    os_observacoes = st.text_area(
                        "Advertências, treinamentos e penalidades",
                        value=val_observacoes,
                        height=100,
                    )

                    btn_gerar_os = st.form_submit_button(
                        f"💾 Gerar e Salvar {rev_preview_str} (Data: {data_hoje})",
                        use_container_width=True,
                    )

                if btn_gerar_os:
                    logo_base64 = (
                        logo_cadastro_emp
                        or (base_form["logo"] if base_form else "")
                    )
                    if logo_arquivo is not None:
                        bytes_logo = logo_arquivo.read()
                        mime = "image/png" if logo_arquivo.type == "image/png" else "image/jpeg"
                        logo_base64 = f"data:{mime};base64,{base64.b64encode(bytes_logo).decode()}"

                    payload_os = {
                        "empresa": os_empresa_nome,
                        "funcionario": os_func_nome,
                        "cargo": os_cargo,
                        "setor": os_setor,
                        "dt_elab": os_dt_elab or data_hoje,
                        "dt_rev": data_hoje,
                        "descricao": os_descricao,
                        "riscos": os_riscos,
                        "epis": os_epis,
                        "orientacoes_gerais": os_orientacoes_gerais,
                        "recomendacoes": os_recomendacoes,
                        "acidentes": os_acidentes,
                        "observacoes": os_observacoes,
                        "logo": logo_base64,
                    }

                    novo_id, rev_salva, dt_salva, reg_salvo = _salvar_nova_revisao_os(
                        DB_NAME, payload_os
                    )
                    payload_os["id"] = novo_id
                    payload_os["revisao"] = rev_salva
                    payload_os["dt_rev"] = dt_salva
                    payload_os["data_registro"] = reg_salvo

                    if "os_em_edicao" in st.session_state:
                        del st.session_state["os_em_edicao"]

                    st.session_state["os_gerada_data"] = payload_os

                    if callable(registrar_log_callback):
                        registrar_log_callback(
                            st.session_state.get("nome_usuario", "Desconhecido"),
                            os_empresa_nome,
                            f"Gerou OS Rev. {rev_salva:02d} ({dt_salva}) para {os_func_nome}",
                        )

                    st.success(
                        f"✅ Ordem de Serviço **Rev. {rev_salva:02d}** salva no sistema em **{dt_salva}** (histórico anterior preservado)!"
                    )
                    st.rerun()

                _bloco_historico_os(
                    df_hist_func,
                    f"📌 Revisões Salvas para {func_os_sel}",
                    f"func_{emp_os_sel}_{func_os_sel}",
                    DB_NAME,
                    registrar_log_callback,
                )

        else:
            st.warning(
                "⚠️ Nenhum funcionário cadastrado para esta empresa. Cadastre funcionários na aba 'Gestão de Funcionários' para emitir a OS."
            )

        if "os_gerada_data" in st.session_state:
            d = st.session_state["os_gerada_data"]
            if d.get("empresa", "").strip().lower() == emp_os_sel.strip().lower():
                st.markdown("---")
                st.components.v1.html(_renderizar_html_os(d), height=800, scrolling=True)
    else:
        st.info("ℹ️ Selecione uma empresa acima para iniciar a emissão ou consultar o histórico de Ordens de Serviço.")
