"""Página Streamlit del PoC de RFP: consume la API del backend y muestra el
panel de explicabilidad completo.
Spec: docs/superpowers/specs/2026-09-18-frontend-design.md
"""

import os
from uuid import uuid4

import streamlit as st

from api_client import BackendError, check_health, get_trace, process_rfp, submit_feedback
from rendering import highlight_citations
from sample_rfps import list_samples

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
FREE_TEXT_OPTION = "— texto libre —"

st.set_page_config(page_title="Algoworks RFP PoC", layout="wide")

if "pipeline_result" not in st.session_state:
    st.session_state["pipeline_result"] = None
if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}
if "rfp_id" not in st.session_state:
    st.session_state["rfp_id"] = f"rfp_{uuid4().hex[:8]}"

st.title("Algoworks RFP PoC — Panel de explicabilidad")

backend_is_up = check_health(BASE_URL)
if backend_is_up:
    st.caption("🟢 Backend conectado")
else:
    st.caption(f"🔴 Backend no disponible en {BASE_URL}")

st.header("1. RFP de entrada")

samples = list_samples()
sample_names = [FREE_TEXT_OPTION, *samples.keys()]
selected_sample = st.selectbox("RFP de ejemplo", sample_names)
default_text = samples.get(selected_sample, "")

rfp_text = st.text_area("Texto del RFP", value=default_text, height=200)
rfp_id = st.text_input("rfp_id", value=st.session_state["rfp_id"])

process_clicked = st.button("Procesar RFP", disabled=not backend_is_up)

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
                            "justification": chunk["justification"],
                        }
                        for chunk in sorted(chunks, key=lambda chunk: chunk["score"], reverse=True)
                    ],
                    use_container_width=True,
                )

            if draft:
                st.subheader("Borrador")
                st.markdown(highlight_citations(draft["text"]))
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
