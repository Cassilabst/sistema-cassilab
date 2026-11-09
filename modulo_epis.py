import base64
from datetime import datetime
import pandas as pd
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
import math


def renderizar_aba_epis(*args, **kwargs):
    # Suporte flexível para argumentos posicionais e nomeados
    DB_NAME = kwargs.get("DB_NAME") or (args[0] if len(args) > 0 else "cassilab_gestao.db")
    is_admin = kwargs.get("is_admin") if "is_admin" in kwargs else (args[1] if len(args) > 1 else False)
    emp_usuario = kwargs.get("emp_usuario") or (args[2] if len(args) > 2 else "")
    pode_lancar = kwargs.get("pode_lancar") if "pode_lancar" in kwargs else (args[3] if len(args) > 3 else True)
    pode_editar = kwargs.get("pode_editar") if "pode_editar" in kwargs else (args[4] if len(args) > 4 else True)
    pode_excluir = kwargs.get("pode_excluir") if "pode_excluir" in kwargs else (args[5] if len(args) > 5 else True)

    get_empresas_func = kwargs.get("get_empresas_func") or kwargs.get("get_empresas") or (args[6] if len(args) > 6 else lambda: [])
    validar_e_formatar_data_input_func = kwargs.get("validar_e_formatar_data_input_func") or kwargs.get("validar_e_formatar_data_input") or (args[7] if len(args) > 7 else lambda x: x)
    limpar_status_banco_func = kwargs.get("limpar_status_banco_func") or kwargs.get("limpar_status_banco") or (args[8] if len(args) > 8 else lambda x: x)
    atualizar_filtro_empresa_func = kwargs.get("atualizar_filtro_empresa_func") or kwargs.get("atualizar_filtro_empresa") or (args[9] if len(args) > 9 else lambda x: None)
    raw_registrar_log_func = kwargs.get("registrar_log_func") or kwargs.get("registrar_log") or (args[10] if len(args) > 10 else None)
    formatar_data_br_func = kwargs.get("formatar_data_br_func") or kwargs.get("formatar_data_br") or (args[11] if len(args) > 11 else lambda x: x)
    raw_formatar_status_visual_func = kwargs.get("formatar_status_visual_func") or kwargs.get("formatar_status_visual") or (args[12] if len(args) > 12 else None)
    formatar_colunas_func = kwargs.get("formatar_colunas_func") or kwargs.get("formatar_colunas_tabela") or (args[13] if len(args) > 13 else lambda df: df)
    adicionar_numeracao_func = kwargs.get("adicionar_numeracao_func") or kwargs.get("adicionar_numeracao") or (args[14] if len(args) > 14 else lambda df: df)
    reset_epi_selection_func = kwargs.get("reset_epi_selection_func") or kwargs.get("reset_epi_selection") or (args[15] if len(args) > 15 else lambda: None)
    dialog_editar_epi_func = kwargs.get("dialog_editar_epi_func") or kwargs.get("dialog_editar_epi") or (args[16] if len(args) > 16 else lambda x: None)

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
        """Busca a logomarca salva no cadastro da empresa ou retorna vazio"""
        try:
            conn = sqlite3.connect(db_name, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute("SELECT logo_empresa FROM empresas WHERE nome_empresa = ?", (nome_empresa,))
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
        df_cad_tipos = pd.read_sql("SELECT empresa, epi, tipo FROM cad_epis", conn)
    except:
        df_cad_tipos = pd.DataFrame()
        
    conn.close()

    if not df.empty and "empresa" in df.columns:
        if not df_cad_tipos.empty:
            df["_emp_lower"] = df["empresa"].astype(str).str.strip().str.lower()
            df["_epi_lower"] = df["epi"].astype(str).str.strip().str.lower()
            
            df_cad_tipos["_emp_lower"] = df_cad_tipos["empresa"].astype(str).str.strip().str.lower()
            df_cad_tipos["_epi_lower"] = df_cad_tipos["epi"].astype(str).str.strip().str.lower()
            
            df = pd.merge(
                df, 
                df_cad_tipos[["_emp_lower", "_epi_lower", "tipo"]], 
                on=["_emp_lower", "_epi_lower"], 
                how="left"
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
                [str(t) for t in df["tipo"].dropna().unique().tolist() if str(t).strip()]
            )
            filtro_tipo_entrega = st.selectbox(
                "Filtrar por Tipo de EPI na Listagem",
                tipos_unicos_disponiveis,
                key="filtro_tipo_entrega_lista"
            )

            df_filtrado_tipo = df.copy()
            if filtro_tipo_entrega != "Todos os Tipos":
                df_filtrado_tipo = df_filtrado_tipo[
                    df_filtrado_tipo["tipo"].astype(str).str.strip().str.lower()
                    == str(filtro_tipo_entrega).strip().lower()
                ]

            if df_filtrado_tipo.empty:
                st.info("ℹ️ Nenhum registro encontrado para este tipo de EPI.")
            else:
                df_edit = df_filtrado_tipo.copy()
                df_edit["_id_banco"] = (
                    df_edit["id"] if "id" in df_edit.columns else df_filtrado_tipo.index
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
                df_epi_sel = df_edit[[c for c in cols_epi_ord if c in df_edit.columns]]

                df_fmt = formatar_colunas_func(df_epi_sel) if callable(formatar_colunas_func) else df_epi_sel
                if "Status" in df_fmt.columns:
                    df_fmt["Status"] = df_fmt["Status"].apply(
                        lambda x: formatar_status_visual_seguro(x, "epi")
                    )
                df_fmt = adicionar_numeracao_func(df_fmt) if callable(adicionar_numeracao_func) else df_fmt

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
                            st.session_state["modal_edit_epi_id"] = int(st.session_state["sel_id_epi"])
                            st.rerun()
                        else:
                            st.warning("⚠️ Selecione um registro marcando o quadradinho para editar.")
                        
                if st.session_state.get("modal_edit_epi_id"):
                    id_ed = st.session_state["modal_edit_epi_id"]
                    st.session_state["modal_edit_epi_id"] = None
                    if callable(dialog_editar_epi_func):
                        dialog_editar_epi_func(id_ed)

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
                            cursor_exc.execute("SELECT epi, funcionario FROM epis WHERE id = ?", (id_exc,))
                            reg_exc = cursor_exc.fetchone()
                            cursor_exc.execute("DELETE FROM epis WHERE id = ?", (id_exc,))
                            conn_exc.commit()
                            conn_exc.close()

                            st.session_state["sel_id_epi"] = None
                            if "editor_sele
