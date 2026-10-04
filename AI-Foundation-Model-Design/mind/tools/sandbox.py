"""
tools.sandbox — the code-interpreter tool (redesign roadmap T1).

Runs a generated Python snippet in a RESTRICTED subprocess: isolated interpreter
(-I), throwaway working directory, wall-clock timeout, output/ stdout+stderr cap,
no shell, no Vio environment. This is the code-interpreter pattern every production
assistant runs — with Vio's guardrails: the tool holds the EXECUTE permission, so
every run is gated behind user confirmation (or AUTONOMY=autonomous) and recorded
in the Task audit trail.

OS-level network isolation is out of scope for a stdlib implementation on Windows —
note it honestly: treat generated code as semi-trusted, keep the confirm gate ON.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

MAX_OUTPUT = 20_000
DEFAULT_TIMEOUT = 30

_BANNED = ("os.system", "subprocess", "shutil.rmtree", "socket", "urllib",
           "requests", "shutil.copy", "open('C:", 'open("C:', "os.remove",
           "os.unlink", "pathlib", "__import__", "eval(", "exec(")


def run(code, timeout=DEFAULT_TIMEOUT, allow_net=False):
    """Execute a Python snippet. Returns a result dict — never raises.
    A static screen rejects obviously destructive patterns; the subprocess
    isolation + confirm gate carry the rest."""
    if not (code or "").strip():
        return {"ok": False, "error": "no code given"}
    low = code.lower()
    if not allow_net:
        for pat in _BANNED:
            if pat in low:
                return {"ok": False,
                        "error": f"blocked pattern in sandboxed code: {pat!r} "
                                 "(network/process access is not allowed in the sandbox)"}
    workdir = tempfile.mkdtemp(prefix="vio_sandbox_")
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code],        # -I: isolated, no env/path tricks
            cwd=workdir, capture_output=True, text=True,
            timeout=max(1, min(int(timeout), 120)),
            env={"PATH": "", "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                 "PYTHONIOENCODING": "utf-8"})
        out = (proc.stdout or "")[:MAX_OUTPUT]
        err = (proc.stderr or "")[:MAX_OUTPUT]
        return {"ok": proc.returncode == 0, "stdout": out, "stderr": err,
                "returncode": proc.returncode, "ms": round((time.time() - t0) * 1000),
                "workdir": workdir}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s", "ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            for f in os.listdir(workdir):
                os.unlink(os.path.join(workdir, f))
            os.rmdir(workdir)
        except Exception:
            pass


def looks_like_run_request(q):
    """'run python: …' / 'compute with python: …' / fenced ```python blocks."""
    import re
    return bool(re.match(r"^\s*(?:run\s+|compute\s+|execute\s+)?python\s*[:\-]\s*", (q or "").strip(), re.I)
                or (q or "").strip().startswith("```python"))
