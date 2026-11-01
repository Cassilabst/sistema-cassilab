from datetime import datetime
import pandas as pd
import plotly.express as px
import sqlite3
import streamlit as st
import streamlit.components.v1 as components


def renderizar_matriz_treinamentos(DB_NAME, empresas, registrar_log_callback):
  st.subheader("📊 Matriz de Treinamentos e Dashboard por Empresa")
  st.markdown(
      "Acompanhe os indicadores gerenciais da matriz baseada nos treinamentos"
      " registrados para a empresa."
  )

  empresa_matriz_sel = st.selectbox(
      "Selecione a Empresa para a Matriz",
      empresas if empresas else ["Nenhuma"],
      key="sel_empresa_matriz",
  )

  if empresa_matriz_sel != "Nenhuma":
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_cad_tr_all = pd.read_sql(
        "SELECT DISTINCT treinamento, carga_horaria FROM treinamentos WHERE"
        " empresa = ? ORDER BY treinamento ASC",
        conn,
        params=(empresa_matriz_sel,),
    )
    df_funcs_mat = pd.read_sql(
        "SELECT funcionario, cargo, setor, status FROM base_funcionarios WHERE"
        " empresa = ? ORDER BY setor ASC, funcionario ASC",
        conn,
        params=(empresa_matriz_sel,),
    )
    df_tr_exec = pd.read_sql(
        "SELECT * FROM treinamentos WHERE empresa = ?",
        conn,
        params=(empresa_matriz_sel,),
    )
    df_cfg_mat = pd.read_sql(
        "SELECT treinamento, carga_horaria, validade, modalidade,"
        " disponibilidade, valor FROM matriz_treinamentos_config WHERE empresa"
        " = ?",
        conn,
        params=(empresa_matriz_sel,),
    )
    df_status_mat = pd.read_sql(
        "SELECT funcionario, treinamento, obrigatoriedade FROM"
        " matriz_treinamentos_status WHERE empresa = ?",
        conn,
        params=(empresa_matriz_sel,),
    )
    conn.close()

    # Mapeamento unificado focando na coluna real do banco 'pessoas_treinadas'
    mapa_cargas_lancadas = {}
    mapa_modalidade_lancada = {}

    if not df_tr_exec.empty:
      for _, r in df_tr_exec.iterrows():
        t_nome = str(r.get("treinamento", "")).strip()
        if not t_nome:
          continue
        t_key = t_nome.lower()

        # 1. Capturar Modalidade ('pessoas_treinadas' é o nome físico na tabela do banco)
        mod_val = None
        for col_name in [
            "pessoas_treinadas",
            "modalidade",
            "tipo_treinamento",
            "tipo",
            "formato",
        ]:
          if col_name in r.index and pd.notna(r[col_name]):
            val_s = str(r[col_name]).strip()
            if val_s and val_s.lower() != t_key:
              mod_val = val_s
              break

        if mod_val:
          mapa_modalidade_lancada[t_key] = mod_val

        # 2. Capturar Carga Horária real
        carga_val = None
        for col_name in ["carga_horaria", "carga", "horaria"]:
          if col_name in r.index and pd.notna(r[col_name]):
            val_s = str(r[col_name]).strip()
            if val_s:
              carga_val = val_s
              break
        if carga_val:
          mapa_cargas_lancadas[t_key] = carga_val

    tab_config, tab_dash = st.tabs(
        ["📊 Matriz de Treinamentos", "📈 Dashboard"]
    )

    with tab_config:
      lista_todos_cursos = (
          df_cad_tr_all["treinamento"].tolist()
          if not df_cad_tr_all.empty
          else []
      )
      mapa_cargas_geral = (
          dict(
              zip(
                  df_cad_tr_all["treinamento"].str.strip().str.lower(),
                  df_cad_tr_all["carga_horaria"],
              )
          )
          if not df_cad_tr_all.empty
          else {}
      )

      st.markdown("### Matriz de Treinamentos")
      st.markdown(
          "Selecione quais treinamentos (já lançados para esta empresa)"
          " compõem a matriz e configure seus parâmetros gerais:"
      )

      if not lista_todos_cursos:
        st.warning(
            "⚠️ Nenhum treinamento foi encontrado na aba Treinamentos para"
            " esta empresa ainda. Cadastre os treinamentos da empresa na aba"
            " anterior para exibi-los aqui."
        )

      cursos_configurados_atuais = (
          df_cfg_mat["treinamento"].tolist() if not df_cfg_mat.empty else []
      )

      cursos_selecionados_matriz = st.multiselect(
          "Treinamentos da Empresa (Registrados na aba Treinamentos)",
          options=lista_todos_cursos,
          default=(
              cursos_configurados_atuais if cursos_configurados_atuais else []
          ),
          key=f"multiselect_cursos_{empresa_matriz_sel}",
      )

      if cursos_selecionados_matriz:
        dados_config_grid = []
        mapa_cfg_existente = {}
        if not df_cfg_mat.empty:
          for _, r_cfg in df_cfg_mat.iterrows():
            mapa_cfg_existente[str(r_cfg["treinamento"]).strip().lower()] = (
                r_cfg.to_dict()
            )

        for c in cursos_selecionados_matriz:
          c_key = str(c).strip().lower()
          cfg_antigo = mapa_cfg_existente.get(c_key, {})

          # PRIORIDADE ABSOLUTA PARA O DADO REAL LANCADO (MAPA), DEPOIS CONFIG ANTIGO, DEPOIS 'Presencial'
          modalidade_real = mapa_modalidade_lancada.get(c_key)
          if not modalidade_real:
            modalidade_real = cfg_antigo.get("modalidade", "Presencial")

          carga_real = (
              mapa_cargas_lancadas.get(c_key)
              or mapa_cargas_geral.get(c_key)
              or cfg_antigo.get("carga_horaria")
              or "8 horas"
          )

          dados_config_grid.append({
              "Treinamento": c,
              "Modalidade": str(modalidade_real),
              "Carga Horária": str(carga_real),
              "Validade (meses)": str(cfg_antigo.get("validade", "12 meses")),
              "Valor (R$)": float(cfg_antigo.get("valor", 0.0) or 0.0),
              "Disponibilidade": str(
                  cfg_antigo.get("disponibilidade", "Recurso Interno")
              ),
          })

        df_grid_cfg = pd.DataFrame(dados_config_grid)

        editado_cfg_cursos = st.data_editor(
            df_grid_cfg,
            key=f"editor_config_cursos_matriz_{empresa_matriz_sel}",
            hide_index=True,
            use_container_width=True,
            column_config={
                "Treinamento": st.column_config.TextColumn(
                    "Treinamento", disabled=True
                ),
                "Modalidade": st.column_config.TextColumn(
                    "Modalidade", disabled=True
                ),
                "Carga Horária": st.column_config.TextColumn(
                    "Carga Horária", disabled=True
                ),
                "Disponibilidade": st.column_config.SelectboxColumn(
                    "Disponibilidade",
                    options=["Recurso Interno", "Recursos Externo"],
                    required=True,
                ),
                "Valor (R$)": st.column_config.NumberColumn(
                    "Valor (R$)", format="R$ %.2f", min_value=0.0, step=50.0
                ),
            },
        )

        st.markdown("---")
        st.markdown("### Matriz de Treinamentos Por Funcionários")

        if not df_funcs_mat.empty:
          mapa_status_existente = {}
          if not df_status_mat.empty:
            for _, r in df_status_mat.iterrows():
              mapa_status_existente[
                  (
                      str(r["funcionario"]).strip().lower(),
                      str(r["treinamento"]).strip().lower(),
                  )
              ] = r["obrigatoriedade"]

          linhas_matriz_func = []
          for _, f_row in df_funcs_mat.iterrows():
            func_nome = f_row["funcionario"]
            func_key = str(func_nome).strip().lower()
            linha_dict = {
                "Funcionário": func_nome,
                "Cargo": f_row["cargo"],
                "Setor": f_row["setor"],
            }
            for c in cursos_selecionados_matriz:
              c_key = str(c).strip().lower()
              linha_dict[c] = mapa_status_existente.get(
                  (func_key, c_key), "Obrigatório"
              )
            linhas_matriz_func.append(linha_dict)

          df_matriz_status = pd.DataFrame(linhas_matriz_func)

          col_config_dict = {
              "Funcionário": st.column_config.TextColumn(
                  "Funcionário", disabled=True
              ),
              "Cargo": st.column_config.TextColumn("Cargo", disabled=True),
              "Setor": st.column_config.TextColumn("Setor", disabled=True),
          }
          for c in cursos_selecionados_matriz:
            col_config_dict[c] = st.column_config.SelectboxColumn(
                c, options=["Obrigatório", "N/A", "Opcional"], required=True
            )

          editado_matriz_status = st.data_editor(
              df_matriz_status,
              key=f"editor_matriz_status_func_{empresa_matriz_sel}",
              hide_index=True,
              use_container_width=True,
              column_config=col_config_dict,
          )

          # --- BOTÃO DE IMPRESSÃO ---
          html_cfg_table = df_grid_cfg.to_html(index=False)
          html_matriz_table = df_matriz_status.to_html(index=False)

          print_component_html = (
              """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <style>
                            .btn-imprimir {
                                background-color: #2e7d32;
                                color: white;
                                padding: 12px 24px;
                                border: none;
                                border-radius: 6px;
                                cursor: pointer;
                                font-size: 15px;
                                font-weight: bold;
                                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                            }
                            .btn-imprimir:hover { background-color: #1b5e20; }
                        </style>
                    </head>
                    <body style="margin: 0; padding-bottom: 10px;">
                        <button class="btn-imprimir" onclick="imprimirMatriz()">🖨️ Imprimir Matriz Completa</button>
                        <script>
                            function imprimirMatriz() {
                                var win = window.open('', '_blank');
                                win.document.write('<html><head><title>Matriz de Treinamentos - """
              + empresa_matriz_sel
              + """</title></head><body>' +
                                   '<h2 style="text-align: center;">Matriz de Treinamentos - """
              + empresa_matriz_sel
              + """</h2>' +
                                   '<h3>Parâmetros dos Treinamentos</h3>' +
                                   '"""
              + html_cfg_table.replace("\n", "").replace('"', '\\"')
              + """' +
                                   '<h3>Matriz de Treinamentos Por Funcionários</h3>' +
                                   '"""
              + html_matriz_table.replace("\n", "").replace('"', '\\"')
              + """' +
                                   '</body></html>');
                                win.document.close();
                                win.focus();
                                setTimeout(function() { win.print(); }, 400);
                            }
                        </script>
                    </body>
                    </html>
                    """
          )
          components.html(print_component_html, height=65)

          if st.button(
              "💾 Salvar Toda a Matriz de Treinamentos",
              key=f"btn_salvar_matriz_{empresa_matriz_sel}",
              use_container_width=True,
          ):
            conn = sqlite3.connect(DB_NAME, timeout=10.0)
            cursor = conn.cursor()

            for _, row in editado_cfg_cursos.iterrows():
              cursor.execute(
                  """
                                INSERT INTO matriz_treinamentos_config (empresa, treinamento, carga_horaria, validade, modalidade, disponibilidade, valor)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(empresa, treinamento) DO UPDATE SET
                                    carga_horaria = excluded.carga_horaria,
                                    validade = excluded.validade,
                                    modalidade = excluded.modalidade,
                                    disponibilidade = excluded.disponibilidade,
                                    valor = excluded.valor
                                """,
                  (
                      empresa_matriz_sel,
                      row["Treinamento"],
                      str(row["Carga Horária"]),
                      str(row["Validade (meses)"]),
                      str(row["Modalidade"]),
                      str(row["Disponibilidade"]),
                      float(row["Valor (R$)"]),
                  ),
              )

            for _, row in editado_matriz_status.iterrows():
              f_nome = row["Funcionário"]
              for c in cursos_selecionados_matriz:
                st_val = row[c]
                cursor.execute(
                    """
                                    INSERT INTO matriz_treinamentos_status (empresa, funcionario, treinamento, obrigatoriedade)
                                    VALUES (?, ?, ?, ?)
                                    ON CONFLICT(empresa, funcionario, treinamento) DO UPDATE SET
                                        obrigatoriedade = excluded.obrigatoriedade
                                    """,
                    (empresa_matriz_sel, f_nome, c, str(st_val)),
                )

            conn.commit()
            conn.close()
            st.session_state["msg_sucesso"] = (
                "✅ Matriz de Treinamentos salva com sucesso!"
            )
            if registrar_log_callback:
              registrar_log_callback(
                  st.session_state.get("nome_usuario", "Desconhecido"),
                  empresa_matriz_sel,
                  "Atualizou a Matriz de Treinamentos",
              )
            st.rerun()
        else:
          st.warning(
              "⚠️ Nenhum funcionário cadastrado para esta empresa. Cadastre"
              " funcionários na aba Gestão de Funcionários para preencher a"
              " matriz."
          )
      else:
        st.info("ℹ️ Selecione ao menos um treinamento acima para exibir a matriz.")

    with tab_dash:
      st.markdown(f"### 📈 Dashboard Gerencial - {empresa_matriz_sel}")

      if not df_tr_exec.empty and "data_realizacao" in df_tr_exec.columns:
        df_tr_exec["_dt"] = pd.to_datetime(
            df_tr_exec["data_realizacao"], dayfirst=True, errors="coerce"
        )
        df_tr_exec["_ano"] = df_tr_exec["_dt"].dt.year.astype(str)
        df_tr_exec["_mes"] = df_tr_exec["_dt"].dt.strftime("%b")
      else:
        df_tr_exec["_ano"] = str(datetime.now().year)
        df_tr_exec["_mes"] = "Jan"

      if not df_tr_exec.empty and not df_funcs_mat.empty:
        if "setor" in df_funcs_mat.columns:
          has_setor = (
              "setor" in df_tr_exec.columns
              and not df_tr_exec["setor"].isna().all()
          )
          if not has_setor:
            if "setor" in df_tr_exec.columns:
              df_tr_exec = df_tr_exec.drop(columns=["setor"])
            df_tr_exec = pd.merge(
                df_tr_exec,
                df_funcs_mat[["funcionario", "setor", "cargo"]],
                on="funcionario",
                how="left",
            )

      col_f1, col_f2, col_f3 = st.columns(3)
      anos_disp = (
          sorted(df_tr_exec["_ano"].dropna().unique().tolist())
          if not df_tr_exec.empty
          else [str(datetime.now().year)]
      )
      if str(datetime.now().year) not in anos_disp:
        anos_disp.append(str(datetime.now().year))

      ano_sel = col_f1.selectbox(
          "Ano", options=anos_disp, key=f"dash_ano_{empresa_matriz_sel}"
      )
      meses_disp = [
          "Todos",
          "Jan",
          "Fev",
          "Mar",
          "Abr",
          "Mai",
          "Jun",
          "Jul",
          "Ago",
          "Set",
          "Out",
          "Nov",
          "Dez",
      ]
      mes_sel = col_f2.selectbox(
          "Mês", options=meses_disp, key=f"dash_mes_{empresa_matriz_sel}"
      )

      lista_trein_disp = (
          sorted(df_tr_exec["treinamento"].dropna().unique().tolist())
          if not df_tr_exec.empty
          else []
      )
      trein_sel_dash = col_f3.multiselect(
          "Treinamento",
          options=lista_trein_disp,
          default=[],
          key=f"dash_trein_{empresa_matriz_sel}",
      )

      df_filtrado = df_tr_exec.copy()
      if not df_filtrado.empty:
        if "_ano" in df_filtrado.columns and ano_sel:
          df_filtrado = df_filtrado[df_filtrado["_ano"] == ano_sel]
        if mes_sel != "Todos" and "_mes" in df_filtrado.columns:
          df_filtrado = df_filtrado[df_filtrado["_mes"] == mes_sel]
        if trein_sel_dash:
          df_filtrado = df_filtrado[
              df_filtrado["treinamento"].isin(trein_sel_dash)
          ]

      qtd_atual_funcs = len(df_funcs_mat)
      qtd_funcs_treinados = (
          df_filtrado["funcionario"].nunique()
          if not df_filtrado.empty
          else 0
      )
      qtd_treinamentos_realizados = len(df_filtrado)

      m1, m2, m3 = st.columns(3)
      m1.metric("Qtd Atual Funcionários", qtd_atual_funcs)
      m2.metric("Qtd Funcionários Treinados", qtd_funcs_treinados)
      m3.metric("Qtd Treinamentos Realizados", qtd_treinamentos_realizados)

      st.markdown("---")

      g_col1, g_col2 = st.columns(2)

      with g_col1:
        st.markdown("#### Qt Mensal Treinamentos")
        if not df_filtrado.empty and "_dt" in df_filtrado.columns:
          df_mensal = (
              df_filtrado.groupby(df_filtrado["_dt"].dt.strftime("%b"))
              .size()
              .reset_index(name="Qtd")
          )
          fig_mensal = px.line(
              df_mensal,
              x="_dt",
              y="Qtd",
              markers=True,
              labels={"_dt": "Mês", "Qtd": "Quantidade"},
          )
          fig_mensal.update_layout(
              margin=dict(l=20, r=20, t=20, b=20), height=300
          )
          st.plotly_chart(fig_mensal, use_container_width=True)
        else:
          st.info("Sem dados mensais para exibir.")

      with g_col2:
        st.markdown("#### Treinamentos por Área")
        if (
            not df_filtrado.empty
            and "setor" in df_filtrado.columns
            and not df_filtrado["setor"].isna().all()
        ):
          df_area = (
              df_filtrado.groupby("setor").size().reset_index(name="Qtd")
          )
          fig_area = px.bar(
              df_area,
              x="setor",
              y="Qtd",
              labels={"setor": "Área / Setor", "Qtd": "Quantidade"},
          )
          fig_area.update_layout(
              margin=dict(l=20, r=20, t=20, b=20), height=300
          )
          st.plotly_chart(fig_area, use_container_width=True)
        else:
          st.info("Sem dados de setor para exibir.")

      g_col3, g_col4 = st.columns(2)

      with g_col3:
        st.markdown("#### Qt Funcionários Treinados - Área")
        if not df_funcs_mat.empty and "setor" in df_funcs_mat.columns:
          df_total_setor = (
              df_funcs_mat.groupby("setor")
              .size()
              .reset_index(name="Total Funcionários")
          )
          if not df_filtrado.empty and "setor" in df_filtrado.columns:
            df_treinados_setor = (
                df_filtrado.groupby("setor")["funcionario"]
                .nunique()
                .reset_index(name="Funcionários Treinados")
            )
          else:
            df_treinados_setor = pd.DataFrame(
                columns=["setor", "Funcionários Treinados"]
            )

          df_comp = pd.merge(
              df_total_setor, df_treinados_setor, on="setor", how="left"
          ).fillna(0)
          df_comp_melt = pd.melt(
              df_comp,
              id_vars=["setor"],
              value_vars=["Total Funcionários", "Funcionários Treinados"],
              var_name="Métrica",
              value_name="Quantidade",
          )

          fig_comp = px.bar(
              df_comp_melt,
              x="setor",
              y="Quantidade",
              color="Métrica",
              barmode="group",
              labels={"setor": "Área / Setor"},
          )
          fig_comp.update_layout(
              margin=dict(l=20, r=20, t=20, b=20), height=300
          )
          st.plotly_chart(fig_comp, use_container_width=True)
        else:
          st.info("Sem funcionários cadastrados para gerar comparativo.")

      with g_col4:
        st.markdown("#### TOP 5 - Treinamentos")
        if not df_filtrado.empty and "treinamento" in df_filtrado.columns:
          df_top5 = (
              df_filtrado.groupby("treinamento")
              .size()
              .reset_index(name="Qtd")
              .sort_values(by="Qtd", ascending=False)
              .head(5)
          )
          fig_top5 = px.bar(
              df_top5,
              x="Qtd",
              y="treinamento",
              orientation="h",
              labels={"treinamento": "Treinamento", "Qtd": "Quantidade"},
          )
          fig_top5.update_layout(
              margin=dict(l=20, r=20, t=20, b=20),
              height=300,
              yaxis={"categoryorder": "total ascending"},
          )
          st.plotly_chart(fig_top5, use_container_width=True)
        else:
          st.info("Nenhum treinamento para exibir no TOP 5.")
  else:
    st.info(
        "ℹ️ Selecione uma empresa para visualizar ou configurar a matriz de"
        " treinamentos."
    )