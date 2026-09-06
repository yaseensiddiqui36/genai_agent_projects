"""One-command launcher: starts the FastAPI backend, then the Streamlit UI.

    python app.py                # both services, default ports
    python app.py --no-browser   # don't auto-open the browser tab

Ctrl+C stops both processes. If a port is already occupied by a *stale* process from
a previous run, that's the classic cause of `WinError 10013/10048` on Windows -- this
script checks for that up front and reports which process to kill instead of failing
deep inside uvicorn's socket bind.
"""

from __future__ import annotations

import argparse
import atexit
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_HOST = "127.0.0.1"
API_PORT = 8000
UI_PORT = 8501

_children: list[subprocess.Popen] = []


def _port_status(host: str, port: int) -> str:
    """Returns 'free', 'ours' (our own /health responds), or 'occupied' (something else)."""
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as resp:
            if resp.status == 200:
                return "ours"
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return "free"
        except OSError:
            return "occupied"


def _cleanup() -> None:
    for proc in _children:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 5
    for proc in _children:
        remaining = max(0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_for_backend(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_status(API_HOST, API_PORT) == "ours":
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open the Streamlit tab")
    args = parser.parse_args()

    atexit.register(_cleanup)

    backend_status = _port_status(API_HOST, API_PORT)
    if backend_status == "occupied":
        print(
            f"Port {API_PORT} is already in use by another process (not this app's backend).\n"
            f"On Windows, find and stop it with:\n"
            f"  netstat -ano | findstr :{API_PORT}\n"
            f"  taskkill /PID <pid> /F\n"
            f"Or set a different port by editing API_PORT in app.py.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif backend_status == "ours":
        print(f"Backend already running at http://{API_HOST}:{API_PORT}, reusing it.")
    else:
        print(f"Starting FastAPI backend on http://{API_HOST}:{API_PORT} ...")
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "infinite_coding_round.api.main:app",
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
            ]
        )
        _children.append(backend)
        if not _wait_for_backend():
            print("Backend did not become healthy in time; check the logs above.", file=sys.stderr)
            _cleanup()
            sys.exit(1)
        print("Backend is up.")

    print(f"Starting Streamlit UI on http://{API_HOST}:{UI_PORT} ...")
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "src/infinite_coding_round/ui/streamlit_app.py",
        "--server.port",
        str(UI_PORT),
    ]
    if args.no_browser:
        streamlit_cmd += ["--server.headless", "true"]

    try:
        subprocess.run(streamlit_cmd, check=False)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
