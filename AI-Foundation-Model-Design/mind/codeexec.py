"""
codeexec — run Python for Vio's agents, contained.

Code execution is the most dangerous capability an assistant can have. Vio reads
untrusted text (web pages, GitHub repos, uploads) and can be reached over the internet
through a tunnel, so a mistake here means someone else's program running on the
user's PC — next to their firewall configurations and, often, their company network.
It is therefore layered, and no single layer is trusted on its own:

  1. APPROVAL   model-written code is shown and runs only when the user approves that
                exact run by id (see Mind.request_code_run / approve_code_run).
  2. LOCALITY   runs are refused for requests arriving through a tunnel/proxy unless
                the operator opts in with VIO_EXEC_REMOTE=1.
  3. PROCESS    code runs in a separate interpreter (`python -I`: no user site dir, no
                PYTHON* variables) with an environment stripped of every secret,
                inside a fresh temp directory that is deleted afterwards.
  4. LIMITS     wall-clock timeout; output capped (the child is killed when it
                exceeds it); CPU/memory/file-size limits where the OS supports them.
  5. POLICY     a PEP 578 audit hook, installed before the code runs and unreachable
                from it, refuses: network (socket), launching programs (subprocess,
                os.system/exec/spawn/fork, startfile), killing processes, native code
                (ctypes), and ANY file access outside the run's own directory and
                Python's installation — so Vio's token, library and the user's files
                cannot be read or changed.

Honest limit: CPython documents audit hooks as "not a sandbox" — they are a strong
policy layer, not a guarantee against a determined attacker. That is exactly why they
sit behind human approval and locality rather than replacing them.

What the code CAN do: the full standard library for computation and analysis —
ipaddress, json, csv, re, statistics, collections, datetime, math … — plus reading and
writing files inside its own directory. The user's parsed configuration is provided
as CONFIG (a list of {"kind", "name", "fields"} dicts) and as config.json.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

DEFAULT_TIMEOUT = int(os.environ.get("VIO_EXEC_TIMEOUT", "20"))
MAX_OUTPUT = int(os.environ.get("VIO_EXEC_MAX_OUTPUT", "40000"))       # bytes, per stream
MAX_CODE = 50_000                                                      # chars

# The prelude runs INSIDE the child, before the user's code. Everything it defines lives
# in _install()'s scope and is deleted, so the running code cannot reach the hook or its
# allow-list: hooks cannot be removed, gc/frame introspection is refused, and the only
# remaining reference to the hook is held by the interpreter itself.
_PRELUDE = r'''
import sys, os, json, io

def _install(sandbox):
    norm = lambda p: os.path.normcase(os.path.realpath(p))
    here = norm(sandbox)
    roots = {here}
    for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix,
              os.path.dirname(os.__file__)}:
        if p:
            roots.add(norm(p))
    try:
        import site
        for p in site.getsitepackages():
            roots.add(norm(p))
    except Exception:
        pass
    roots = tuple(sorted(roots))

    def within(path, allowed):
        if isinstance(path, int):             # an already-open descriptor
            return True
        try:
            p = norm(os.fsdecode(path))
        except Exception:
            return False
        return any(p == r or p.startswith(r + os.sep) for r in allowed)

    BLOCKED_EVENTS = {
        "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo",
        "socket.gethostbyname", "socket.sendto", "socket.sendmsg",
        "subprocess.Popen", "os.system", "os.exec", "os.spawn", "os.posix_spawn",
        "os.fork", "os.forkpty", "os.startfile", "os.kill", "os.killpg",
        "signal.pthread_kill", "ctypes.dlopen", "ctypes.dlsym", "ctypes.cdata",
        "ctypes.call_function", "gc.get_objects", "gc.get_referrers",
        "gc.get_referents", "winreg.OpenKey", "winreg.CreateKey",
        "webbrowser.open", "urllib.Request", "ftplib.connect", "smtplib.connect",
        "telnetlib.Telnet.open", "http.client.connect", "imaplib.open",
        "poplib.connect", "nntplib.connect",
    }
    BLOCKED_MODULES = {
        "socket", "_socket", "ssl", "_ssl", "ctypes", "_ctypes", "subprocess",
        "_posixsubprocess", "_winapi", "multiprocessing", "_multiprocessing",
        "winreg", "pty", "asyncio", "selectors", "select", "http", "urllib.request",
        "ftplib", "smtplib", "telnetlib", "xmlrpc", "webbrowser", "concurrent",
    }
    READ_ONLY = {"open", "os.listdir", "os.scandir"}      # may read Python's own files
    MUTATE = {"os.remove", "os.unlink", "os.rename", "os.replace", "os.rmdir",
              "os.mkdir", "os.makedirs", "os.chmod", "os.chown", "os.utime",
              "os.truncate", "os.link", "os.symlink", "os.chdir", "shutil.rmtree",
              "shutil.copyfile", "shutil.copytree", "shutil.move", "os.chflags"}

    def hook(event, args):
        if event in BLOCKED_EVENTS or event.startswith(("os.exec", "os.spawn")):
            raise PermissionError(f"blocked by Vio's sandbox: {event}")
        if event == "import":
            name = str(args[0] or "")
            if name in BLOCKED_MODULES or name.split(".")[0] in BLOCKED_MODULES:
                raise PermissionError(f"blocked by Vio's sandbox: import {name}")
            return
        if event == "open":
            path, mode = args[0], (args[1] or "r")
            writes = any(c in str(mode) for c in "wax+")
            flags = args[2] if len(args) > 2 else 0
            if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
                writes = True
            if not within(path, (here,) if writes else roots):
                raise PermissionError(
                    f"blocked by Vio's sandbox: {'write' if writes else 'read'} "
                    f"outside the run directory ({os.fsdecode(path) if not isinstance(path, int) else path})")
            return
        if event in READ_ONLY or event in MUTATE:
            allowed = roots if event in READ_ONLY else (here,)
            for a in args:
                if isinstance(a, (str, bytes)) or hasattr(a, "__fspath__"):
                    if not within(a, allowed):
                        raise PermissionError(f"blocked by Vio's sandbox: {event} "
                                              "outside the run directory")

    sys.addaudithook(hook)


_payload = json.loads(sys.stdin.read())
_ns = {"__name__": "__main__", "__builtins__": __builtins__,
       "CONFIG": _payload.get("config") or []}
_code = compile(_payload["code"], "<vio-code>", "exec")
os.chdir(_payload["sandbox"])
_install(_payload["sandbox"])
del _install, _payload
exec(_code, _ns)
'''


def _limits():
    """POSIX resource limits for the child. Windows has no equivalent here; the
    timeout and the output cap still apply there."""
    try:
        import resource
    except ImportError:
        return None

    def apply():
        mb = int(os.environ.get("VIO_EXEC_MAX_MB", "512"))
        for lim, val in ((resource.RLIMIT_AS, mb * 1024 * 1024),
                         (resource.RLIMIT_CPU, DEFAULT_TIMEOUT + 5),
                         (resource.RLIMIT_FSIZE, 50 * 1024 * 1024),
                         (resource.RLIMIT_NPROC, 64)):
            try:
                resource.setrlimit(lim, (val, val))
            except (ValueError, OSError):
                pass
    return apply


def _clean_env(sandbox):
    """Only what an interpreter needs to start. No VIO_TOKEN, no API keys, no PATH
    entries beyond the system's own — the child inherits none of Vio's secrets."""
    keep = {}
    for k in ("SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "LANG", "LC_ALL"):
        if os.environ.get(k):
            keep[k] = os.environ[k]
    keep["PATH"] = os.pathsep.join(p for p in (os.environ.get("SYSTEMROOT", ""),)
                                   if p) or os.defpath
    keep.update({"TEMP": sandbox, "TMP": sandbox, "TMPDIR": sandbox, "HOME": sandbox,
                 "USERPROFILE": sandbox, "PYTHONIOENCODING": "utf-8",
                 "PYTHONDONTWRITEBYTECODE": "1"})
    return keep


def run_python(code, config=None, timeout=None):
    """Execute `code` in the sandbox. Returns a dict:
        ok, stdout, stderr, returncode, timed_out, truncated, blocked, ms, files
    `blocked` holds the sandbox's refusal message when the code tried something
    forbidden. Never raises for anything the code does."""
    code = code or ""
    if len(code) > MAX_CODE:
        return {"ok": False, "stdout": "", "stderr": f"code too long (> {MAX_CODE} chars)",
                "returncode": None, "timed_out": False, "truncated": False,
                "blocked": "", "ms": 0, "files": []}
    timeout = timeout or DEFAULT_TIMEOUT
    sandbox = tempfile.mkdtemp(prefix="vio_run_")
    try:
        cfg = list(config or [])
        with open(os.path.join(sandbox, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        payload = json.dumps({"code": code, "config": cfg, "sandbox": sandbox})

        t0 = time.time()
        proc = subprocess.Popen(
            # -I: isolated (no user site, PYTHON* ignored) · -X utf8: UTF-8 I/O even on
            # Windows · -B: never write .pyc files (which would land outside the sandbox)
            [sys.executable, "-I", "-X", "utf8", "-B", "-c", _PRELUDE],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=sandbox, env=_clean_env(sandbox), preexec_fn=_limits(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        out, err, over = bytearray(), bytearray(), {"hit": False}

        def pump(stream, buf):
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                room = MAX_OUTPUT - len(buf)
                if room > 0:
                    buf.extend(chunk[:room])
                if len(chunk) > room:
                    over["hit"] = True           # stop a flood: kill the child
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return

        readers = [threading.Thread(target=pump, args=(proc.stdout, out), daemon=True),
                   threading.Thread(target=pump, args=(proc.stderr, err), daemon=True)]
        for r in readers:
            r.start()
        try:
            proc.stdin.write(payload.encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        for r in readers:
            r.join(timeout=2)
        ms = int((time.time() - t0) * 1000)

        stderr = err.decode("utf-8", "replace")
        blocked = ""
        for line in stderr.splitlines():
            if "blocked by Vio's sandbox" in line:
                blocked = line.split("PermissionError:", 1)[-1].strip()
        files = sorted(f for f in os.listdir(sandbox) if f != "config.json")[:50]
        return {"ok": proc.returncode == 0 and not timed_out and not over["hit"],
                "stdout": out.decode("utf-8", "replace"), "stderr": stderr,
                "returncode": proc.returncode, "timed_out": timed_out,
                "truncated": over["hit"], "blocked": blocked, "ms": ms, "files": files}
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def config_for_code(objects):
    """The parsed configuration as plain data the sandboxed code can use."""
    return [{"kind": o.kind, "name": o.name, "fields": dict(o.fields)} for o in objects]


def format_result(r, code=None):
    """A readable report of one run."""
    lines = []
    if r.get("blocked"):
        lines.append(f"🛡️ The sandbox stopped the code: {r['blocked']}")
    elif r.get("timed_out"):
        lines.append(f"⏱️ Stopped after {DEFAULT_TIMEOUT}s (time limit).")
    elif r.get("truncated"):
        lines.append(f"✂️ Output exceeded {MAX_OUTPUT // 1000} KB; the run was stopped.")
    elif r.get("ok"):
        lines.append(f"✅ Ran in {r['ms']} ms.")
    else:
        lines.append(f"❌ The code raised an error (exit {r.get('returncode')}).")
    out = (r.get("stdout") or "").rstrip()
    if out:
        lines.append("```\n" + out + "\n```")
    err = (r.get("stderr") or "").strip()
    if err and not r.get("blocked"):
        tail = "\n".join(err.splitlines()[-8:])
        lines.append("stderr:\n```\n" + tail + "\n```")
    if not out and not err and r.get("ok"):
        lines.append("(no output — use print() to show results)")
    if r.get("files"):
        lines.append("Files it wrote (deleted after the run): " + ", ".join(r["files"]))
    return "\n".join(lines)
