"""Preparación y arranque local del dashboard desde el iniciador gráfico."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import venv


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYTHON = VENV / "Scripts" / "python.exe" if os.name == "nt" else VENV / "bin" / "python"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state")) / "red_flujos"
LOG_FILE = LOG_DIR / "iniciador.log"
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(command: list[str]) -> subprocess.CompletedProcess:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        return subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                              creationflags=HIDDEN, check=False)


def prepare_environment(status) -> None:
    """Crea el entorno e instala la interfaz solo si hace falta."""
    if not PYTHON.exists():
        status("Creando el entorno de Python…")
        if sys.version_info < (3, 10):
            raise RuntimeError("Se requiere Python 3.10 o superior.")
        venv.create(VENV, with_pip=True)
    check = _run([str(PYTHON), "-c", "import streamlit, plotly, pyvis, red_flujos"])
    if check.returncode != 0:
        status("Instalando dependencias; la primera vez puede tardar varios minutos…")
        installed = _run([str(PYTHON), "-m", "pip", "install", "-e", ".[dashboard]"])
        if installed.returncode != 0:
            raise RuntimeError(f"No se pudieron instalar las dependencias. Consulte {LOG_FILE}")


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_server() -> tuple[subprocess.Popen, str]:
    """Inicia Streamlit accesible solo desde esta computadora."""
    port = available_port()
    command = [str(PYTHON), "-m", "streamlit", "run", str(ROOT / "app.py"),
               "--server.address=127.0.0.1", f"--server.port={port}",
               "--server.headless=true", "--browser.gatherUsageStats=false"]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=HIDDEN)
    return process, f"http://127.0.0.1:{port}"


def wait_until_ready(process: subprocess.Popen, url: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"La aplicación se cerró al iniciar. Consulte {LOG_FILE}")
        try:
            with urlopen(url + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            pass
        time.sleep(0.3)
    raise RuntimeError(f"La aplicación no respondió a tiempo. Consulte {LOG_FILE}")
