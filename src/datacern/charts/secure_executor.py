"""Restricted code execution for generated chart code.

Two layers of protection:

1. **AST whitelist (in-process, at parse time).** Only pandas / numpy /
   matplotlib / seaborn may be imported; dangerous names and attributes
   (open, eval, exec, compile, getattr, __import__, os, sys, subprocess,
   savefig, dataframe I/O methods, ...) are rejected before anything runs.
   A nesting-depth limit guards against pathological ASTs.

2. **Process isolation (at run time).** The validated code is executed in a
   spawned child process so a CPU-bound infinite loop cannot starve the main
   process, and a hard timeout is enforced with ``Process.join(timeout)`` +
   ``Process.terminate()``. This gives real isolation and a reliable timeout,
   which in-process threads cannot provide.

Matplotlib figures are captured automatically as PNG bytes; the generated
code must not call ``plt.show()`` / ``plt.savefig()`` (they are blocked).
"""

from __future__ import annotations

import ast
import builtins
import io
import multiprocessing
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend, no GUI window

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402

# ---------------------------------------------------------------- policy
WHITELIST_MODULE_ROOTS = ("pandas", "numpy", "matplotlib", "seaborn")

SAFE_BUILTINS = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "int",
    "len",
    "list",
    "map",
    "max",
    "min",
    "print",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "repr",
    "divmod",
    "pow",
    "next",
    "iter",
    "slice",
    "frozenset",
    "format",
    "hash",
}

BANNED_ATTRS = {
    "open",
    "read",
    "write",
    "system",
    "popen",
    "spawn",
    "fork",
    "exec",
    "eval",
    "execfile",
    "compile",
    "input",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "__import__",
    "__builtins__",
    "__globals__",
    "__subclasses__",
    "__class__",
    "__bases__",
    "__mro__",
    "__code__",
    "__dict__",
    "__loader__",
    "__spec__",
    "__reduce__",
    "__reduce_ex__",
    "__format__",
    "savefig",
    "show",
    "imsave",
    "imread",
    "to_csv",
    "to_excel",
    "to_pickle",
    "to_json",
    "to_parquet",
    "to_hdf",
    "to_sql",
    "to_feather",
    "read_csv",
    "read_excel",
    "read_pickle",
    "read_json",
    "read_parquet",
    "read_hdf",
    "read_sql",
    "read_html",
    "read_clipboard",
    "read_feather",
    "read_stata",
    "read_sas",
    "read_spss",
}

MAX_AST_DEPTH = 60


class SecurityError(Exception):
    """Raised when generated code violates the execution policy."""


def _module_allowed(module: str) -> bool:
    return any(module == root or module.startswith(root + ".") for root in WHITELIST_MODULE_ROOTS)


def validate_source(source: str) -> None:
    """Parse ``source`` and reject anything outside the whitelist.

    Raises SecurityError on any violation.
    """
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise SecurityError(f"invalid Python syntax: {exc}") from exc

    allowed = set(SAFE_BUILTINS) | {"df", "pd", "np", "plt", "sns", "True", "False", "None"}

    # Pre-pass: collect every name the code assigns (locals, loop targets,
    # params, function/class names, comprehension targets) so user code can
    # define its own intermediate variables.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            allowed.add(node.id)
        elif isinstance(node, ast.arg):
            allowed.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            allowed.add(node.name)

    def walk(node: ast.AST, depth: int) -> None:
        if depth > MAX_AST_DEPTH:
            raise SecurityError("code is nested too deeply")

        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _module_allowed(alias.name):
                    raise SecurityError(f"module '{alias.name}' is not whitelisted")
                allowed.add(alias.asname or alias.name.split(".")[-1])
            return

        if isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise SecurityError("relative imports are not allowed")
            if not _module_allowed(node.module):
                raise SecurityError(f"module '{node.module}' is not whitelisted")
            for alias in node.names:
                allowed.add(alias.asname or alias.name)
            return

        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in allowed:
                raise SecurityError(f"name '{node.id}' is not allowed")

        if isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                raise SecurityError(f"attribute '{node.attr}' is not allowed")
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise SecurityError(f"dunder attribute '{node.attr}' is not allowed")

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"eval", "exec", "compile", "__import__"}:
                raise SecurityError(f"call to '{func.id}' is not allowed")

        if isinstance(node, ast.Starred):
            raise SecurityError("starred expressions are not allowed")

        for child in ast.iter_child_nodes(node):
            walk(child, depth + 1)

    walk(tree, 0)


def _restricted_globals(dataframe: pd.DataFrame | None) -> dict[str, Any]:
    safe_builtins = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    # __import__ is required by Python's import machinery (used when the code
    # does `import pandas as pd`, etc.). It stays unusable by the generated
    # code itself because validate_source rejects the `__import__` name.
    safe_builtins["__import__"] = builtins.__import__
    return {
        "__builtins__": safe_builtins,
        "df": dataframe,
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
    }


def _run_block(source: str, dataframe: pd.DataFrame | None) -> dict:
    """Execute ``source`` in restricted globals; returns stdout + PNG images."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        exec(compile(source, "<generated>", "exec"), _restricted_globals(dataframe))

    images: list[bytes] = []
    for num in plt.get_fignums():
        fig = plt.figure(num)
        tmp = io.BytesIO()
        fig.savefig(tmp, format="png", bbox_inches="tight", dpi=120)
        images.append(tmp.getvalue())
    plt.close("all")

    return {"stdout": buf.getvalue().strip(), "images": images}


def _worker_entry(
    code_path: str,
    df_path: str | None,
    image_dir: str,
    queue: multiprocessing.Queue,
) -> None:
    """Entry point executed in the child process."""
    try:
        source = Path(code_path).read_text(encoding="utf-8")
        dataframe = pd.read_pickle(df_path) if df_path else None
        result = _run_block(source, dataframe)

        image_paths: list[str] = []
        for i, png in enumerate(result["images"], start=1):
            target = Path(image_dir) / f"chart_{i}.png"
            target.write_bytes(png)
            image_paths.append(str(target))

        queue.put({"stdout": result["stdout"], "error": "", "image_paths": image_paths})
    except Exception as exc:  # noqa: BLE001
        queue.put({"stdout": "", "error": f"{type(exc).__name__}: {exc}", "image_paths": []})


def execute_code(
    source: str,
    dataframe: pd.DataFrame | None = None,
    timeout: int = 12,
) -> dict:
    """Validate and run ``source`` in a restricted child process.

    Returns a dict with keys:
        success   bool
        stdout    str  (captured print output)
        error     str  (empty on success)
        images    list[bytes]  (PNG chart images, in creation order)
        elapsed   float seconds
    """
    start = time.perf_counter()

    try:
        validate_source(source)
    except SecurityError as exc:
        return {
            "success": False,
            "stdout": "",
            "error": f"SECURITY BLOCKED: {exc}",
            "images": [],
            "elapsed": time.perf_counter() - start,
        }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        code_path = tmp_dir / "code.py"
        code_path.write_text(source, encoding="utf-8")

        df_path: str | None = None
        if dataframe is not None:
            df_path = str(tmp_dir / "df.pkl")
            dataframe.to_pickle(df_path)

        image_dir = tmp_dir / "charts"
        image_dir.mkdir(parents=True, exist_ok=True)

        queue: multiprocessing.Queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_worker_entry,
            args=(str(code_path), df_path, str(image_dir), queue),
            daemon=True,
        )
        proc.start()
        proc.join(timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            return {
                "success": False,
                "stdout": "",
                "error": f"execution timed out after {timeout}s",
                "images": [],
                "elapsed": time.perf_counter() - start,
            }

        try:
            result = queue.get(timeout=10)
        except Exception:  # noqa: BLE001  (queue.Empty)
            result = {"stdout": "", "error": "worker exited without a result", "image_paths": []}

        images = [Path(p).read_bytes() for p in result.get("image_paths", []) if Path(p).exists()]

    result.pop("image_paths", None)
    result["images"] = images
    result["elapsed"] = time.perf_counter() - start
    result["success"] = not bool(result.get("error"))
    return result
