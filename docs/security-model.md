# Security model

DataCern executes LLM-generated plotting code. The sandbox is **hardened,
not bullet-proof**: treat it as safe for semi-trusted model output, and run
inside a container for fully adversarial settings.

## Layer 1 — AST whitelist (parse time, in-process)

`charts/secure_executor.py::validate_source` rejects before anything runs:

- Imports limited to `pandas`, `numpy`, `matplotlib`, `seaborn` (incl. submodules).
- Banned names/attributes: `open`, `eval`, `exec`, `compile`, `getattr`,
  `__import__`, `os`, `sys`, `subprocess`, dunders, dataframe/file I/O
  (`to_csv`, `read_csv`, …), `savefig`/`show`.
- Local variable names assigned in the code are allow-listed via a pre-pass.
- AST nesting depth cap (`MAX_AST_DEPTH = 60`).
- `__import__` exists in restricted builtins **only** for Python’s own import
  machinery; the name is rejected for user code by the validator.

## Layer 2 — process isolation (run time)

- Validated code runs in a **spawned child process** (`multiprocessing`,
  daemon) with restricted `__builtins__` and a pre-injected `df`.
- Hard timeout via `Process.join(timeout)` + `terminate()` — a CPU-bound
  infinite loop cannot starve the host (in-process threads cannot guarantee
  this because of the GIL).
- Matplotlib uses the headless `Agg` backend; figures are captured to PNG.
- PNG bytes travel via **temp files**, with only tiny file paths
  crossing the IPC queue (prevents pipe-buffer deadlock).
- Timeouts, crashes, and tracebacks are returned as structured errors and
  fed back to the LLM for self-healing retries (max `CHART_MAX_ATTEMPTS`).

## Residual risks

- No memory/CPU cgroup limits — enforce via Docker/container runtime.
- Resource-heavy but legal code (giant figures, huge loops) can burn CPU
  until the timeout fires.
- Uploads and Chroma stores persist on disk under `var/` — set retention and
  access controls appropriate to your data (see `docs/deployment.md`).
- No PII redaction yet — do not process regulated personal data without
  adding scrubbing and a reviewed DPA posture.

## Regression coverage

`tests/test_secure_executor.py` pins: valid charts produce images; `os`,
`open`, `eval`, `getattr`-dunder, non-whitelisted imports, dataframe I/O,
and `savefig` are blocked; runtime errors surface; infinite loops are killed
by the timeout.
