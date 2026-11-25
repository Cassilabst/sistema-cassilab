import sqlite3
from datetime import datetime
import streamlit as st


# Catálogo das Normas Regulamentadoras
# Categoria: "geral" (vermelho), "especial" (azul), "setorial" (amarelo), "revogada" (cinza/riscada)
NRS_CATALOGO = [
    {"nr": "NR-01", "icone": "📋", "titulo": "Disposições Gerais e GRO", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-01-atualizada-2024.pdf"},
    {"nr": "NR-02", "icone": "🚫", "titulo": "Inspeção Prévia (Revogada)", "cat": "revogada", "revogada": True, "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras"},
    {"nr": "NR-03", "icone": "🛑", "titulo": "Embargo e Interdição", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-03-atualizada-2020.pdf"},
    {"nr": "NR-04", "icone": "🏥", "titulo": "SESMT", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-04-atualizada-2022.pdf"},
    {"nr": "NR-05", "icone": "🛡️", "titulo": "CIPA", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-05-atualizada-2023.pdf"},
    {"nr": "NR-06", "icone": "🦺", "titulo": "EPI", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-06-atualizada-2022.pdf"},
    {"nr": "NR-07", "icone": "🩺", "titulo": "PCMSO", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-07-atualizada-2022.pdf"},
    {"nr": "NR-08", "icone": "🏢", "titulo": "Edificações", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-08-atualizada.pdf"},
    {"nr": "NR-09", "icone": "🌡️", "titulo": "Avaliação e Controle Exposições Ocupacionais", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-09-atualizada-2021.pdf"},
    {"nr": "NR-10", "icone": "⚡", "titulo": "Segurança em Instalações e Serviços em Eletricidade", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-10-atualizada-2020.pdf"},
    {"nr": "NR-11", "icone": "🚜", "titulo": "Transporte, Movimentação e Armazenagem de Materiais", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-11-atualizada-2020.pdf"},
    {"nr": "NR-12", "icone": "⚙️", "titulo": "Segurança no Trabalho em Máquinas e Equipamentos", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-12-atualizada-2024.pdf"},
    {"nr": "NR-13", "icone": "🛢️", "titulo": "Caldeiras, Vasos de Pressão, Tubulações e Tanques", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-13-atualizada-2022.pdf"},
    {"nr": "NR-14", "icone": "🔥", "titulo": "Fornos", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-14-atualizada.pdf"},
    {"nr": "NR-15", "icone": "☣️", "titulo": "Atividades e Operações Insalubres", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-15-atualizada.pdf"},
    {"nr": "NR-16", "icone": "💣", "titulo": "Atividades e Operações Perigosas", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-16-atualizada-2020.pdf"},
    {"nr": "NR-17", "icone": "🪑", "titulo": "Ergonomia", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-17-atualizada-2022.pdf"},
    {"nr": "NR-18", "icone": "🏗️", "titulo": "Indústria da Construção", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-18-atualizada-2024.pdf"},
    {"nr": "NR-19", "icone": "🧨", "titulo": "Explosivos", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-19-atualizada-2020.pdf"},
    {"nr": "NR-20", "icone": "⛽", "titulo": "Inflamáveis e Combustíveis", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-20-atualizada-2024.pdf"},
    {"nr": "NR-21", "icone": "☀️", "titulo": "Trabalhos a Céu Aberto", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-21-atualizada.pdf"},
    {"nr": "NR-22", "icone": "⛏️", "titulo": "Mineração", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-22-atualizada-2022.pdf"},
    {"nr": "NR-23", "icone": "🧯", "titulo": "Proteção Contra Incêndios", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-23-atualizada.pdf"},
    {"nr": "NR-24", "icone": "🚿", "titulo": "Condições Sanitárias e de Conforto", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-24-atualizada-2022.pdf"},
    {"nr": "NR-25", "icone": "♻️", "titulo": "Resíduos Industriais", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-25-atualizada.pdf"},
    {"nr": "NR-26", "icone": "🚧", "titulo": "Sinalização de Segurança", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-26-atualizada.pdf"},
    {"nr": "NR-27", "icone": "🚫", "titulo": "Registro Profissional (Revogada)", "cat": "revogada", "revogada": True, "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras"},
    {"nr": "NR-28", "icone": "⚖️", "titulo": "Fiscalização e Penalidades", "cat": "geral", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-28-atualizada-2020.pdf"},
    {"nr": "NR-29", "icone": "⚓", "titulo": "Trabalho Portuário", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-29-atualizada-2024.pdf"},
    {"nr": "NR-30", "icone": "🚢", "titulo": "Segurança e Saúde no Trabalho Aquaviário", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-30-atualizada-2020.pdf"},
    {"nr": "NR-31", "icone": "🌾", "titulo": "Agricultura, Pecuária, Silvicultura e Aquicultura", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-31-atualizada-2022.pdf"},
    {"nr": "NR-32", "icone": "🏥", "titulo": "Segurança e Saúde no Trabalho em Serviços de Saúde", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-32-atualizada-2022.pdf"},
    {"nr": "NR-33", "icone": "🕳️", "titulo": "Segurança e Saúde em Espaços Confinados", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-33-atualizada-2022.pdf"},
    {"nr": "NR-34", "icone": "🛳️", "titulo": "Construção, Reparação e Desmonte Naval", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-34-atualizada-2024.pdf"},
    {"nr": "NR-35", "icone": "🪜", "titulo": "Trabalho em Altura", "cat": "especial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-35-atualizada-2024.pdf"},
    {"nr": "NR-36", "icone": "🥩", "titulo": "Abate e Processamento de Carnes e Derivados", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-36-atualizada.pdf"},
    {"nr": "NR-37", "icone": "🛢️", "titulo": "Segurança e Saúde em Plataformas de Petróleo", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-37-atualizada-2022.pdf"},
    {"nr": "NR-38", "icone": "🧹", "titulo": "Segurança e Saúde nas Atividades de Limpeza Urbana", "cat": "setorial", "url": "https://www.gov.br/trabalho-e-emprego/pt-br/composicao/orgaos-especificos/secretaria-de-trabalho/inspecao/seguranca-e-saude-no-trabalho/normas-regulamentadoras/nr-38-atualizada-2024.pdf"},
]

CORES_CATEGORIA = {
    "geral": {"bg": "#c0392b", "borda": "#922b21", "texto": "#ffffff"},
    "especial": {"bg": "#1f618d", "borda": "#154360", "texto": "#ffffff"},
    "setorial": {"bg": "#d4ac0d", "borda": "#9a7d0a", "texto": "#1b2631"},
    "revogada": {"bg": "#eceff1", "borda": "#90a4ae", "texto": "#546e7a"},
}


def _garantir_tabela_nrs(db_name):
    conn = sqlite3.connect(db_name, timeout=10.0)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS empresa_nrs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            nr_codigo TEXT NOT NULL,
            aplicavel INTEGER DEFAULT 0,
            atualizado_em TEXT,
            UNIQUE(empresa, nr_codigo)
        )
        """
    )
    conn.commit()
    conn.close()


def _carregar_nrs_empresa(db_name, empresa):
    _garantir_tabela_nrs(db_name)
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT nr_codigo, aplicavel FROM empresa_nrs WHERE empresa = ?",
        (empresa,),
    )
    rows = cur.fetchall()
    conn.close()
    return {nr: bool(ap) for nr, ap in rows}


def _salvar_nrs_empresa(db_name, empresa, selecionadas_set):
    _garantir_tabela_nrs(db_name)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_name, timeout=10.0)
    cur = conn.cursor()
    for item in NRS_CATALOGO:
        nr_cod = item["nr"]
        aplic = 0 if item.get("revogada") else (1 if nr_cod in selecionadas_set else 0)
        cur.execute(
            """
            INSERT INTO empresa_nrs (empresa, nr_codigo, aplicavel, atualizado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(empresa, nr_codigo) DO UPDATE SET
                aplicavel = excluded.aplicavel,
                atualizado_em = excluded.atualizado_em
            """,
            (empresa, nr_cod, aplic, agora),
        )
    conn.commit()
    conn.close()


def _render_legenda():
    st.markdown(
        """
        <div style="display:flex; flex-wrap:wrap; gap:14px; align-items:center;
                    background:#f8f9fa; padding:10px 14px; border-radius:8px;
                    border:1px solid #e0e0e0; margin-bottom:14px; font-size:13px;">
            <span><strong style="color:#c0392b;">■ Vermelho:</strong> NRs Gerais</span>
            <span><strong style="color:#1f618d;">■ Azul:</strong> NRs Especiais</span>
            <span><strong style="color:#b7950b;">■ Amarelo:</strong> NRs Setoriais</span>
            <span><strong style="color:#566573;">■ Cinza / Riscado:</strong> NR-02 e NR-27 Revogadas</span>
            <span style="color:#666;">| <em>Colorido = Aplicável à empresa | Preto e branco = Não aplicável</em></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_aba_normas(
    DB_NAME,
    is_admin=False,
    emp_usuario="",
    get_empresas=None,
    registrar_log=None,
):
    st.title("📜 Normas Regulamentadoras (NRs)")

    if is_admin and callable(get_empresas):
        empresas = get_empresas() or []
        emp_global = st.session_state.get("empresa_global", "Todas")
        if emp_global and emp_global != "Todas" and emp_global in empresas:
            empresa_alvo = emp_global
        elif empresas:
            empresa_alvo = st.selectbox(
                "🏢 Selecione a Empresa para configurar as NRs aplicáveis",
                empresas,
                key="sel_empresa_normas",
            )
        else:
            st.warning("Nenhuma empresa cadastrada.")
            return
    else:
        empresa_alvo = emp_usuario

    if not empresa_alvo:
        st.info("Selecione uma empresa para gerenciar as Normas Regulamentadoras.")
        return

    st.markdown(
        f"<h4 style='color:#2980b9; margin-top:-8px;'>🏢 Empresa: <b>{empresa_alvo}</b></h4>",
        unsafe_allow_html=True,
    )
    _render_legenda()

    state_key = f"nrs_selecionadas_{empresa_alvo}"
    if state_key not in st.session_state:
        salvas = _carregar_nrs_empresa(DB_NAME, empresa_alvo)
        st.session_state[state_key] = {
            nr for nr, ativo in salvas.items()
            if ativo and not any(x["nr"] == nr and x.get("revogada") for x in NRS_CATALOGO)
        }

    selecionadas = st.session_state[state_key]

    col_s1, col_s2, col_s3 = st.columns([0.35, 0.35, 0.30])
    with col_s1:
        st.metric("NRs Aplicáveis Selecionadas", len(selecionadas))
    with col_s2:
        if st.button("💾 Salvar Seleção da Empresa", type="primary", use_container_width=True):
            _salvar_nrs_empresa(DB_NAME, empresa_alvo, selecionadas)
            if callable(registrar_log):
                registrar_log(
                    st.session_state.get("nome_usuario", "Desconhecido"),
                    empresa_alvo,
                    f"Atualizou NRs aplicáveis ({len(selecionadas)} selecionadas)",
                )
            st.success("✅ Seleção de NRs salva para a empresa!")
    with col_s3:
        if st.button("🧹 Limpar Seleções", use_container_width=True):
            st.session_state[state_key] = set()
            st.rerun()

    st.markdown("---")

    cols_por_linha = 6
    for idx in range(0, len(NRS_CATALOGO), cols_por_linha):
        linha_itens = NRS_CATALOGO[idx : idx + cols_por_linha]
        cols = st.columns(cols_por_linha)
        for col, item in zip(cols, linha_itens):
            nr_cod = item["nr"]
            icone = item.get("icone", "📄")
            titulo = item["titulo"]
            cat = item["cat"]
            revogada = bool(item.get("revogada"))
            url_mte = item["url"]
            ativo = (nr_cod in selecionadas) and (not revogada)

            if revogada:
                bg = "#eceff1"
                borda = "#90a4ae"
                texto_cor = "#546e7a"
                filtro_css = "grayscale(100%); opacity: 0.78;"
                decoracao_titulo = "text-decoration: line-through;"
                status_tag = "REVOGADA"
            elif ativo:
                estilo = CORES_CATEGORIA.get(cat, CORES_CATEGORIA["geral"])
                bg = estilo["bg"]
                borda = estilo["borda"]
                texto_cor = estilo["texto"]
                filtro_css = "none;"
                decoracao_titulo = "none;"
                status_tag = "APLICÁVEL"
            else:
                bg = "#f2f3f4"
                borda = "#bdc3c7"
                texto_cor = "#4d5656"
                filtro_css = "grayscale(100%); opacity: 0.85;"
                decoracao_titulo = "none;"
                status_tag = "NÃO MARCADA"

            with col:
                st.markdown(
                    f"""
                    <div style="
                        background:{bg};
                        border:2px solid {borda};
                        border-radius:10px;
                        padding:10px 8px;
                        min-height:142px;
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                        filter:{filtro_css};
                        margin-bottom:6px;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:10px; font-weight:700; letter-spacing:0.4px;
                                         color:{texto_cor}; opacity:0.9;">
                                {status_tag}
                            </span>
                            <span style="font-size:20px; line-height:1;">{icone}</span>
                        </div>
                        <div style="font-size:15px; font-weight:800; color:{texto_cor};
                                    margin:2px 0; {decoracao_titulo}">
                            {nr_cod}
                        </div>
                        <div style="font-size:11px; line-height:1.25; color:{texto_cor};
                                    {decoracao_titulo}">
                            {titulo}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if revogada:
                    st.caption("🚫 Revogada")
                else:
                    label_btn = "✅ Marcada" if ativo else "Marcar"
                    if st.button(
                        label_btn,
                        key=f"btn_nr_{empresa_alvo}_{nr_cod}",
                        use_container_width=True,
                    ):
                        if ativo:
                            selecionadas.discard(nr_cod)
                        else:
                            selecionadas.add(nr_cod)
                        st.session_state[state_key] = selecionadas
                        st.rerun()

                st.markdown(
                    f"<div style='text-align:center; font-size:11px; margin-bottom:10px;'>"
                    f"<a href='{url_mte}' target='_blank' style='text-decoration:none;'>🔗 Norma MTE</a>"
                    f"</div>",
                    unsafe_allow_html=True,
                )