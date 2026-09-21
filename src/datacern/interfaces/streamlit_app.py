"""DataCern Streamlit web interface.

Run locally:
    datacern-web
    # or: streamlit run src/datacern/interfaces/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Fallback: allow `streamlit run src/datacern/interfaces/streamlit_app.py`
# without an installed package by adding src/ to sys.path.
_SRC = Path(__file__).resolve().parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from datacern import __version__  # noqa: E402
from datacern.charts.planner import CHART_CATALOG, available_chart_options  # noqa: E402
from datacern.config import settings as config  # noqa: E402
from datacern.data.loaders import load_file  # noqa: E402
from datacern.data.preprocessing import PreprocessOptions  # noqa: E402
from datacern.data.profiling import profile_dataframe  # noqa: E402
from datacern.reports.generator import ReportGenerator  # noqa: E402

st.set_page_config(page_title=f"DataCern {__version__}", page_icon="📊", layout="wide")

# --- session state defaults ---
for _k, _v in {
    "prep_drop_dupes": False,
    "prep_drop_constant": False,
    "prep_missing": "keep",
    "prep_trim": True,
    "prep_coerce": True,
    "chart_max": 6,
    "chart_palette": "viridis",
    "chart_selected": [],
    "history_loaded": None,
    "last_result": None,
    "preview_df": None,
    "preview_name": None,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

st.title("📊 DataCern — evidence-grounded reports")
st.caption(
    "Upload a CSV or PDF, ask a question, and get a professional report with "
    "auto-generated charts — powered by RAG (Chroma + Gemini/Groq/OpenRouter/OpenAI failover)."
)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    st.caption(f"LLM preference: `{config.LLM_PROVIDER_PREFERENCE}`")
    st.write(f"{'✅' if config.GEMINI_API_KEY else '❌'} Gemini API key")
    st.write(f"{'✅' if config.GROQ_API_KEY else '❌'} Groq (`{config.GROQ_LLM_MODEL}`)")
    st.write(
        f"{'✅' if config.OPENROUTER_API_KEY else '❌'} OpenRouter "  # noqa: E501
        f"(`{config.OPENROUTER_LLM_MODEL}`)"
    )
    st.write(f"{'✅' if config.OPENAI_API_KEY else '❌'} OpenAI API key")
    if not any(
        (
            config.GEMINI_API_KEY,
            config.GROQ_API_KEY,
            config.OPENROUTER_API_KEY,
            config.OPENAI_API_KEY,
        )
    ):
        st.warning("No API key configured. Set keys in `.env` or Secrets.")  # noqa: E501

    st.divider()
    st.subheader("History")
    outputs_root = Path(config.OUTPUT_PATH)
    runs: list[Path] = []
    if outputs_root.exists():
        runs = sorted(
            [p for p in outputs_root.glob("*/run.json")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:10]
    if not runs:
        st.caption("No past runs yet.")
    else:
        for rp in runs:
            try:
                data = json.loads(rp.read_text(encoding="utf-8"))
                label = f"{data.get('query', '')[:32]} · {rp.parent.name}"
                if st.button(label, key=str(rp), use_container_width=True):
                    st.session_state.history_loaded = str(rp)
            except Exception:
                continue
        if st.session_state.history_loaded:
            try:
                hj = json.loads(Path(st.session_state.history_loaded).read_text(encoding="utf-8"))
                st.caption(f"Loaded: {hj.get('query', '')[:40]}")
                report_p = Path(hj["outputs"]["report_path"])
                if report_p.exists():
                    st.download_button(
                        "Download report.md", report_p.read_bytes(), file_name=report_p.name
                    )
            except Exception:
                pass

    with st.expander("Advanced preprocessing defaults"):
        st.checkbox("Trim whitespace", key="prep_trim")
        st.checkbox("Coerce numeric/dates", key="prep_coerce")
        st.checkbox("Drop duplicate rows", key="prep_drop_dupes")
        st.checkbox("Drop constant columns", key="prep_drop_constant")
        st.selectbox(
            "Missing values (global)",
            [
                "keep",
                "drop_rows",
                "fill_median",
                "fill_mean",
                "fill_mode",
                "fill_zero",
                "fill_forward",
            ],
            key="prep_missing",
        )
    with st.expander("Visuals (charts)"):
        st.slider("Max charts", 1, 6, key="chart_max")
        st.selectbox(
            "Palette",
            ["viridis", "Set2", "tab10", "coolwarm", "magma", "pastel"],
            key="chart_palette",
        )
        st.caption("Leave empty for smart auto (ranked). Select to override.")
        # options depend on preview
        _opts = []
        try:
            _opts = available_chart_options(st.session_state.preview_df)
        except Exception:
            _opts = list(CHART_CATALOG.keys())
        if _opts:
            st.multiselect(
                "Chart types (override smart)",
                options=_opts,
                format_func=lambda x: f"{x}: {CHART_CATALOG.get(x, x)}",
                key="chart_selected",
            )

# ------------------------------------------------------------------ inputs
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

# ------------------------------------------------ preview + cleaning
df_preview: pd.DataFrame | None = None
preview_name: str | None = None
if uploaded is not None:
    # cache preview df in session to avoid re-reading on rerun
    if st.session_state.preview_name != uploaded.name:
        suffix = Path(uploaded.name).suffix.lower()
        tmp_p = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_p = tmp.name
            loaded = load_file(tmp_p)
            df_preview = loaded["dataframe"]
            preview_name = uploaded.name
            st.session_state.preview_df = df_preview
            st.session_state.preview_name = preview_name
        except Exception as e:
            st.error(f"Could not preview file: {e}")
        finally:
            if tmp_p:
                try:
                    Path(tmp_p).unlink(missing_ok=True)
                except OSError:
                    pass
    else:
        df_preview = st.session_state.preview_df
        preview_name = st.session_state.preview_name

    if df_preview is not None and not df_preview.empty:
        st.divider()
        st.subheader(
            f"Preview: {preview_name} — {df_preview.shape[0]} rows × {df_preview.shape[1]} cols"
        )
        tab_data, tab_quality, tab_clean, tab_visuals = st.tabs(
            ["Data", "Quality", "Cleaning", "Visuals"]
        )

        with tab_data:
            st.dataframe(df_preview.head(100), use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", df_preview.shape[0])
            c2.metric("Columns", df_preview.shape[1])
            c3.metric("Duplicates", int(df_preview.duplicated().sum()))
            with st.expander("dtypes & head(5)"):
                st.code(df_preview.dtypes.to_string())
                st.code(df_preview.head(5).to_string())

        with tab_quality:
            profile = profile_dataframe(df_preview)
            st.text(profile)
            # missing bar
            miss = df_preview.isna().sum()
            miss = miss[miss > 0]
            if not miss.empty:
                st.warning(
                    f"{len(miss)} columns with missing values — choose a fix in Cleaning tab."
                )
                st.bar_chart(miss)
            else:
                st.success("No missing values detected.")
            if any(df_preview[c].nunique(dropna=False) <= 1 for c in df_preview.columns):
                st.info("Constant columns detected — optionally drop them in Cleaning.")

        with tab_clean:
            st.caption("Opt-in cleaning — lineage saved to run.json.")  # noqa: E501
            # per-column missing overrides
            st.write("**Per-column missing handling (overrides global)**")
            per_col: dict[str, str] = {}
            cols = st.columns(3)
            for i, col in enumerate(df_preview.columns):
                miss_ct = int(df_preview[col].isna().sum())
                if miss_ct == 0:
                    continue
                with cols[i % 3]:
                    per_col[col] = st.selectbox(
                        f"{col} ({miss_ct} miss)",
                        [
                            "(global)",
                            "keep",
                            "drop_rows",
                            "fill_median",
                            "fill_mean",
                            "fill_mode",
                            "fill_zero",
                            "fill_forward",
                        ],
                        key=f"prep_col_{col}",
                    )
            # store for generate step
            st.session_state["_per_col"] = {k: v for k, v in per_col.items() if v != "(global)"}

        with tab_visuals:
            st.caption(
                "Smart auto ranks diverse charts; override in sidebar Visuals expander (up to 6)."
            )
            st.write(f"**Max charts:** {st.session_state.chart_max}")
            st.write(f"**Palette:** {st.session_state.chart_palette}")
            sel = st.session_state.chart_selected
            st.write(f"**Selected:** {', '.join(sel) if sel else 'smart auto (ranked)'}")
            opts = available_chart_options(df_preview)
            st.caption(
                f"Available for this data: {', '.join(opts) if opts else 'none — will use fallback'}"  # noqa: E501
            )
    elif df_preview is not None and df_preview.empty:
        st.info("File loaded but table is empty (0 rows).")
    elif uploaded is not None:
        st.caption("PDF detected — tabular preview not available; RAG will index text chunks.")

# ------------------------------------------------------------------ run
if generate:
    if uploaded is None:
        st.warning("Please upload a file.")
    elif not query.strip():
        st.warning("Please enter a query.")
    else:
        suffix = Path(uploaded.name).suffix.lower()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name

            # build preprocessing options from UI
            per_col_clean = st.session_state.get("_per_col", {})
            # normalize: skip "(global)"
            per_col_clean = {k: v for k, v in per_col_clean.items() if v and v != "(global)"}
            prep_opts = PreprocessOptions(
                drop_duplicates=bool(st.session_state.prep_drop_dupes),
                drop_constant=bool(st.session_state.prep_drop_constant),
                trim_strings=bool(st.session_state.prep_trim),
                coerce_numeric=bool(st.session_state.prep_coerce),
                coerce_dates=bool(st.session_state.prep_coerce),
                missing_strategy=st.session_state.prep_missing,
                missing_per_column=per_col_clean,
            )

            with st.status("Generating report…", expanded=True) as status:
                st.write("Validating & preprocessing…")
                generator = ReportGenerator()
                st.write("Indexing & retrieving (RAG)…")
                chart_sel = st.session_state.chart_selected or None
                result = generator.generate(
                    tmp_path,
                    query.strip(),
                    original_filename=uploaded.name,
                    export_pdf_=want_pdf,
                    export_pptx_=want_pptx,
                    preprocess_options=prep_opts,
                    chart_types=chart_sel,
                    chart_palette=st.session_state.chart_palette,
                    max_charts=int(st.session_state.chart_max),
                )
                status.update(label="Report ready", state="complete", expanded=False)

            st.session_state.last_result = result

            st.subheader("Report")
            # editable report before export
            edited = st.text_area(
                "Edit report (Markdown) before export", value=result["report"], height=420
            )
            if edited != result["report"]:
                result["report"] = edited
                # re-save edited markdown
                try:
                    Path(result["outputs"]["report_path"]).write_text(edited, encoding="utf-8")
                except Exception:
                    pass
            st.markdown(result["report"])

            if result.get("warnings"):
                for warning in result["warnings"]:
                    st.warning(warning)

            if result["charts"]:
                st.subheader("Charts")
                caps = result.get("chart_captions") or [
                    f"Figure {i + 1}" for i in range(len(result["charts"]))
                ]
                cols = st.columns(2)
                for i, chart in enumerate(result["charts"]):
                    cap = caps[i] if i < len(caps) else f"Figure {i + 1}"
                    with cols[i % 2]:
                        st.image(chart, caption=cap[:80], use_container_width=True)
                        st.caption(cap[:160])
            else:
                st.info("No charts produced (input may be a PDF without tabular data).")

            with st.expander("Preprocessing lineage"):
                st.json(result.get("preprocessing", {}))

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
                    if d.get("code"):
                        st.code(d["code"], language="python")

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
