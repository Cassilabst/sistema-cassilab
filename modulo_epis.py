import base64
from datetime import datetime
import math
import sqlite3
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def renderizar_aba_epis(*args, **kwargs):
    # Suporte flexível para argumentos posicionais e nomeados
    DB_NAME = kwargs.get("DB_NAME") or (
        args[0] if len(args) > 0 else "cassilab_gestao.db"
    )
    is_admin = (
        kwargs.get("is_admin")
        if "is_admin" in kwargs
        else (args[1] if len(args) > 1 else False)
    )
    emp_usuario = kwargs.get("emp_usuario") or (
        args[2] if len(args) > 2 else ""
    )
    pode_lancar = (
        kwargs.get("pode_lancar")
        if "pode_lancar" in kwargs
        else (args[3] if len(args) > 3 else True)
    )
    pode_editar = (
        kwargs.get("pode_editar")
        if "pode_editar" in kwargs
        else (args[4] if len(args) > 4 else True)
    )
    pode_excluir = (
        kwargs.get("pode_excluir")
        if "pode_excluir" in kwargs
        else (args[5] if len(args) > 5 else True)
    )

    get_empresas_func = (
        kwargs.get("get_empresas_func")
        or kwargs.get("get_empresas")
        or (args[6] if len(args) > 6 else lambda: [])
    )
    validar_e_formatar_data_input_func = (
        kwargs.get("validar_e_formatar_data_input_func")
        or kwargs.get("validar_e_formatar_data_input")
        or (args[7] if len(args) > 7 else lambda x: x)
    )
    limpar_status_banco_func = (
        kwargs.get("limpar_status_banco_func")
        or kwargs.get("limpar_status_banco")
        or (args[8] if len(args) > 8 else lambda x: x)
    )
    atualizar_filtro_empresa_func = (
        kwargs.get("atualizar_filtro_empresa_func")
        or kwargs.get("atualizar_filtro_empresa")
        or (args[9] if len(args) > 9 else lambda x: None)
    )
    raw_registrar_log_func = kwargs.get("registrar_log_func") or kwargs.get(
        "registrar_log"
    ) or (args[10] if len(args) > 10 else None)
    formatar_data_br_func = (
        kwargs.get("formatar_data_br_func")
        or kwargs.get("formatar_data_br")
        or (args[11] if len(args) > 11 else lambda x: x)
    )
    raw_formatar_status_visual_func = kwargs.get(
        "formatar_status_visual_func"
    ) or kwargs.get("formatar_status_visual") or (
        args[12] if len(args) > 12 else None
    )
    formatar_colunas_func = (
        kwargs.get("formatar_colunas_func")
        or kwargs.get("formatar_colunas_tabela")
        or (args[13] if len(args) > 13 else lambda df: df)
    )
    adicionar_numeracao_func = (
        kwargs.get("adicionar_numeracao_func")
        or kwargs.get("adicionar_numeracao")
        or (args[14] if len(args) > 14 else lambda df: df)
    )
    reset_epi_selection_func = (
        kwargs.get("reset_epi_selection_func")
        or kwargs.get("reset_epi_selection")
        or (args[15] if len(args) > 15 else lambda: None)
    )
    dialog_editar_epi_func = (
        kwargs.get("dialog_editar_epi_func")
        or kwargs.get("dialog_editar_epi")
        or (args[16] if len(args) > 16 else lambda x: None)
    )

    def registrar_log_func_seguro(*l_args, **l_kwargs):
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

    def buscar_logo_empresa(db_name, nome_empresa):
        try:
            conn = sqlite3.connect(db_name, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT logo_empresa FROM empresas WHERE nome_empresa = ?",
                (nome_empresa,),
            )
            res = cursor.fetchone()
            conn.close()
            if res and res[0]:
                return f'<img src="{res[0]}" style="max-height: 50px; max-width: 180px; object-fit: contain; display: block;" />'
        except Exception:
            pass
        return '<div style="font-size: 9px; color: #666;">[ Logo da Empresa ]</div>'

    def formatar_status_visual_seguro(val, tipo="epi"):
        if pd.isna(val) or not str(val).strip():
            return "🟢 Entregue"
        v = str(val).strip()
        if "🟢" in v or "🔴" in v or "🟠" in v or "🟡" in v:
            return v
        if callable(raw_formatar_status_visual_func):
            try:
                return raw_formatar_status_visual_func(val, tipo)
            except Exception:
                try:
                    return raw_formatar_status_visual_func(val)
                except Exception:
                    pass
        v_low = v.lower()
        if "devolvido" in v_low:
            return f"🟠 {v}"
        if "substituído" in v_low or "substituido" in v_low:
            return f"🟡 {v}"
        return f"🟢 {v}"

    # DIALOG DE EDIÇÃO PROTEGIDO POR PIN DO COLABORADOR
    @st.dialog("✏️ Corrigir Lançamento de EPI (Autorização por PIN)")
    def modal_editar_registro_pin(id_registro, empresa_atual):
        conn = sqlite3.connect(DB_NAME, timeout=10.0)
        df_reg = pd.read_sql("SELECT * FROM epis WHERE id = ?", conn, params=(id_registro,))
        conn.close()

        if df_reg.empty:
            st.error("Registro não encontrado.")
            if st.button("Fechar"):
                st.rerun()
            return

        r_atual = df_reg.iloc[0]
        func_nome = r_atual["funcionario"]
        epi_atual = r_atual["epi"]
        ca_atual = r_atual["ca"]
        qtd_atual = r_atual["quantidade"]

        st.markdown(f"**Colaborador:** {func_nome}")
        st.markdown("Preencha os novos dados e solicite que o colaborador digite o seu PIN pessoal de 4 dígitos para autorizar a alteração.")

        with st.form("form_edicao_pin_epi"):
            novo_epi = st.text_input("Novo EPI", value=str(epi_atual))
            novo_ca = st.text_input("Novo CA", value=str(ca_atual))
            nova_qtd = st.number_input("Nova Quantidade", min_value=1, value=int(qtd_atual))
            
            pin_autorizacao = st.text_input("PIN de 4 dígitos do Colaborador", type="password", max_chars=4)

            btn_salvar_alt = st.form_submit_button("💾 Salvar Correção Autorizada", type="primary")
            if btn_salvar_alt:
                conn_p = sqlite3.connect(DB_NAME, timeout=10.0)
                cur_p = conn_p.cursor()
                cur_p.execute("SELECT pin_colaborador FROM base_funcionarios WHERE empresa = ? AND funcionario = ?", (empresa_atual, func_nome))
                res_p = cur_p.fetchone()
                conn_p.close()

                pin_cadastrado = str(res_p[0]).strip() if res_p and res_p[0] is not None else ""

                if not pin_cadastrado or len(pin_cadastrado) != 4:
                    st.error("❌ Este colaborador não possui um PIN de 4 dígitos cadastrado no sistema!")
                elif pin_autorizacao.strip() != pin_cadastrado:
                    st.error("❌ PIN incorreto! A correção não pode ser salva sem a autorização correta do colaborador.")
                else:
                    status_corrigido = f"Corrigido via PIN em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    conn_upd = sqlite3.connect(DB_NAME, timeout=10.0)
                    conn_upd.execute(
                        "UPDATE epis SET epi = ?, ca = ?, quantidade = ?, status = ? WHERE id = ?",
                        (novo_epi.strip(), novo_ca.strip(), int(nova_qtd), status_corrigido, id_registro)
                    )
                    conn_upd.commit()
                    conn_upd.close()

                    st.success("✅ Correção realizada e autorizada com sucesso!")
                    registrar_log_func_seguro(
                        st.session_state.get("nome_usuario", "Desconhecido"),
                        empresa_atual,
                        f"Corrigiu registro de EPI ID {id_registro} para {func_nome} com autorização por PIN",
                    )
                    st.session_state["modal_edit_epi_id"] = None
                    st.rerun()

    st.title("🦺 Controle e Ficha de EPIs")

    empresas_cad = get_empresas_func() if callable(get_empresas_func) else []

    if is_admin:
        empresa_global = st.session_state.get("empresa_global", "Todas")
        if empresa_global != "Todas":
            empresa_selecionada = empresa_global
        else:
            opcoes_emp = ["Todas"] + empresas_cad
            idx_sel = (
                opcoes_emp.index(empresa_global)
                if empresa_global in opcoes_emp
                else 0
            )
            empresa_selecionada = st.selectbox(
                "🏢 Selecione a Empresa",
                opcoes_emp,
                index=idx_sel,
                key="sel_epi_admin",
            )
            if empresa_selecionada != empresa_global:
                st.session_state["empresa_global"] = empresa_selecionada
    else:
        empresa_selecionada = emp_usuario

    if isinstance(empresa_selecionada, bool) or not empresa_selecionada:
        empresa_selecionada = "Todas"

    st.markdown(
        f"<h3 style='color: #2980b9; margin-top: -10px;'>🏢 Empresa:"
        f" <b>{empresa_selecionada}</b></h3>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df = pd.read_sql("SELECT * FROM epis", conn)

    try:
        df_cad_tipos = pd.read_sql(
            "SELECT empresa, epi, tipo FROM cad_epis", conn
        )
    except:
        df_cad_tipos = pd.DataFrame()

    conn.close()

    if not df.empty and "empresa" in df.columns:
        if not df_cad_tipos.empty:
            df["_emp_lower"] = (
                df["empresa"].astype(str).str.strip().str.lower()
            )
            df["_epi_lower"] = df["epi"].astype(str).str.strip().str.lower()

            df_cad_tipos["_emp_lower"] = (
                df_cad_tipos["empresa"].astype(str).str.strip().str.lower()
            )
            df_cad_tipos["_epi_lower"] = (
                df_cad_tipos["epi"].astype(str).str.strip().str.lower()
            )

            df = pd.merge(
                df,
                df_cad_tipos[["_emp_lower", "_epi_lower", "tipo"]],
                on=["_emp_lower", "_epi_lower"],
                how="left",
            )
            df = df.drop(columns=["_emp_lower", "_epi_lower"])

        if "tipo" not in df.columns:
            df["tipo"] = "Diversos"
        else:
            df["tipo"] = df["tipo"].fillna("Diversos")

        if is_admin and empresa_selecionada != "Todas":
            df = df[
                df["empresa"].astype(str).str.strip().str.lower()
                == str(empresa_selecionada).strip().lower()
            ]
        elif not is_admin:
            df = df[
                df["empresa"].astype(str).str.strip().str.lower()
                == str(empresa_selecionada).strip().lower()
            ]
        df = df.drop(columns=["empresa"])

    aba_lista, aba_gestao_ficha = st.tabs(
        ["📋 Lista e Gestão", "➕ Lançamentos e Ficha de EPI"]
    )

    with aba_lista:
        st.markdown("### 📋 Registros de Entrega de EPIs")
        if df.empty:
            st.info("Nenhum registro de EPI encontrado.")
        else:
            tipos_unicos_disponiveis = ["Todos os Tipos"] + sorted(
                [
                    str(t)
                    for t in df["tipo"].dropna().unique().tolist()
                    if str(t).strip()
                ]
            )
            filtro_tipo_entrega = st.selectbox(
                "Filtrar por Tipo de EPI na Listagem",
                tipos_unicos_disponiveis,
                key="filtro_tipo_entrega_lista",
            )

            df_filtrado_tipo = df.copy()
            if filtro_tipo_entrega != "Todos os Tipos":
                df_filtrado_tipo = df_filtrado_tipo[
                    df_filtrado_tipo["tipo"].astype(str).str.strip().str.lower()
                    == str(filtro_tipo_entrega).strip().lower()
                ]

            if df_filtrado_tipo.empty:
                st.info(
                    "ℹ️ Nenhum registro encontrado para este tipo de EPI."
                )
            else:
                df_edit = df_filtrado_tipo.copy()
                df_edit["_id_banco"] = (
                    df_edit["id"]
                    if "id" in df_edit.columns
                    else df_filtrado_tipo.index
                )
                if "id" in df_edit.columns:
                    df_edit = df_edit.drop(columns=["id"])

                if "sel_id_epi" not in st.session_state:
                    st.session_state["sel_id_epi"] = None

                df_edit["Selecionar"] = (
                    df_edit["_id_banco"] == st.session_state["sel_id_epi"]
                )

                cols_epi_ord = [
                    "Selecionar",
                    "_id_banco",
                    "funcionario",
                    "tipo",
                    "epi",
                    "ca",
                    "data_entrega",
                    "quantidade",
                    "status",
                ]
                df_epi_sel = df_edit[
                    [c for c in cols_epi_ord if c in df_edit.columns]
                ]

                df_fmt = (
                    formatar_colunas_func(df_epi_sel)
                    if callable(formatar_colunas_func)
                    else df_epi_sel
                )
                if "Status" in df_fmt.columns:
                    df_fmt["Status"] = df_fmt["Status"].apply(
                        lambda x: formatar_status_visual_seguro(x, "epi")
                    )
                df_fmt = (
                    adicionar_numeracao_func(df_fmt)
                    if callable(adicionar_numeracao_func)
                    else df_fmt
                )

                edit_df = st.data_editor(
                    df_fmt,
                    hide_index=True,
                    num_rows="fixed",
                    key="editor_selecao_epis",
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar", required=True, pinned=True
                        ),
                        "_id_banco": None,
                        "Nº": st.column_config.NumberColumn(
                            "Nº", disabled=True, pinned=True
                        ),
                        "funcionario": st.column_config.TextColumn(
                            "Funcionário", disabled=True, pinned=True
                        ),
                    },
                )

                linhas_marcadas = edit_df[edit_df["Selecionar"] == True][
                    "_id_banco"
                ].tolist()
                if linhas_marcadas:
                    st.session_state["sel_id_epi"] = int(linhas_marcadas[-1])
                else:
                    st.session_state["sel_id_epi"] = None

                st.write("")
                col_acao1, col_acao2 = st.columns(2)

                if pode_editar:
                    if col_acao1.button(
                        "✏️ Editar Registro Selecionado",
                        use_container_width=True,
                        key="btn_edit_epi",
                    ):
                        if st.session_state.get("sel_id_epi") is not None:
                            st.session_state["modal_edit_epi_id"] = int(
                                st.session_state["sel_id_epi"]
                            )
                            st.rerun()
                        else:
                            st.warning(
                                "⚠️ Selecione um registro marcando o"
                                " quadradinho para editar."
                            )

                if st.session_state.get("modal_edit_epi_id"):
                    id_ed = st.session_state["modal_edit_epi_id"]
                    modal_editar_registro_pin(id_ed, empresa_selecionada)

                if pode_excluir:
                    if col_acao2.button(
                        "🗑️ Excluir Registro Selecionado",
                        use_container_width=True,
                        key="btn_del_epi",
                    ):
                        if st.session_state["sel_id_epi"] is not None:
                            id_exc = int(st.session_state["sel_id_epi"])
                            conn_exc = sqlite3.connect(DB_NAME, timeout=10.0)
                            cursor_exc = conn_exc.cursor()
                            cursor_exc.execute(
                                "SELECT epi, funcionario FROM epis WHERE id ="
                                " ?",
                                (id_exc,),
                            )
                            reg_exc = cursor_exc.fetchone()
                            cursor_exc.execute(
                                "DELETE FROM epis WHERE id = ?", (id_exc,)
                            )
                            conn_exc.commit()
                            conn_exc.close()

                            st.session_state["sel_id_epi"] = None
                            if "editor_selecao_epis" in st.session_state:
                                del st.session_state["editor_selecao_epis"]
                            st.session_state["msg_sucesso"] = (
                                "🗑️ Registro de EPI excluído com sucesso!"
                            )
                            registrar_log_func_seguro(
                                st.session_state.get(
                                    "nome_usuario", "Desconhecido"
                                ),
                                empresa_selecionada
                                if empresa_selecionada != "Todas"
                                else "Geral",
                                f"Excluiu EPI ({reg_exc[0] if reg_exc else ''})"
                                f" de {reg_exc[1] if reg_exc else ''}",
                            )
                            st.rerun()
                        else:
                            st.warning(
                                "⚠️ Selecione um registro marcando o"
                                " quadradinho para excluir."
                            )

    with aba_gestao_ficha:
        st.markdown(
            "### ➕ Registrar Entrega e Gerar Ficha Individual de EPI"
        )

        if empresa_selecionada == "Todas":
            st.warning(
                "⚠️ Selecione uma empresa específica no filtro superior para"
                " realizar lançamentos e gerar fichas."
            )
        else:
            conn = sqlite3.connect(DB_NAME, timeout=10.0)

            try:
                conn.execute(
                    "ALTER TABLE base_funcionarios ADD COLUMN armario TEXT"
                )
            except Exception:
                pass
            try:
                conn.execute(
                    "ALTER TABLE base_funcionarios ADD COLUMN calcado TEXT"
                )
            except Exception:
                pass
            conn.commit()

            df_funcs = pd.read_sql(
                "SELECT funcionario, matricula, cargo, setor, data_admissao,"
                " armario, calcado FROM base_funcionarios WHERE empresa = ?",
                conn,
                params=(empresa_selecionada,),
            )
            df_cad_epis = pd.read_sql(
                "SELECT epi, ca FROM cad_epis WHERE empresa = ? ORDER BY epi"
                " ASC",
                conn,
                params=(empresa_selecionada,),
            )
            df_historico_epi = pd.read_sql(
                "SELECT epi, ca, data_entrega, quantidade, funcionario, status"
                " FROM epis WHERE empresa = ?",
                conn,
                params=(empresa_selecionada,),
            )
            conn.close()

            lista_f = (
                df_funcs["funcionario"].tolist()
                if not df_funcs.empty
                else []
            )
            lista_epis_cad = (
                df_cad_epis["epi"].tolist() if not df_cad_epis.empty else []
            )
            mapa_ca = (
                dict(zip(df_cad_epis["epi"], df_cad_epis["ca"]))
                if not df_cad_epis.empty
                else {}
            )

            if not lista_f:
                st.info(
                    "ℹ️ Nenhum funcionário cadastrado para esta empresa."
                )
            else:
                if "ultimo_epi_selecionado" not in st.session_state:
                    st.session_state["ultimo_epi_selecionado"] = None
                if "unificado_ca" not in st.session_state:
                    st.session_state["unificado_ca"] = ""

                col_l1, col_l2 = st.columns(2)
                func_escolhido = col_l1.selectbox(
                    "Funcionário", lista_f, key="unificado_func"
                )

                if lista_epis_cad:
                    epi_sel = col_l2.selectbox(
                        "EPI", lista_epis_cad, key="unificado_epi"
                    )

                    if st.session_state["ultimo_epi_selecionado"] != epi_sel:
                        st.session_state["ultimo_epi_selecionado"] = epi_sel
                        st.session_state["unificado_ca"] = str(
                            mapa_ca.get(epi_sel, "")
                        )
                        st.rerun()

                    ca_sug = st.session_state["unificado_ca"]
                else:
                    epi_sel = col_l2.text_input(
                        "EPI",
                        value="Óculos de Proteção",
                        key="unificado_epi_txt",
                    )
                    ca_sug = ""

                col_l3, col_l4, col_l5 = st.columns(3)
                ca_in = col_l3.text_input("Número do CA", key="unificado_ca")
                data_ent = col_l4.text_input(
                    "Data de Entrega",
                    value=datetime.today().strftime("%d/%m/%Y"),
                    key="unificado_data",
                )
                qtd_in = col_l5.number_input(
                    "Quantidade", min_value=1, value=1, key="unificado_qtd"
                )

                tipo_assinatura_lanc = st.radio(
                    "🔑 Forma de Validação / Assinatura",
                    [
                        (
                            "Física (Assinatura manual na ficha impressa)"
                        ),
                        (
                            "Eletrônica (Validar com PIN de 4 dígitos do"
                            " colaborador)"
                        ),
                    ],
                    key="tipo_ass_lanc_epi",
                )

                pin_informado = ""
                if "Eletrônica" in tipo_assinatura_lanc:
                    pin_informado = st.text_input(
                        "Digite o PIN (4 dígitos) do Colaborador para"
                        " Confirmar",
                        type="password",
                        max_chars=4,
                        key="pin_lanc_epi_input",
                    )

                if st.button(
                    "Salvar Entrega de EPI",
                    type="primary",
                    key="btn_salvar_epi_unif",
                ):
                    if func_escolhido and epi_sel:
                        mat_f, cargo_f, setor_f, pin_cadastrado, termo_aceito = (
                            "",
                            "",
                            "",
                            "",
                            0,
                        )

                        conn_f = sqlite3.connect(DB_NAME, timeout=10.0)
                        df_f_info = pd.read_sql(
                            "SELECT matricula, cargo, setor, pin_colaborador,"
                            " termo_adesao FROM base_funcionarios WHERE empresa"
                            " = ? AND funcionario = ?",
                            conn_f,
                            params=(empresa_selecionada, func_escolhido),
                        )
                        conn_f.close()

                        if not df_f_info.empty:
                            mat_f = df_f_info.iloc[0].get("matricula", "")
                            cargo_f = df_f_info.iloc[0].get("cargo", "")
                            setor_f = df_f_info.iloc[0].get("setor", "")
                            pin_cadastrado = str(
                                df_f_info.iloc[0].get(
                                    "pin_colaborador", ""
                                )
                            ).strip()
                            termo_aceito = int(
                                df_f_info.iloc[0].get("termo_adesao", 0) or 0
                            )

                        status_gravacao = "Entregue"
                        if "Eletrônica" in tipo_assinatura_lanc:
                            if not termo_aceito:
                                st.error(
                                    "⚠️ O colaborador selecionado ainda não"
                                    " possui o Termo de Adesão ao EPI Eletrônico"
                                    " assinado no cadastro!"
                                )
                                st.stop()
                            if (
                                pin_informado.strip() != pin_cadastrado
                                or len(pin_cadastrado) != 4
                            ):
                                st.error(
                                    "❌ PIN incorreto ou colaborador sem PIN"
                                    " de 4 dígitos cadastrado!"
                                )
                                st.stop()
                            status_gravacao = (
                                f"Assinado Eletronicamente via PIN"
                                f" ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
                            )

                        data_hora_atual_str = f"{validar_e_formatar_data_input_func(data_ent) if callable(validar_e_formatar_data_input_func) else data_ent} {datetime.now().strftime('%H:%M')}"

                        conn = sqlite3.connect(DB_NAME, timeout=10.0)
                        conn.execute(
                            """
                            INSERT INTO epis (empresa, matricula, funcionario, cargo, setor, epi, ca, data_entrega, quantidade, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                empresa_selecionada,
                                str(mat_f),
                                func_escolhido,
                                str(cargo_f),
                                str(setor_f),
                                epi_sel,
                                ca_in.strip(),
                                data_hora_atual_str,
                                int(qtd_in),
                                status_gravacao,
                            ),
                        )
                        conn.commit()
                        conn.close()
                        st.success(
                            "✅ Entrega de EPI cadastrada com sucesso!"
                        )
                        registrar_log_func_seguro(
                            st.session_state.get(
                                "nome_usuario", "Desconhecido"
                            ),
                            empresa_selecionada,
                            f"Cadastrou EPI ({epi_sel}) para"
                            f" {func_escolhido} [{status_gravacao}]",
                        )
                        st.rerun()
                    else:
                        st.error("Preencha todos os campos obrigatórios.")
                st.markdown("---")
                st.markdown(
                    "### 📄 Configuração e Geração da Ficha Individual (Paisagem)"
                )

                f_atual = (
                    df_funcs[df_funcs["funcionario"] == func_escolhido].iloc[
                        0
                    ]
                    if not df_funcs.empty
                    else {}
                )
                val_armario_salvo = str(f_atual.get("armario", "") or "")
                val_calcado_salvo = str(f_atual.get("calcado", "") or "")

                col_f_cfg1, col_f_cfg2 = st.columns(2)
                armario_num = col_f_cfg1.text_input(
                    "Armário nº (Opcional para a Ficha)",
                    value=val_armario_salvo,
                    key="ficha_armario",
                )
                calcado_num = col_f_cfg2.text_input(
                    "Calçado nº (Opcional para a Ficha)",
                    value=val_calcado_salvo,
                    key="ficha_calcado",
                )
                logo_ficha_html = buscar_logo_empresa(
                    DB_NAME, empresa_selecionada
                )

                if st.button(
                    "📄 Gerar e Exibir Ficha de EPI do Colaborador Selecionado",
                    type="primary",
                    use_container_width=True,
                    key="btn_gerar_ficha_unif",
                ):
                    if armario_num or calcado_num:
                        conn_up = sqlite3.connect(DB_NAME, timeout=10.0)
                        conn_up.execute(
                            """
                            UPDATE base_funcionarios 
                            SET armario = ?, calcado = ? 
                            WHERE empresa = ? AND funcionario = ?
                            """,
                            (
                                armario_num,
                                calcado_num,
                                empresa_selecionada,
                                func_escolhido,
                            ),
                        )
                        conn_up.commit()
                        conn_up.close()

                    f_dados = df_funcs[
                        df_funcs["funcionario"] == func_escolhido
                    ].iloc[0]
                    cargo_func = f_dados.get("cargo", "")
                    setor_func = f_dados.get("setor", "")
                    admissao_func = f_dados.get("data_admissao", "")
                    if not admissao_func or pd.isna(admissao_func):
                        admissao_func = ""

                    historico_func = (
                        df_historico_epi[
                            df_historico_epi["funcionario"]
                            .astype(str)
                            .str.strip()
                            .str.lower()
                            == str(func_escolhido).strip().lower()
                        ]
                        if not df_historico_epi.empty
                        else pd.DataFrame()
                    )

                    itens_por_pagina = 12
                    total_registros = len(historico_func)
                    total_paginas = max(
                        1, math.ceil(total_registros / itens_por_pagina)
                    )

                    html_paginas_acumulado = ""

                    for pagina_idx in range(total_paginas):
                        inicio_slice = pagina_idx * itens_por_pagina
                        fim_slice = inicio_slice + itens_por_pagina
                        fatia_historico = historico_func.iloc[
                            inicio_slice:fim_slice
                        ]

                        linhas_ficha_html = ""
                        c_reg = 0

                        for _, r_hist in fatia_historico.iterrows():
                            e_nome = str(r_hist.get("epi", ""))
                            e_quant = str(r_hist.get("quantidade", "1"))
                            e_data = str(r_hist.get("data_entrega", ""))
                            e_ca = str(r_hist.get("ca", ""))
                            e_status = str(r_hist.get("status", ""))

                            if (
                                "Assinado Eletronicamente" in e_status
                                or "PIN" in e_status
                                or "Corrigido" in e_status
                            ):
                                texto_assinatura_celula = (
                                    "<div style='font-size: 7px; color:"
                                    " #0b2545; line-height: 1.1; font-weight:"
                                    " bold; text-align: center;'>Validado"
                                    " via PIN<br>(Validade Jurídica)</div>"
                                )
                            else:
                                texto_assinatura_celula = ""

                            linhas_ficha_html += (
                                "<tr>"
                                f"<td style='padding: 3px 5px; font-size: 9px; height: 18px;'>{e_nome}</td>"
                                f"<td style='text-align: center; padding: 3px 5px; font-size: 9px; height: 18px;'>{e_quant}</td>"
                                f"<td style='text-align: center; padding: 3px 5px; font-size: 9px; height: 18px;'>{e_data}</td>"
                                f"<td style='text-align: center; padding: 2px 3px; height: 18px; vertical-align: middle;'>{texto_assinatura_celula}</td>"
                                f"<td style='text-align: center; padding: 3px 5px; font-size: 9px; height: 18px;'>{e_ca}</td>"
                                "</tr>"
                            )
                            c_reg += 1

                        while c_reg < itens_por_pagina:
                            linhas_ficha_html += (
                                "<tr>"
                                "<td style='height: 18px;'></td>"
                                "<td></td><td></td><td></td><td></td>"
                                "</tr>"
                            )
                            c_reg += 1

                        num_pagina_atual = pagina_idx + 1
                        indicador_pagina = (
                            f"<b>Página {num_pagina_atual} de"
                            f" {total_paginas}</b>"
                            if total_paginas > 1
                            else ""
                        )

                        html_paginas_acumulado += f"""
                        <div class='sheet'>
                            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #000; padding: 4px 8px;'>
                                <div>{logo_ficha_html}</div>
                                <div style='font-size: 9px; font-weight: bold;'>{indicador_pagina}</div>
                            </div>
                            <div class='cabecalho-principal-ficha'>
                                CONTROLE DE ENTREGA DE EQUIPAMENTO DE PROTEÇÃO INDIVIDUAL - E.P.I.
                            </div>
                            <table class='tabela-ficha'>
                                <tr><td colspan='3'><b>Empresa:</b> {empresa_selecionada}</td></tr>
                                <tr>
                                    <td style='width: 52%;'><b>Nome:</b> {func_escolhido}</td>
                                    <td style='width: 24%;'><b>Data de admissão:</b> {admissao_func}</td>
                                </tr>
                                <tr>
                                    <td><b>Função:</b> {cargo_func}</td>
                                    <td colspan='2'><b>Armário nº:</b> {armario_num}</td>
                                </tr>
                                <tr>
                                    <td><b>Setor:</b> {setor_func}</td>
                                    <td colspan='2'><b>Calçado nº:</b> {calcado_num}</td>
                                </tr>
                            </table>
                            <table class='tabela-itens'>
                                <thead>
                                    <tr>
                                        <th style="width: 44%;">Tipo de E.P.I.</th>
                                        <th style="width: 8%;">Quant.</th>
                                        <th style="width: 18%;">Data / Hora da Entrega</th>
                                        <th style="width: 20%;">Assinatura do Funcionário</th>
                                        <th style="width: 10%;">C.A.</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {linhas_ficha_html}
                                </tbody>
                            </table>
                            <div class='termo-legal'>
                                Declaro que recebi os EPIs acima indicados, em perfeito estado de conservação, comprometendo-me a usá-los permanentemente, zelar pela sua guarda e limpeza, e devolvê-los ao término do uso ou quando exigido. Estou ciente de que a falta de uso constitui falta grave passível de punição conforme a CLT.
                            </div>
                            <div class='assinatura-area'>
                                <div style="display: inline-block; border-top: 1px solid #000; width: 300px; padding-top: 2px;">
                                    <b>{func_escolhido}</b><br>Assinatura do Colaborador
                                </div>
                            </div>
                        </div>
                        """

                    # Criação do HTML limpo completo
                    html_conteudo_bruto = (
                        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='UTF-8'>"
                        "<title>Ficha de EPI - " + str(func_escolhido) + "</title>"
                        "<style>"
                        "@page { size: A4 landscape !important; margin: 5mm !important; }"
                        "body { font-family: Arial, sans-serif; font-size: 9px; color: #000; margin: 0; padding: 0; background-color: #fff; }"
                        ".sheet { width: 100% !important; max-width: 100% !important; margin: 0 auto 15px auto; box-sizing: border-box; border: 2px solid #000; padding: 4px; background-color: #fff; page-break-after: always; }"
                        ".tabela-ficha { width: 100%; border-collapse: collapse; }"
                        ".tabela-ficha td { border: 1px solid #000; padding: 3px 6px; vertical-align: middle; font-size: 9px; }"
                        ".cabecalho-principal-ficha { text-align: center; font-weight: bold; font-size: 10px; padding: 4px; border-bottom: 2px solid #000; }"
                        ".tabela-itens { width: 100%; border-collapse: collapse; margin-top: -1px; }"
                        ".tabela-itens th, .tabela-itens td { border: 1px solid #000; padding: 3px 5px; font-size: 9px; }"
                        ".tabela-itens th { background-color: #f2f2f2; text-align: center; font-weight: bold; }"
                        ".termo-legal { border: 1px solid #000; border-top: none; padding: 4px 6px; font-size: 7.5px; line-height: 1.15; text-align: justify; }"
                        ".assinatura-area { border: 1px solid #000; border-top: none; padding: 6px; text-align: center; font-size: 9px; }"
                        "@media print { body { -webkit-print-color-adjust: exact; } .no-print { display: none !important; } .sheet { border: 2px solid #000 !important; width: 100% !important; margin: 0 auto !important; page-break-after: always; } }"
                        "</style></head><body>"
                        + html_paginas_acumulado
                        + "</body></html>"
                    )

                    # Codificamos o HTML em Base64 para segurança na injeção por script
                    html_b64_seguro = base64.b64encode(html_conteudo_bruto.encode("utf-8")).decode("utf-8")

                    # Botão profissional com injeção limpa via Blob/document.write (Garante que nunca saia em branco)
                    trecho_botao_impressao = f"""
                    <div class='no-print' style='background: #e9ecef; padding: 10px; margin-bottom: 15px; border-radius: 6px; text-align: center;'>
                        <button onclick="
                            var win = window.open('', '_blank');
                            var htmlContent = decodeURIComponent(escape(window.atob('{html_b64_seguro}')));
                            win.document.open();
                            win.document.write(htmlContent);
                            win.document.close();
                            setTimeout(function(){ win.focus(); win.print(); }, 800);
                        " style='background-color: #28a745; color: white; border: none; padding: 10px 20px; font-size: 14px; font-weight: bold; border-radius: 4px; cursor: pointer;'>
                            🖨️ IMPRIMIR / SALVAR FICHA DE EPI (A4 PAISAGEM)
                        </button>
                        <p style='margin: 4px 0 0 0; font-size: 11px; color: #555;'>Clique para abrir a ficha completa direto na janela de impressão em A4 Paisagem.</p>
                    </div>
                    """

                    html_ficha = (
                        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='UTF-8'>"
                        "<style>"
                        "@page { size: A4 landscape !important; margin: 5mm !important; }"
                        "body { font-family: Arial, sans-serif; font-size: 9px; color: #000; margin: 0; padding: 0; background-color: #fff; }"
                        ".sheet { width: 100% !important; max-width: 100% !important; margin: 0 auto 15px auto; box-sizing: border-box; border: 2px solid #000; padding: 4px; background-color: #fff; page-break-after: always; }"
                        ".tabela-ficha { width: 100%; border-collapse: collapse; }"
                        ".tabela-ficha td { border: 1px solid #000; padding: 3px 6px; vertical-align: middle; font-size: 9px; }"
                        ".cabecalho-principal-ficha { text-align: center; font-weight: bold; font-size: 10px; padding: 4px; border-bottom: 2px solid #000; }"
                        ".tabela-itens { width: 100%; border-collapse: collapse; margin-top: -1px; }"
                        ".tabela-itens th, .tabela-itens td { border: 1px solid #000; padding: 3px 5px; font-size: 9px; }"
                        ".tabela-itens th { background-color: #f2f2f2; text-align: center; font-weight: bold; }"
                        ".termo-legal { border: 1px solid #000; border-top: none; padding: 4px 6px; font-size: 7.5px; line-height: 1.15; text-align: justify; }"
                        ".assinatura-area { border: 1px solid #000; border-top: none; padding: 6px; text-align: center; font-size: 9px; }"
                        "@media print { body { -webkit-print-color-adjust: exact; } .no-print { display: none !important; } .sheet { border: 2px solid #000 !important; width: 100% !important; margin: 0 auto !important; page-break-after: always; } }"
                        "</style></head><body>"
                        + trecho_botao_impressao
                        + html_paginas_acumulado
                        + "</body></html>"
                    )

                    # Exibe a pré-visualização completa direto na tela do sistema
                    components.html(html_ficha, height=850, scrolling=True)

    st.markdown("---")
    st.subheader("📋 Histórico de Entregas Cadastradas")
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    df_hist = pd.read_sql(
        "SELECT * FROM epis WHERE empresa = ? ORDER BY id DESC",
        conn,
        params=(empresa_selecionada,),
    )
    conn.close()

    if not df_hist.empty:
        df_hist["_id_banco"] = df_hist["id"]
        if "Selecionar" not in df_hist.columns:
            df_hist.insert(0, "Selecionar", False)

        df_hist_exib = adicionar_numeracao_func(formatar_colunas_func(df_hist))
        st.dataframe(df_hist_exib, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma entrega registrada para esta empresa.")
