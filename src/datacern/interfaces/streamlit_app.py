"""DataCern Streamlit web interface.

Run locally:
    datacern-web
    # or: streamlit run src/datacern/interfaces/streamlit_app.py

Then open the printed URL (default http://localhost:8501).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Fallback: allow `streamlit run src/datacern/interfaces/streamlit_app.py`
# without an installed package by adding src/ to sys.path. A proper
# `pip install -e .` makes this unnecessary.
_SRC = Path(__file__).resolve().parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402

from datacern import __version__  # noqa: E402
from datacern.config import settings as config  # noqa: E402
from datacern.reports.generator import ReportGenerator  # noqa: E402

st.set_page_config(page_title=f"DataCern {__version__}", page_icon="📊", layout="wide")

st.title("📊 DataCern — evidence-grounded reports")
st.caption(
    "Upload a CSV or PDF, ask a question, and get a professional report with "
    "auto-generated charts — powered by RAG (Chroma + Gemini/Groq/OpenRouter/OpenAI failover)."
)

# ------------------------------------------------------------------ inputs
with st.sidebar:
    st.header("Settings")
    st.caption(f"LLM preference: `{config.LLM_PROVIDER_PREFERENCE}`")
    _has_gemini = bool(config.GEMINI_API_KEY)
    _has_groq = bool(config.GROQ_API_KEY)
    _has_openrouter = bool(config.OPENROUTER_API_KEY)
    _has_openai = bool(config.OPENAI_API_KEY)
    st.write(f"{'✅' if _has_gemini else '❌'} Gemini API key")
    st.write(f"{'✅' if _has_groq else '❌'} Groq API key (`llama-3.1-8b-instant`)")
    st.write(f"{'✅' if _has_openrouter else '❌'} OpenRouter API key (`llama-3.1-8b:free`)")
    st.write(f"{'✅' if _has_openai else '❌'} OpenAI API key")
    if not (_has_gemini or _has_groq or _has_openrouter or _has_openai):
        st.warning(
            "No API key configured. Locally, set keys in `.env`; on "
            "Streamlit Community Cloud, add them under App settings → Secrets."
        )

uploaded = st.file_uploader("Choose a CSV or PDF file", type=["csv", "pdf"])
query = st.text_input(
    "What should the report cover?",
    value="Analyze revenue by region and product; identify top and bottom performers.",
)
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    want_pdf = st.checkbox("Export PDF", value=False)
with col_btn2:
    want_pptx = st.checkbox("Export PPTX", value=False)
with col_btn3:
    generate = st.button("Generate Report", type="primary")

# ------------------------------------------------------------------ run
if generate:
    if uploaded is None:
        st.warning("Please upload a file first.")
    elif not query.strip():
        st.warning("Please enter a query.")
    else:
        suffix = Path(uploaded.name).suffix.lower()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name

            with st.spinner(
                "Generating report (indexing → retrieval → analysis → LLM → charts). "
                "This can take up to a minute..."
            ):
                generator = ReportGenerator()
                result = generator.generate(
                    tmp_path,
                    query.strip(),
                    original_filename=uploaded.name,
                    export_pdf_=want_pdf,
                    export_pptx_=want_pptx,
                )

            st.subheader("Report")
            st.markdown(result["report"])

            if result.get("warnings"):
                for warning in result["warnings"]:
                    st.warning(warning)

            if result["charts"]:
                st.subheader("Charts")
                cols = st.columns(2)
                for i, chart in enumerate(result["charts"]):
                    with cols[i % 2]:
                        st.image(chart, caption=f"Chart {i + 1}", use_container_width=True)
            else:
                st.info("No charts produced (input may be a PDF without tabular data).")

            with st.expander("Key figures & anomaly brief (deterministic)"):
                st.text(result["insights"])

            with st.expander("Retrieved context (RAG)"):
                st.text(result["context"])

            if result.get("exec_detail"):
                with st.expander("Chart code execution details"):
                    d = result["exec_detail"]
                    st.write(
                        f"success={d.get('success')} images={len(d.get('images') or [])} "
                        f"elapsed={d.get('elapsed', 0):.2f}s"
                    )
                    if d.get("error"):
                        st.write("**error**")
                        st.code(d["error"])

            usage = result.get("usage", {})
            st.caption(
                f"run `{result['run_id']}` · provider `{result.get('embedding_provider')}` · "
                f"LLM {usage.get('total_seconds_llm', 0)}s · "
                f"est. ${usage.get('estimated_cost_usd', 0)} · "
                f"saved to `{result['outputs']['report_path']}`"
            )

            for key, label in (("pdf_path", "Download PDF"), ("pptx_path", "Download PPTX")):
                path = result["outputs"].get(key)
                if path:
                    with open(path, "rb") as fh:
                        st.download_button(label, fh.read(), file_name=Path(path).name)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Generation failed: {exc}")
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass
