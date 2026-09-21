"""Report generation: orchestrates loading, RAG retrieval, analysis, LLM
writing and safe chart-code execution."""

from __future__ import annotations

import re
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from datacern import __version__
from datacern.analysis.insights import build_insight_context
from datacern.charts.planner import plan_charts
from datacern.charts.secure_executor import execute_code
from datacern.charts.validator import validate_execution
from datacern.config import settings as config
from datacern.config.providers import active_embedding_provider, call_llm
from datacern.data.loaders import dataframe_summary, load_file
from datacern.data.preprocessing import (
    PreprocessOptions,
    format_preprocessing_report,
    preprocess_dataframe,
)
from datacern.observability.logging import get_logger
from datacern.rag.pipeline import (
    RAGPipeline,
    collection_name_for,
    content_hash_for,
)
from datacern.reports.exporters import export_pdf, export_pptx
from datacern.reports.prompts import (
    CAPTION_SYSTEM_PROMPT,
    CAPTION_USER_PROMPT,
    CHART_FIX_HINT,
    CHART_SYSTEM_PROMPT,
    CHART_USER_PROMPT,
    REPORT_SYSTEM_PROMPT,
    REPORT_USER_PROMPT,
)
from datacern.services.cost_tracking import UsageTracker
from datacern.services.storage import RunStore

log = get_logger("reports.generator")


def _strip_code_fences(code: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", code, re.DOTALL)
    return match.group(1) if match else code.strip()


class ReportGenerator:
    """High-level API used by the CLI, web UI, and future API layer."""

    def __init__(self) -> None:
        if not any(
            (
                config.GEMINI_API_KEY,
                config.OPENAI_API_KEY,
                config.GROQ_API_KEY,
                config.OPENROUTER_API_KEY,
            )
        ):
            raise RuntimeError(
                "No API keys configured. Create a .env file in the project root "
                "and set GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY / "
                "OPENAI_API_KEY (see .env.example)."
            )
        self.usage = UsageTracker()

    # ------------------------------------------------------------ helpers
    def _write_report(
        self, query: str, context: str, df_summary: str, insights: str, kind: str
    ) -> str:
        prompt = REPORT_USER_PROMPT.format(
            kind=kind,
            query=query,
            context=context,
            df_summary=df_summary,
            insights=insights,
        )
        messages = [SystemMessage(content=REPORT_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        with self.usage.track("report", config.GEMINI_LLM_MODEL, prompt):
            report = call_llm(messages)
        self.usage.record_output("report", report)
        return report

    def _write_chart_code(
        self,
        query: str,
        df_summary: str,
        chart_plan: str,
        report: str,
        palette: str = "viridis",
        max_charts: int = 6,
        last_error: str = "",
    ) -> str:
        snippet = report[:1500]
        fix_hint = CHART_FIX_HINT.format(error=last_error) if last_error else ""
        prompt = CHART_USER_PROMPT.format(
            query=query,
            df_summary=df_summary,
            chart_plan=chart_plan,
            report_snippet=snippet,
            palette=palette,
            max_charts=max_charts,
            fix_hint=fix_hint,
        )
        messages = [SystemMessage(content=CHART_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        with self.usage.track("chart_code", config.GEMINI_LLM_MODEL, prompt):
            code = _strip_code_fences(call_llm(messages))
        self.usage.record_output("chart_code", code)
        return code

    def _write_captions(
        self, query: str, df_summary: str, chart_plan: str, report: str, insights: str, n: int
    ) -> list[str]:
        """Generate short professional captions (one per chart). Fallback to plan if LLM fails."""
        if n <= 0:
            return []
        prompt = CAPTION_USER_PROMPT.format(
            df_summary=df_summary,
            chart_plan=chart_plan,
            report_snippet=report[:1200],
            insights=insights[:800],
            n=n,
            query=query,
        )
        messages = [SystemMessage(content=CAPTION_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        try:
            with self.usage.track("captions", config.GEMINI_LLM_MODEL, prompt):
                raw = call_llm(messages).strip()
            self.usage.record_output("captions", raw)
            lines = [line.strip(" -•\t") for line in raw.splitlines() if line.strip()]
            # enforce n lines, trim to 22 words each
            caps: list[str] = []
            for line in lines[:n]:
                words = line.split()
                if len(words) > 22:
                    line = " ".join(words[:22])
                caps.append(line)
            # pad if short
            while len(caps) < n:
                caps.append(
                    f"Figure {len(caps) + 1} — {chart_plan.splitlines()[len(caps)].strip()[:60]}"
                )
            return caps[:n]
        except Exception:
            # deterministic fallback: use chart plan lines
            fallback: list[str] = []
            for idx, pline in enumerate(chart_plan.splitlines()[:n], 1):
                fallback.append(f"Figure {idx} — {pline.strip()[:90]}")
            return fallback

    # ------------------------------------------------------------- main
    def generate(
        self,
        file_path: str,
        user_query: str,
        original_filename: str | None = None,
        export_pdf_: bool = False,
        export_pptx_: bool = False,
        preprocess_options: PreprocessOptions | dict | None = None,
        chart_types: list[str] | None = None,
        chart_palette: str = "viridis",
        max_charts: int = 6,
    ) -> dict:
        """Generate a complete report.

        Returns a dict with report text, chart paths, retrieved context,
        KPI insights, citations, warnings, usage stats, and output paths.
        """
        started = time.perf_counter()
        config.ensure_runtime_dirs()

        loaded = load_file(file_path)
        df = loaded["dataframe"]
        # --- preprocessing (opt-in, conservative defaults) ---
        if isinstance(preprocess_options, dict):
            preprocess_options = PreprocessOptions(**preprocess_options)
        df, prep_report = preprocess_dataframe(df, preprocess_options)
        df_summary = dataframe_summary(df)
        # inject preprocessing lineage into insights context
        insight_base = build_insight_context(df)
        prep_line = format_preprocessing_report(prep_report)
        insights = (
            f"{insight_base}\n\n--- preprocessing ---\n{prep_line}" if prep_line else insight_base
        )

        embedding_provider = active_embedding_provider()
        pipeline = RAGPipeline(
            collection_name=collection_name_for(
                loaded["filename"], content_hash_for(loaded["path"])
            ),
            embedding_provider=embedding_provider,
        )
        chunk_count = pipeline.index(loaded["documents"])
        context = pipeline.retrieve_context(user_query)

        report = self._write_report(user_query, context, df_summary, insights, loaded["kind"])

        # --------------------------------------------------- charts (CSV only)
        run_id = config.new_run_id()
        store = RunStore(run_id, original_filename or loaded["filename"])
        chart_plan = plan_charts(df, user_query, selected=chart_types, max_charts=max_charts)

        charts: list[str] = []
        exec_detail: dict | None = None
        if df is not None:
            last_error = ""
            for _attempt in range(config.CHART_MAX_ATTEMPTS):
                code = self._write_chart_code(
                    user_query,
                    df_summary,
                    chart_plan,
                    report,
                    palette=chart_palette,
                    max_charts=max_charts,
                    last_error=last_error,
                )
                exec_detail = execute_code(code, dataframe=df, timeout=config.EXEC_TIMEOUT)
                exec_detail["code"] = code
                if exec_detail.get("success") and exec_detail.get("images"):
                    break
                if not exec_detail.get("success"):
                    last_error = exec_detail.get("error", "") or "unknown execution error"
                else:
                    last_error = (
                        "the code ran but produced no figures; create figures with plt.subplots()"
                    )
            if exec_detail.get("success") and exec_detail.get("images"):
                charts = store.save_images(exec_detail["images"])
            elif exec_detail.get("success") and not exec_detail.get("images"):
                exec_detail = None  # no figures is not a failure of the report

        # --- captions (short, professional, after charts) ---
        chart_captions: list[str] = []
        if charts:
            chart_captions = self._write_captions(
                user_query, df_summary, chart_plan, report, insights, len(charts)
            )

        # ------------------------------------------------------------- persist
        report_path = store.save_report(report)
        pdf_path, pptx_path = "", ""
        title = f"DataCern Report — {store.stem}"
        if export_pdf_:
            pdf_path = export_pdf(
                report,
                charts,
                Path(store.root) / f"{store.stem}_{run_id}.pdf",
                title,
                chart_captions,
            )
        if export_pptx_:
            pptx_path = export_pptx(
                report,
                charts,
                Path(store.root) / f"{store.stem}_{run_id}.pptx",
                title,
                chart_captions,
            )

        warnings = validate_execution(exec_detail, want_images=df is not None)
        elapsed = time.perf_counter() - started
        log.info(
            "run %s finished in %.1fs charts=%d warnings=%d",
            run_id,
            elapsed,
            len(charts),
            len(warnings),
        )

        ledger = {
            "datacern_version": __version__,
            "query": user_query,
            "kind": loaded["kind"],
            "embedding_provider": embedding_provider,
            "chunk_count": chunk_count,
            "chart_count": len(charts),
            "chart_plan": chart_plan,
            "chart_palette": chart_palette,
            "max_charts": max_charts,
            "chart_captions": chart_captions,
            "warnings": warnings,
            "usage": self.usage.summary(),
            "elapsed_seconds": round(elapsed, 2),
            "preprocessing": prep_report,
            "outputs": {
                "report_path": report_path,
                "chart_dir": str(store.chart_dir),
                "pdf_path": pdf_path,
                "pptx_path": pptx_path,
            },
        }
        ledger_path = store.save_ledger(ledger)

        return {
            "report": report,
            "charts": charts,
            "chart_captions": chart_captions,
            "context": context,
            "df_summary": df_summary,
            "insights": insights,
            "success": True,
            "error": "",
            "warnings": warnings,
            "exec_detail": exec_detail,
            "usage": ledger["usage"],
            "embedding_provider": embedding_provider,
            "preprocessing": prep_report,
            "run_id": run_id,
            "ledger_path": ledger_path,
            "outputs": ledger["outputs"],
        }
