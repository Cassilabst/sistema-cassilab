        elif menu == "Cadastros Gerais":
            col_h1, col_h2 = st.columns([0.8, 0.2])
            with col_h1:
                st.title("⚙️ Gerenciamento de Cadastros Gerais")
            with col_h2:
                st.write("")
                if st.button("🔄 Atualizar Aba"):
                    st.rerun()

            if not is_admin:
                st.warning("🔒 Área restrita ao Administrador.")
            else:
                empresas_cadastradas = get_empresas()
                
                sub_abas_nomes = ["Cargos", "Setores", "Serviços", "Treinamentos", "EPIs"]
                sub_aba_url = st.query_params.get("sub_aba", "Cargos")
                idx_aba_inicial = sub_abas_nomes.index(sub_aba_url) if sub_aba_url in sub_abas_nomes else 0

                aba_selecionada = st.radio(
                    "Navegação de Cadastros",
                    sub_abas_nomes,
                    index=idx_aba_inicial,
                    horizontal=True,
                    key="radio_sub_abas_gerais"
                )
                st.query_params["sub_aba"] = aba_selecionada
                st.markdown("---")

        if aba_selecionada == "Cargos":
            st.subheader("Gerenciar Cargos por Empresa")
            with st.form("form_cad_cargo_unico"):
                empresa_cargo_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_cargo",
                )
                novo_cargo = st.text_input("Novo Cargo")
                btn_add_salvar_cargo = st.form_submit_button(
                    "Adicionar e Salvar Cargo"
                )
                if btn_add_salvar_cargo:
                    if empresa_cargo_sel != "Nenhuma" and novo_cargo.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        cargo_fmt = formatar_titulo(novo_cargo)
                        cursor.execute(
                            "SELECT id FROM cad_cargos WHERE empresa = ? AND cargo = ?",
                            (empresa_cargo_sel, cargo_fmt),
                        )
                        existe = cursor.fetchone()
                        if existe:
                            st.error(
                                "Este cargo já está cadastrado para a empresa"
                                f" {empresa_cargo_sel}."
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO cad_cargos (empresa, cargo) VALUES (?, ?)",
                                (empresa_cargo_sel, cargo_fmt),
                            )
                            conn.commit()
                            if "edit_cargos_tbl" in st.session_state:
                                del st.session_state["edit_cargos_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_cargo_sel,
                                f"Adicionou cargo: {cargo_fmt}",
                            )
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do cargo.")
            st.markdown("---")
            filtro_cargo_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_cargo_emp_view",
            )
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_cargos_geral = pd.read_sql(
                "SELECT id, empresa, cargo FROM cad_cargos ORDER BY empresa, cargo ASC",
                conn,
            )
            conn.close()
            if filtro_cargo_emp != "Todas as Empresas" and not df_cargos_geral.empty:
                df_cargos_geral = df_cargos_geral[
                    df_cargos_geral["empresa"].astype(str).str.strip().str.lower()
                    == str(filtro_cargo_emp).strip().lower()
                ]
            if not df_cargos_geral.empty:
                if "sel_id_cargo_geral" not in st.session_state:
                    st.session_state["sel_id_cargo_geral"] = None
                df_cargos_geral["_id_banco"] = df_cargos_geral["id"]
                df_cargos_geral["Selecionar"] = (
                    df_cargos_geral["_id_banco"]
                    == st.session_state["sel_id_cargo_geral"]
                )
                df_cargos_geral = df_cargos_geral[
                    ["Selecionar", "_id_banco", "empresa", "cargo"]
                ]
                df_cargos_ex = formatar_colunas_tabela(df_cargos_geral)
                df_cargos_ex = adicionar_numeracao(df_cargos_ex)
                edit_cargos = st.data_editor(
                    df_cargos_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_cargos_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar", required=True
                        ),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                curr_c_geral = edit_cargos[edit_cargos["Selecionar"] == True][
                    "_id_banco"
                ].tolist()
                new_c_geral = [
                    uid
                    for uid in curr_c_geral
                    if uid != st.session_state["sel_id_cargo_geral"]
                ]
                if new_c_geral:
                    st.session_state["sel_id_cargo_geral"] = new_c_geral[-1]
                    st.rerun()
                elif not curr_c_geral and st.session_state["sel_id_cargo_geral"] is not None:
                    st.session_state["sel_id_cargo_geral"] = None
                    st.rerun()
                linhas_sel_cargo = edit_cargos[edit_cargos["Selecionar"] == True]
                col_cg_1, col_cg_2 = st.columns(2)
                if col_cg_1.button(
                    "💾 Salvar Alterações na Tabela de Cargos", use_container_width=True
                ):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_cargos.iterrows():
                        c_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        c_val = row.get("Cargo", row.get("cargo"))
                        if pd.notna(e_val) and pd.notna(c_val) and str(c_val).strip():
                            if pd.notna(c_id) and str(c_id).strip() not in (
                                "",
                                "nan",
                                "None",
                            ):
                                cursor.execute(
                                    "UPDATE cad_cargos SET empresa=?, cargo=? WHERE id=?",
                                    (str(e_val).strip(), formatar_titulo(c_val), int(c_id)),
                                )
                    conn.commit()
                    conn.close()
                    if "edit_cargos_tbl" in st.session_state:
                        del st.session_state["edit_cargos_tbl"]
                    st.session_state["sel_id_cargo_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        "Atualização na tabela de cargos",
                    )
                    st.rerun()
                if col_cg_2.button(
                    "🗑️ Excluir Cargo Selecionado", use_container_width=True
                ):
                    if len(linhas_sel_cargo) == 1:
                        cargo_id_exc = int(linhas_sel_cargo.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_cargos WHERE id = ?", (cargo_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_cargos_tbl" in st.session_state:
                            del st.session_state["edit_cargos_tbl"]
                        st.session_state["sel_id_cargo_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = (
                            "🗑️ Cargo excluído com sucesso!"
                        )
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu cargo ID {cargo_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um cargo marcando o quadradinho.")

        elif aba_selecionada == "Setores":
            st.subheader("Gerenciar Setores por Empresa")
            with st.form("form_cad_setor_unico"):
                empresa_setor_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_setor",
                )
                novo_setor = st.text_input("Novo Setor")
                btn_add_salvar_setor = st.form_submit_button("Adicionar e Salvar Setor")
                if btn_add_salvar_setor:
                    if empresa_setor_sel != "Nenhuma" and novo_setor.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        setor_fmt = formatar_titulo(novo_setor)
                        cursor.execute(
                            "SELECT id FROM cad_setores WHERE empresa = ? AND setor = ?",
                            (empresa_setor_sel, setor_fmt),
                        )
                        existe = cursor.fetchone()
                        if existe:
                            st.error(f"Este setor já está cadastrado para a empresa {empresa_setor_sel}.")
                        else:
                            cursor.execute(
                                "INSERT INTO cad_setores (empresa, setor) VALUES (?, ?)",
                                (empresa_setor_sel, setor_fmt),
                            )
                            conn.commit()
                            if "edit_setores_tbl" in st.session_state:
                                del st.session_state["edit_setores_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_setor_sel,
                                f"Adicionou setor: {setor_fmt}",
                            )
                            st.rerun()
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do setor.")
            st.markdown("---")
            filtro_setor_emp = st.selectbox(
                "Filtrar por Empresa",
                ["Todas as Empresas"] + empresas_cadastradas,
                key="filtro_setor_emp_view",
            )
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_setores_geral = pd.read_sql(
                "SELECT id, empresa, setor FROM cad_setores ORDER BY empresa, setor ASC",
                conn,
            )
            conn.close()
            if filtro_setor_emp != "Todas as Empresas" and not df_setores_geral.empty:
                df_setores_geral = df_setores_geral[
                    df_setores_geral["empresa"].astype(str).str.strip().str.lower()
                    == str(filtro_setor_emp).strip().lower()
                ]
            if not df_setores_geral.empty:
                if "sel_id_setor_geral" not in st.session_state:
                    st.session_state["sel_id_setor_geral"] = None
                df_setores_geral["_id_banco"] = df_setores_geral["id"]
                df_setores_geral["Selecionar"] = (
                    df_setores_geral["_id_banco"] == st.session_state["sel_id_setor_geral"]
                )
                df_setores_geral = df_setores_geral[["Selecionar", "_id_banco", "empresa", "setor"]]
                df_setores_ex = formatar_colunas_tabela(df_setores_geral)
                df_setores_ex = adicionar_numeracao(df_setores_ex)
                edit_setores = st.data_editor(
                    df_setores_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_setores_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                curr_s_geral = edit_setores[edit_setores["Selecionar"] == True]["_id_banco"].tolist()
                new_s_geral = [
                    uid for uid in curr_s_geral if uid != st.session_state["sel_id_setor_geral"]
                ]
                if new_s_geral:
                    st.session_state["sel_id_setor_geral"] = new_s_geral[-1]
                    st.rerun()
                elif not curr_s_geral and st.session_state["sel_id_setor_geral"] is not None:
                    st.session_state["sel_id_setor_geral"] = None
                    st.rerun()
                linhas_sel_setor = edit_setores[edit_setores["Selecionar"] == True]
                col_sg_1, col_sg_2 = st.columns(2)
                if col_sg_1.button("💾 Salvar Alterações na Tabela de Setores", use_container_width=True):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_setores.iterrows():
                        s_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        s_val = row.get("Setor", row.get("setor"))
                        if pd.notna(e_val) and pd.notna(s_val) and str(s_val).strip():
                            if pd.notna(s_id) and str(s_id).strip() not in ("", "nan", "None"):
                                cursor.execute(
                                    "UPDATE cad_setores SET empresa=?, setor=? WHERE id=?",
                                    (str(e_val).strip(), formatar_titulo(s_val), int(s_id)),
                                )
                    conn.commit()
                    conn.close()
                    if "edit_setores_tbl" in st.session_state:
                        del st.session_state["edit_setores_tbl"]
                    st.session_state["sel_id_setor_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        "Atualização na tabela de setores",
                    )
                    st.rerun()
                if col_sg_2.button("🗑️ Excluir Setor Selecionado", use_container_width=True):
                    if len(linhas_sel_setor) == 1:
                        setor_id_exc = int(linhas_sel_setor.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_setores WHERE id = ?", (setor_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_setores_tbl" in st.session_state:
                            del st.session_state["edit_setores_tbl"]
                        st.session_state["sel_id_setor_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ Setor excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu setor ID {setor_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um setor marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum setor cadastrado.")

        elif aba_selecionada == "Serviços":
            st.subheader("Gerenciar Serviços Gerais do Sistema")
            with st.form("form_cad_servico_geral_unico"):
                novo_servico_geral = st.text_input("Nome do Serviço")
                btn_add_servico_geral = st.form_submit_button("Adicionar e Salvar Serviço")
                if btn_add_servico_geral:
                    if novo_servico_geral.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        cursor = conn.cursor()
                        serv_fmt = formatar_titulo(novo_servico_geral)
                        try:
                            cursor.execute(
                                "INSERT INTO cad_servicos (servico) VALUES (?)",
                                (serv_fmt,),
                            )
                            conn.commit()
                            if "edit_servicos_gerais_tbl" in st.session_state:
                                del st.session_state["edit_servicos_gerais_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                "Todas",
                                f"Adicionou serviço geral: {serv_fmt}",
                            )
                            st.rerun()
                        except:
                            st.error(f"O serviço '{serv_fmt}' já está cadastrado.")
                        conn.close()
                    else:
                        st.error("Preencha o nome do serviço.")
            st.markdown("---")
            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            df_serv_geral = pd.read_sql(
                "SELECT id, servico FROM cad_servicos ORDER BY servico ASC",
                conn,
            )
            conn.close()
            if not df_serv_geral.empty:
                if "sel_id_serv_geral" not in st.session_state:
                    st.session_state["sel_id_serv_geral"] = None
                df_serv_geral["_id_banco"] = df_serv_geral["id"]
                df_serv_geral["Selecionar"] = (
                    df_serv_geral["_id_banco"] == st.session_state["sel_id_serv_geral"]
                )
                df_serv_geral = df_serv_geral[["Selecionar", "_id_banco", "servico"]]
                df_serv_ex = formatar_colunas_tabela(df_serv_geral)
                df_serv_ex = adicionar_numeracao(df_serv_ex)
                edit_serv_geral = st.data_editor(
                    df_serv_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_servicos_gerais_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                    },
                )
                curr_sg = edit_serv_geral[edit_serv_geral["Selecionar"] == True]["_id_banco"].tolist()
                new_sg = [uid for uid in curr_sg if uid != st.session_state["sel_id_serv_geral"]]
                if new_sg:
                    st.session_state["sel_id_serv_geral"] = new_sg[-1]
                    st.rerun()
                elif not curr_sg and st.session_state["sel_id_serv_geral"] is not None:
                    st.session_state["sel_id_serv_geral"] = None
                    st.rerun()
                linhas_sel_serv_geral = edit_serv_geral[edit_serv_geral["Selecionar"] == True]
                col_svg_1, col_svg_2 = st.columns(2)
                if col_svg_1.button("💾 Salvar Alterações na Tabela de Serviços", use_container_width=True):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    for _, row in edit_serv_geral.iterrows():
                        sg_id = row.get("_id_banco", row.get("id"))
                        sg_val = row.get("Serviço Executado", row.get("servico"))
                        if pd.notna(sg_val) and str(sg_val).strip():
                            if pd.notna(sg_id) and str(sg_id).strip() not in ("", "nan", "None"):
                                try:
                                    cursor.execute(
                                        "UPDATE cad_servicos SET servico=? WHERE id=?",
                                        (formatar_titulo(sg_val), int(sg_id)),
                                    )
                                except:
                                    pass
                    conn.commit()
                    conn.close()
                    if "edit_servicos_gerais_tbl" in st.session_state:
                        del st.session_state["edit_servicos_gerais_tbl"]
                    st.session_state["sel_id_serv_geral"] = None
                    st.cache_data.clear()
                    st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                    registrar_log(
                        st.session_state.get("nome_usuario", "Administrador"),
                        "Todas",
                        "Atualização na tabela de serviços gerais",
                    )
                    st.rerun()
                if col_svg_2.button("🗑️ Excluir Serviço Selecionado", use_container_width=True):
                    if len(linhas_sel_serv_geral) == 1:
                        serv_id_exc = int(linhas_sel_serv_geral.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_servicos WHERE id = ?", (serv_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_servicos_gerais_tbl" in st.session_state:
                            del st.session_state["edit_servicos_gerais_tbl"]
                        st.session_state["sel_id_serv_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ Serviço excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu serviço geral ID {serv_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um serviço marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum serviço cadastrado.")

        elif aba_selecionada == "EPIs":
            st.subheader("Gerenciar EPIs por Empresa (com CA e Tipo)")
            with st.form("form_cad_epi_unico"):
                empresa_epi_sel = st.selectbox(
                    "Selecione a Empresa",
                    empresas_cadastradas if empresas_cadastradas else ["Nenhuma"],
                    key="sel_emp_epi_geral",
                )
                tipos_epi_lista = [
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]
                c_epi_1, c_epi_2, c_epi_3 = st.columns(3)
                novo_epi_nome = c_epi_1.text_input("Nome do EPI")
                novo_epi_ca = c_epi_2.text_input("Número do CA")
                tipo_epi_sel = c_epi_3.selectbox("Tipo / Categoria", tipos_epi_lista)
                
                btn_add_salvar_epi = c_epi_1.form_submit_button(
                    "Adicionar e Salvar EPI e CA"
                )
                if btn_add_salvar_epi:
                    if empresa_epi_sel != "Nenhuma" and novo_epi_nome.strip():
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        try:
                            conn.execute("ALTER TABLE cad_epis ADD COLUMN tipo TEXT;")
                        except:
                            pass
                            
                        try:
                            epi_fmt = formatar_titulo(novo_epi_nome)
                            conn.execute(
                                "INSERT INTO cad_epis (empresa, epi, ca, tipo) VALUES (?, ?, ?, ?)",
                                (empresa_epi_sel, epi_fmt, novo_epi_ca.strip(), tipo_epi_sel),
                            )
                            conn.commit()
                            if "edit_epis_tbl" in st.session_state:
                                del st.session_state["edit_epis_tbl"]
                            st.cache_data.clear()
                            st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                            registrar_log(
                                st.session_state.get("nome_usuario", "Administrador"),
                                empresa_epi_sel,
                                f"Adicionou EPI: {epi_fmt} (Tipo: {tipo_epi_sel})",
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao cadastrar EPI: {e}")
                        conn.close()
                    else:
                        st.error("Selecione a empresa e preencha o nome do EPI.")
                        
            st.markdown("---")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_epi_geral_emp = st.selectbox(
                    "Filtrar por Empresa",
                    ["Todas as Empresas"] + empresas_cadastradas,
                    key="filtro_epi_geral_emp_view",
                )
            with col_f2:
                tipos_epi_filtro_lista = [
                    "Todos os Tipos",
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]
                filtro_tipo_epi_sel = st.selectbox(
                    "Filtrar por Tipo de EPI",
                    tipos_epi_filtro_lista,
                    key="filtro_epi_tipo_view",
                )

            conn = sqlite_original.connect(DB_NAME, timeout=10.0)
            try:
                df_epis_geral = pd.read_sql(
                    "SELECT id, empresa, epi, ca, tipo FROM cad_epis ORDER BY empresa, epi ASC",
                    conn,
                )
            except:
                df_epis_geral = pd.read_sql(
                    "SELECT id, empresa, epi, ca FROM cad_epis ORDER BY empresa, epi ASC",
                    conn,
                )
                if "tipo" not in df_epis_geral.columns:
                    df_epis_geral["tipo"] = "Diversos"
            conn.close()

            if filtro_epi_geral_emp != "Todas as Empresas" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[
                    df_epis_geral["empresa"].astype(str).str.strip().str.lower()
                    == str(filtro_epi_geral_emp).strip().lower()
                ]

            if filtro_tipo_epi_sel != "Todos os Tipos" and not df_epis_geral.empty:
                df_epis_geral = df_epis_geral[
                    df_epis_geral["tipo"].astype(str).str.strip().str.lower()
                    == str(filtro_tipo_epi_sel).strip().lower()
                ]

            if not df_epis_geral.empty:
                if "sel_id_epi_geral" not in st.session_state:
                    st.session_state["sel_id_epi_geral"] = None
                df_epis_geral["_id_banco"] = df_epis_geral["id"]
                df_epis_geral["Selecionar"] = (
                    df_epis_geral["_id_banco"] == st.session_state["sel_id_epi_geral"]
                )
                
                cols_epi_exib = ["Selecionar", "_id_banco", "empresa"]
                if "tipo" in df_epis_geral.columns:
                    cols_epi_exib.append("tipo")
                cols_epi_exib.extend(["epi", "ca"])
                
                df_epis_geral = df_epis_geral[cols_epi_exib]

                df_epis_ex = formatar_colunas_tabela(df_epis_geral)
                df_epis_ex = adicionar_numeracao(df_epis_ex)

                tipos_epi_lista = [
                    "Calçados de Segurança",
                    "Óculos",
                    "Protetor Auricular",
                    "Trabalho em Altura",
                    "Máscaras",
                    "Respiradores",
                    "Luvas",
                    "Diversos",
                ]

                edit_epis = st.data_editor(
                    df_epis_ex,
                    hide_index=True,
                    num_rows="fixed",
                    key="edit_epis_tbl",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar", required=True
                        ),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn("Nº", disabled=True),
                        "tipo": st.column_config.SelectboxColumn(
                            "Tipo",
                            options=tipos_epi_lista,
                            required=True,
                        ),
                        "Tipo": st.column_config.SelectboxColumn(
                            "Tipo",
                            options=tipos_epi_lista,
                            required=True,
                        ),
                    },
                )
                curr_ep_geral = edit_epis[edit_epis["Selecionar"] == True][
                    "_id_banco"
                ].tolist()
                new_ep_geral = [
                    uid
                    for uid in curr_ep_geral
                    if uid != st.session_state["sel_id_epi_geral"]
                ]
                if new_ep_geral:
                    st.session_state["sel_id_epi_geral"] = new_ep_geral[-1]
                    st.rerun()
                elif not curr_ep_geral and st.session_state["sel_id_epi_geral"] is not None:
                    st.session_state["sel_id_epi_geral"] = None
                    st.rerun()

                linhas_sel_epi_geral = edit_epis[edit_epis["Selecionar"] == True]
                col_ep_1, col_ep_2 = st.columns(2)
                if col_ep_1.button(
                    "💾 Salvar Alterações na Tabela de EPIs", use_container_width=True
                ):
                    conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                    cursor = conn.cursor()
                    erro_integridade = False
                    
                    for _, row in edit_epis.iterrows():
                        epi_id = row.get("_id_banco", row.get("id"))
                        e_val = row.get("Empresa", row.get("empresa"))
                        epi_val = row.get("EPI", row.get("epi"))
                        ca_val = row.get("CA", row.get("ca"))
                        tipo_val = row.get("Tipo", row.get("tipo", "Diversos"))
                        
                        if pd.notna(e_val) and pd.notna(epi_val) and str(epi_val).strip():
                            if pd.notna(epi_id) and str(epi_id).strip() not in (
                                "",
                                "nan",
                                "None",
                            ):
                                try:
                                    cursor.execute("ALTER TABLE cad_epis ADD COLUMN tipo TEXT;")
                                except:
                                    pass
                                
                                try:
                                    cursor.execute(
                                        "UPDATE cad_epis SET empresa=?, epi=?, ca=?, tipo=? WHERE id=?",
                                        (
                                            str(e_val).strip(),
                                            formatar_titulo(epi_val),
                                            str(ca_val).strip(),
                                            str(tipo_val).strip(),
                                            int(epi_id),
                                        ),
                                    )
                                except sqlite_original.IntegrityError:
                                    erro_integridade = True
                                    st.error(f"❌ Conflito: Já existe um EPI chamado '{formatar_titulo(epi_val)}' cadastrado para a empresa '{str(e_val).strip()}'.")

                    if not erro_integridade:
                        conn.commit()
                        conn.close()
                        if "edit_epis_tbl" in st.session_state:
                            del st.session_state["edit_epis_tbl"]
                        st.session_state["sel_id_epi_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "✅ Operação salva com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            "Atualização na tabela de EPIs cadastrados",
                        )
                        st.rerun()
                    else:
                        conn.rollback()
                        conn.close()
                if col_ep_2.button(
                    "🗑️ Excluir EPI Selecionado", use_container_width=True
                ):
                    if len(linhas_sel_epi_geral) == 1:
                        epi_id_exc = int(linhas_sel_epi_geral.iloc[0]["_id_banco"])
                        conn = sqlite_original.connect(DB_NAME, timeout=10.0)
                        conn.execute("DELETE FROM cad_epis WHERE id = ?", (epi_id_exc,))
                        conn.commit()
                        conn.close()
                        if "edit_epis_tbl" in st.session_state:
                            del st.session_state["edit_epis_tbl"]
                        st.session_state["sel_id_epi_geral"] = None
                        st.cache_data.clear()
                        st.session_state["msg_sucesso"] = "🗑️ EPI excluído com sucesso!"
                        registrar_log(
                            st.session_state.get("nome_usuario", "Administrador"),
                            "Todas",
                            f"Excluiu EPI cadastrado ID {epi_id_exc}",
                        )
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione um EPI marcando o quadradinho.")
            else:
                st.info("ℹ️ Nenhum EPI cadastrado com os filtros selecionados.")
