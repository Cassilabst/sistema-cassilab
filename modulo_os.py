import base64
from datetime import datetime
import json
import sqlite3
import pandas as pd
import streamlit as st


def _garantir_tabela_os(db_name):
  conn = sqlite3.connect(db_name, timeout=10.0)
  conn.execute("""
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
            recomendacoes TEXT,
            acidentes TEXT,
            observacoes TEXT,
            logo_base64 TEXT
        )
        """)
  conn.commit()
  conn.close()


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
            descricao, riscos, epis, recomendacoes, acidentes, observacoes,
            logo_base64
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def _listar_historico_os(db_name, empresa, funcionario):
  _garantir_tabela_os(db_name)
  conn = sqlite3.connect(db_name, timeout=10.0)
  df_hist = pd.read_sql(
      """
        SELECT id, revisao, dt_elab, dt_rev, data_registro, cargo, setor
        FROM ordens_servico
        WHERE LOWER(TRIM(empresa)) = LOWER(TRIM(?))
          AND LOWER(TRIM(funcionario)) = LOWER(TRIM(?))
        ORDER BY revisao DESC, id DESC
        """,
      conn,
      params=(empresa, funcionario),
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
               descricao, riscos, epis, recomendacoes, acidentes, observacoes,
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
      "recomendacoes": row[12] or "",
      "acidentes": row[13] or "",
      "observacoes": row[14] or "",
      "logo": row[15] or "",
  }


def _renderizar_html_os(d):
  rev_num = int(d.get("revisao", 0))
  rev_label = f"Rev. {rev_num:02d}"
  tag_logo = (
      f'<img src="{d["logo"]}" style="max-height: 50px; max-width: 150px;'
      ' object-fit: contain;">'
      if d.get("logo")
      else (
          '<b style="color: #023e8a; font-size: 18px;">CASSILAB SST</b>'
      )
  )

  return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Ordem de Serviço - {d['funcionario']} ({rev_label})</title>
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


def renderizar_aba_os(DB_NAME, get_empresas_func, registrar_log_callback):
  _garantir_tabela_os(DB_NAME)
  st.title("📝 Elaboração de Ordem de Serviço (OS) - Conforme NR")
  st.markdown(
      "Selecione a empresa e o funcionário abaixo. Cada emissão ou atualização"
      " salva uma **nova revisão no histórico** (sem sobrescrever versões"
      " anteriores) com a **data do calendário atual**, pronta para"
      " visualizar e imprimir em A4."
  )

  data_hoje = datetime.now().strftime("%d/%m/%Y")
  empresas = get_empresas_func()
  emp_os_sel = st.selectbox(
      "Selecione a Empresa", ["-- Selecione --"] + empresas, key="os_empresa_sel"
  )

  if emp_os_sel != "-- Selecione --":
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_funcs_os = pd.read_sql(
        "SELECT funcionario, cargo, setor FROM base_funcionarios WHERE empresa ="
        " ? ORDER BY funcionario ASC",
        conn,
        params=(emp_os_sel,),
    )
    conn.close()

    if not df_funcs_os.empty:
      lista_funcs_os = df_funcs_os["funcionario"].tolist()
      func_os_sel = st.selectbox(
          "Selecione o Funcionário",
          ["-- Selecione o Funcionário --"] + lista_funcs_os,
          key="os_func_sel",
      )

      if func_os_sel != "-- Selecione o Funcionário --":
        dados_func = df_funcs_os[df_funcs_os["funcionario"] == func_os_sel].iloc[
            0
        ]
        cargo_auto = (
            str(dados_func["cargo"]) if pd.notna(dados_func["cargo"]) else ""
        )
        setor_auto = (
            str(dados_func["setor"]) if pd.notna(dados_func["setor"]) else ""
        )

        df_hist = _listar_historico_os(DB_NAME, emp_os_sel, func_os_sel)
        ultima_os = None
        if not df_hist.empty:
          ultima_os = _buscar_os_por_id(DB_NAME, int(df_hist.iloc[0]["id"]))

        proxima_rev_preview = _proxima_revisao_os(
            DB_NAME, emp_os_sel, func_os_sel
        )
        rev_preview_str = f"Rev. {proxima_rev_preview:02d}"

        st.markdown("---")
        st.subheader(
            f"📄 Ordem de Serviço para: {func_os_sel} ({rev_preview_str} — Data"
            f" atual: {data_hoje})"
        )

        if ultima_os:
          st.caption(
              f"ℹ️ Já existem {len(df_hist)} revisão(ões) salva(s) para este"
              " colaborador. Ao gerar agora, será criada a"
              f" **{rev_preview_str}** com data **{data_hoje}**, mantendo as"
              " anteriores intactas."
          )

        val_cargo = ultima_os["cargo"] if ultima_os else cargo_auto
        val_setor = ultima_os["setor"] if ultima_os else setor_auto
        val_dt_elab = ultima_os["dt_elab"] if ultima_os else data_hoje
        val_descricao = (
            ultima_os["descricao"]
            if ultima_os
            else (
                "Manutenção preventiva e corretiva, inspeção e execução de"
                " rotinas operacionais inerentes ao cargo, seguindo"
                " rigorosamente os procedimentos de segurança da empresa e"
                " normas regulamentadoras aplicáveis."
            )
        )
        val_riscos = (
            ultima_os["riscos"]
            if ultima_os
            else (
                "Riscos Físicos - Ruído gerado nos ambientes de trabalho.\nRiscos"
                " de Acidentes - Queda de altura, ferimentos com ferramentas"
                " manuais e elétricas, choque elétrico, riscos de acidentes no"
                " deslocamento."
            )
        )
        val_epis = (
            ultima_os["epis"]
            if ultima_os
            else (
                "Uso geral: Calçado de Segurança, luvas de proteção, proteção"
                " auditiva, óculos de segurança.\nTrabalho em altura (quando"
                " aplicável): Cinto de segurança tipo paraquedista, talabarte,"
                " capacete com jugular."
            )
        )
        val_recomendacoes = (
            ultima_os["recomendacoes"]
            if ultima_os
            else (
                "Cuidados nos deslocamentos pela fábrica e setores; utilize os"
                " EPIs apenas para a finalidade a que se destinam e"
                " mantenha-os sob guarda e conservação; observe atentamente o"
                " meio ambiente de trabalho e informe condições inseguras"
                " imediatamente."
            )
        )
        val_acidentes = (
            ultima_os["acidentes"]
            if ultima_os
            else (
                "Todo e qualquer acidente de trabalho, por mais leve que seja,"
                " deverá ser comunicado imediatamente ao superior direto e ao"
                " SESMT.\nO acidente não comunicado não será considerado para"
                " efeitos legais."
            )
        )
        val_observacoes = (
            ultima_os["observacoes"]
            if ultima_os
            else (
                "Mantenha em dia seus treinamentos obrigatórios (Nrs).\nNão"
                " executar qualquer atividade sem treinamento e pleno"
                " conhecimento dos riscos.\nO não cumprimento ao disposto nesta"
                " Ordem de Serviço sujeita o trabalhador às penalidades cabíveis"
                " previstas na legislação trabalhista e normas da empresa."
            )
        )

        with st.form(f"form_edicao_os_{emp_os_sel}_{func_os_sel}"):
          logo_arquivo = st.file_uploader(
              "🖼️ Inserir Logo do Cliente (PNG, JPG)",
              type=["png", "jpg", "jpeg"],
          )

          col_h1, col_h2 = st.columns(2)
          os_empresa_nome = col_h1.text_input("Empresa", value=emp_os_sel)
          os_func_nome = col_h2.text_input(
              "Nome do Colaborador", value=func_os_sel
          )

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
              (
                  "Equipamentos de Proteção Individual fornecidos e de uso"
                  " obrigatório"
              ),
              value=val_epis,
              height=100,
          )

          st.markdown("### 4. Recomendações de Segurança")
          os_recomendacoes = st.text_area(
              "Orientações e cuidados gerais para prevenção de acidentes",
              value=val_recomendacoes,
              height=100,
          )

          st.markdown("### 5. Procedimentos em Caso de Acidentes")
          os_acidentes = st.text_area(
              "Condutas em caso de ocorrências ou incidentes",
              value=val_acidentes,
              height=100,
          )

          st.markdown("### 6. Observações e Disposições Legais")
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
          logo_base64 = ultima_os["logo"] if ultima_os else ""
          if logo_arquivo is not None:
            bytes_logo = logo_arquivo.read()
            mime = (
                "image/png"
                if logo_arquivo.type == "image/png"
                else "image/jpeg"
            )
            logo_base64 = (
                f"data:{mime};base64,{base64.b64encode(bytes_logo).decode()}"
            )

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

          st.session_state["os_gerada_data"] = payload_os

          if callable(registrar_log_callback):
            registrar_log_callback(
                st.session_state.get("nome_usuario", "Desconhecido"),
                os_empresa_nome,
                (
                    f"Gerou OS Rev. {rev_salva:02d} ({dt_salva}) para"
                    f" {os_func_nome}"
                ),
            )

          st.success(
              f"✅ Ordem de Serviço **Rev. {rev_salva:02d}** salva no sistema"
              f" em **{dt_salva}** (histórico anterior preservado)!"
          )
          st.rerun()

        # --- HISTÓRICO DE REVISÕES SALVAS PARA ESTE COLABORADOR ---
        df_hist_atual = _listar_historico_os(DB_NAME, emp_os_sel, func_os_sel)
        if not df_hist_atual.empty:
          st.markdown("---")
          st.markdown("### 📚 Histórico de Ordens de Serviço Emitidas (Revisões)")
          df_exibir_hist = df_hist_atual.copy()
          df_exibir_hist["Revisão"] = df_exibir_hist["revisao"].apply(
              lambda r: f"Rev. {int(r):02d}"
          )
          df_exibir_hist = df_exibir_hist[[
              "id",
              "Revisão",
              "dt_elab",
              "dt_rev",
              "data_registro",
              "cargo",
              "setor",
          ]].rename(
              columns={
                  "id": "ID",
                  "dt_elab": "Elaboração",
                  "dt_rev": "Data Revisão",
                  "data_registro": "Salvo em (Data/Hora)",
                  "cargo": "Cargo",
                  "setor": "Setor",
              }
          )
          st.dataframe(
              df_exibir_hist, use_container_width=True, hide_index=True
          )

          opcoes_hist = {
              f"Rev. {int(row['revisao']):02d} — Revisão: {row['dt_rev']}"
              f" (Registrado em: {row['data_registro']}) [ID {int(row['id'])}]": (
                  int(row["id"])
              )
              for _, row in df_hist_atual.iterrows()
          }
          escolha_hist = st.selectbox(
              "Selecionar revisão salva para visualizar ou imprimir",
              list(opcoes_hist.keys()),
              key=f"sel_hist_os_{emp_os_sel}_{func_os_sel}",
          )
          if st.button(
              "👁️ Visualizar / Imprimir Revisão Selecionada",
              key=f"btn_ver_hist_os_{emp_os_sel}_{func_os_sel}",
          ):
            os_carregada = _buscar_os_por_id(DB_NAME, opcoes_hist[escolha_hist])
            if os_carregada:
              st.session_state["os_gerada_data"] = os_carregada
              st.rerun()

        # --- PRÉVIA / IMPRESSÃO A4 ---
        if "os_gerada_data" in st.session_state:
          d = st.session_state["os_gerada_data"]
          if (
              d.get("empresa", "").strip().lower() == emp_os_sel.strip().lower()
              and d.get("funcionario", "").strip().lower()
              == func_os_sel.strip().lower()
          ):
            st.markdown("---")
            st.components.v1.html(
                _renderizar_html_os(d), height=800, scrolling=True
            )
    else:
      st.warning(
          "⚠️ Nenhum funcionário cadastrado para esta empresa. Cadastre"
          " funcionários na aba 'Gestão de Funcionários' para emitir a OS."
      )
  else:
    st.info(
        "ℹ️ Selecione uma empresa acima para iniciar a emissão da Ordem de"
        " Serviço."
    )
