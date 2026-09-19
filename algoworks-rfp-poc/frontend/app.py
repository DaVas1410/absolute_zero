"""Página Streamlit del PoC de RFP: consume la API del backend y muestra el
panel de explicabilidad completo.
Spec: docs/superpowers/specs/2026-09-18-frontend-design.md
"""

import html
import os
from datetime import datetime
from uuid import uuid4

import streamlit as st

from api_client import BackendError, check_health, get_trace, process_rfp, submit_feedback
from rendering import highlight_citations
from sample_rfps import list_samples

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
FREE_TEXT_OPTION = "— texto libre —"
SECTION_LABELS = {
    "experiencia_previa": "Experiencia previa",
    "capacidades_tecnicas": "Capacidades técnicas",
    "equipo": "Equipo",
}


def _section_label(section_target: str) -> str:
    return SECTION_LABELS.get(section_target, section_target.replace("_", " ").capitalize())

st.set_page_config(page_title="Algoworks RFP PoC", layout="wide")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap');

        [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stHeader"] {
            font-family: 'IBM Plex Sans', sans-serif;
        }
        h1, h2, h3, h4 { font-family: 'IBM Plex Sans', sans-serif; letter-spacing: -0.01em; }

        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #D8DCE1;
            border-radius: 4px;
            padding: 0.85rem 1rem 0.65rem;
        }
        div[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; }

        .rfp-doc {
            background: #FAF7F0;
            border: 1px solid #D8DCE1;
            border-left: 3px solid #A9772C;
            border-radius: 4px;
            padding: 2.25rem 2.75rem;
            max-width: 760px;
            margin: 0.5rem 0 1.5rem;
        }
        .rfp-doc p, .rfp-doc li {
            font-family: 'Source Serif 4', Georgia, serif;
            color: #17233D;
            line-height: 1.65;
            font-size: 1.03rem;
        }
        .rfp-doc h4 {
            font-family: 'Source Serif 4', Georgia, serif;
            color: #17233D;
            font-weight: 700;
            margin-top: 1.6rem;
        }
        .rfp-cover { border-bottom: 1px solid #D8DCE1; padding-bottom: 1.1rem; margin-bottom: 1.4rem; }
        .rfp-cover-title {
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.85rem;
            font-weight: 700;
            color: #17233D;
            margin: 0 0 0.35rem;
        }
        .rfp-cover-meta {
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.85rem;
            color: #46536B;
            margin: 0 0 0.6rem;
        }
        .rfp-badge {
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            padding: 0.15rem 0.55rem;
            border-radius: 3px;
            border: 1px solid currentColor;
        }
        .rfp-badge--verified { color: #2F6F4E; }
        .rfp-badge--flagged { color: #A23B2E; }

        .rfp-section-sources {
            font-family: 'IBM Plex Sans', sans-serif !important;
            font-size: 0.82rem;
            color: #46536B;
            margin-top: -0.4rem;
        }
        .rfp-section-sources code {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            background: transparent;
            color: #46536B;
        }

        .rfp-cite {
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 0.82em;
            padding: 0.05em 0.4em;
            border-radius: 3px;
            border: 1px solid transparent;
            cursor: help;
            white-space: nowrap;
        }
        .rfp-cite--verified { background: rgba(47, 111, 78, 0.10); border-color: rgba(47, 111, 78, 0.35); color: #2F6F4E; }
        .rfp-cite--flagged { background: rgba(162, 59, 46, 0.10); border-color: rgba(162, 59, 46, 0.35); color: #A23B2E; }
        .rfp-cite--neutral { background: rgba(169, 119, 44, 0.10); border-color: rgba(169, 119, 44, 0.35); color: #A9772C; }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_styles()

if "pipeline_result" not in st.session_state:
    st.session_state["pipeline_result"] = None
if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}
if "rfp_id" not in st.session_state:
    st.session_state["rfp_id"] = f"rfp_{uuid4().hex[:8]}"

st.title("Algoworks — Asistente de propuestas RFP")
st.caption(
    "Genera un borrador de propuesta a partir de un RFP y expone, para cada "
    "afirmación, de qué fuente proviene y por qué el sistema la consideró pertinente."
)

with st.sidebar:
    st.header("1. RFP de entrada")

    backend_is_up = check_health(BASE_URL)
    if backend_is_up:
        st.caption("🟢 Backend conectado")
    else:
        st.caption(f"🔴 Backend no disponible en {BASE_URL}")

    samples = list_samples()
    sample_names = [FREE_TEXT_OPTION, *samples.keys()]
    selected_sample = st.selectbox("RFP de ejemplo", sample_names)
    default_text = samples.get(selected_sample, "")

    rfp_text = st.text_area("Texto del RFP", value=default_text, height=200)
    rfp_id = st.text_input("rfp_id", value=st.session_state["rfp_id"])

    process_clicked = st.button(
        "Procesar RFP", disabled=not backend_is_up, use_container_width=True
    )

    if process_clicked:
        with st.spinner("Procesando RFP… (puede tardar hasta un minuto)"):
            try:
                result = process_rfp(BASE_URL, rfp_id, rfp_text)
                st.session_state["pipeline_result"] = result
                st.session_state["feedback"] = {}
            except BackendError as exc:
                st.error(f"{exc.error}: {exc.detail}")

pipeline_result = st.session_state["pipeline_result"]

if pipeline_result:
    st.header("2. Resultado")

    metrics = pipeline_result["metrics"]
    columns = st.columns(5)
    columns[0].metric("Duración total", f"{metrics['total_duration_ms'] / 1000:.1f} s")
    columns[1].metric("Tokens totales", metrics["total_tokens"]["total_tokens"])
    columns[2].metric("Costo estimado", f"${metrics['total_tokens']['estimated_cost_usd']:.4f}")
    columns[3].metric("Reintentos usados", metrics["retries_used"])
    columns[4].metric("Citas alucinadas atrapadas", metrics["hallucinated_citations_caught"])

    audit = pipeline_result["reasoning_path_audit"]
    if audit["is_consistent"]:
        st.success("✓ Camino de ejecución consistente")
    else:
        st.error(f"✗ {len(audit['issues'])} problema(s) detectado(s) en el camino de ejecución")
        for issue in audit["issues"]:
            st.markdown(f"- {issue}")

    requirements = pipeline_result["requirements"]
    retrieved = pipeline_result["retrieved"]
    drafts = pipeline_result["drafts"]
    verification = pipeline_result["verification"]

    chunk_sources: dict[str, str] = {
        chunk["chunk_id"]: chunk.get("source", "")
        for chunks in retrieved.values()
        for chunk in chunks
    }

    st.header("3. Propuesta")
    st.caption(
        "Documento consolidado que el sistema propone para este RFP. Pasá el cursor "
        "sobre una cita para ver su documento de origen; el color indica si el "
        "verificador respaldó esa sección. El detalle completo por requisito está más abajo."
    )

    proposal_sections: list[tuple[str, list[tuple[str, list[str], bool | None]]]] = []
    for requirement in requirements:
        draft = drafts.get(requirement["req_id"])
        if not draft:
            continue
        verdict = verification.get(requirement["req_id"])
        supported = verdict["supported"] if verdict else None
        section_label = _section_label(requirement["section_target"])
        entry = (draft["text"], draft.get("cited_chunks", []), supported)
        if proposal_sections and proposal_sections[-1][0] == section_label:
            proposal_sections[-1][1].append(entry)
        else:
            proposal_sections.append((section_label, [entry]))

    if proposal_sections:
        supported_count = sum(
            1 for req in requirements if (verification.get(req["req_id"]) or {}).get("supported")
        )
        total_count = len(requirements)
        badge_class = "verified" if supported_count == total_count else "flagged"
        badge_text = f"{supported_count}/{total_count} secciones verificadas"
        prepared_on = datetime.now().strftime("%d/%m/%Y")

        doc_html = ['<div class="rfp-doc">', '<div class="rfp-cover">']
        doc_html.append(
            f'<p class="rfp-cover-title">Propuesta técnica — {html.escape(pipeline_result["rfp_id"])}</p>'
        )
        doc_html.append(f'<p class="rfp-cover-meta">Preparado por Algoworks · {prepared_on}</p>')
        doc_html.append(f'<span class="rfp-badge rfp-badge--{badge_class}">{badge_text}</span>')
        doc_html.append("</div>")

        for section_label, entries in proposal_sections:
            doc_html.append(f"<h4>{html.escape(section_label)}</h4>")
            section_chunk_ids: set[str] = set()
            for text, cited_chunks, supported in entries:
                doc_html.append(
                    f"<p>{highlight_citations(text, cited_sources=chunk_sources, supported=supported)}</p>"
                )
                section_chunk_ids.update(cited_chunks)
            if section_chunk_ids:
                sources_line = ", ".join(
                    f"<code>{html.escape(cid)}</code> — "
                    f"{html.escape(chunk_sources.get(cid, 'fuente desconocida'))}"
                    for cid in sorted(section_chunk_ids)
                )
                doc_html.append(f'<p class="rfp-section-sources">Fuentes: {sources_line}</p>')

        doc_html.append("</div>")
        st.markdown("\n".join(doc_html), unsafe_allow_html=True)

        export_lines = [
            f"# Propuesta técnica — {pipeline_result['rfp_id']}",
            f"_Preparado por Algoworks · {prepared_on} · {badge_text}_",
            "",
        ]
        for section_label, entries in proposal_sections:
            export_lines.append(f"## {section_label}")
            section_chunk_ids = set()
            for text, cited_chunks, _ in entries:
                export_lines.append("")
                export_lines.append(highlight_citations(text))
                section_chunk_ids.update(cited_chunks)
            if section_chunk_ids:
                export_lines.append("")
                export_lines.append(
                    "Fuentes: "
                    + ", ".join(
                        f"{cid} — {chunk_sources.get(cid, 'fuente desconocida')}"
                        for cid in sorted(section_chunk_ids)
                    )
                )
            export_lines.append("")

        st.download_button(
            "Descargar propuesta (.md)",
            data="\n".join(export_lines),
            file_name=f"{pipeline_result['rfp_id']}_propuesta.md",
            mime="text/markdown",
        )
    else:
        st.info("Todavía no hay borradores generados para esta RFP.")

    st.header("4. Panel de explicabilidad (detalle por requisito)")

    for index, requirement in enumerate(requirements):
        req_id = requirement["req_id"]
        draft = drafts.get(req_id)
        verdict = verification.get(req_id)
        feedback = st.session_state["feedback"].get(req_id)

        title = f"{requirement['section_target']} — {requirement['text'][:80]}…"
        if feedback is True:
            title = f"✓ Aceptado | {title}"
        elif feedback is False:
            title = f"✗ Rechazado | {title}"

        with st.expander(title, expanded=(index == 0)):
            st.markdown(f"**Requisito completo:** {requirement['text']}")
            st.caption(f"section_target: {requirement['section_target']}")

            st.subheader("Chunks recuperados")
            chunks = retrieved.get(req_id, [])
            if chunks:
                st.dataframe(
                    [
                        {
                            "chunk_id": chunk["chunk_id"],
                            "score": chunk["score"],
                            "source": chunk.get("source", ""),
                            "justification": chunk["justification"],
                        }
                        for chunk in sorted(chunks, key=lambda chunk: chunk["score"], reverse=True)
                    ],
                    use_container_width=True,
                )

            if draft:
                st.subheader("Borrador")
                st.markdown(
                    highlight_citations(
                        draft["text"],
                        cited_sources=chunk_sources,
                        supported=verdict["supported"] if verdict else None,
                    ),
                    unsafe_allow_html=True,
                )
                st.caption(f"Por qué el modelo citó estos fragmentos: {draft.get('reasoning', '')}")

                citation_similarities = draft.get("citation_similarities", [])
                if citation_similarities:
                    st.markdown(f"**Similitud general:** {draft.get('overall_similarity', 0.0):.2f}")
                    for citation in citation_similarities:
                        st.progress(
                            min(max(citation["similarity"], 0.0), 1.0),
                            text=f"{citation['chunk_id']}: {citation['similarity']:.2f}",
                        )

            if verdict:
                st.subheader("Veredicto del verificador")
                if verdict["supported"]:
                    st.success(f"Soportado (confianza: {verdict['confidence']:.2f})")
                else:
                    st.error(f"No soportado (confianza: {verdict['confidence']:.2f})")
                st.caption(f"Reintentos usados: {verdict.get('retries_used', 0)}")
                st.caption(verdict.get("reasoning", ""))
                for issue in verdict.get("issues", []):
                    st.markdown(f"- {issue}")

            accept_col, reject_col = st.columns(2)
            if accept_col.button("Aceptar", key=f"accept_{req_id}"):
                try:
                    submit_feedback(BASE_URL, req_id, True)
                    st.session_state["feedback"][req_id] = True
                    st.rerun()
                except BackendError as exc:
                    st.warning(f"No se pudo registrar el feedback: {exc.detail}")
            if reject_col.button("Rechazar", key=f"reject_{req_id}"):
                try:
                    submit_feedback(BASE_URL, req_id, False)
                    st.session_state["feedback"][req_id] = False
                    st.rerun()
                except BackendError as exc:
                    st.warning(f"No se pudo registrar el feedback: {exc.detail}")

    with st.expander("Ver trace log completo (trazabilidad técnica)", expanded=False):
        trace_log = pipeline_result["trace_log"]
        st.dataframe(
            [
                {
                    "node": event["node"],
                    "duration_ms": event.get("duration_ms", 0.0),
                    "tokens": (event.get("tokens") or {}).get("total_tokens", 0),
                    "reasoning": event["reasoning"],
                }
                for event in trace_log
            ],
            use_container_width=True,
        )
        if st.button("Refrescar trace desde el backend"):
            try:
                refreshed = get_trace(BASE_URL, pipeline_result["rfp_id"])
                st.session_state["pipeline_result"]["trace_log"] = refreshed
                st.rerun()
            except BackendError as exc:
                st.warning(f"No se pudo refrescar el trace: {exc.detail}")
