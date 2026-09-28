"""Revisa el contenido preparado en Git antes de compartir el repositorio.

Es un control automático básico. La revisión humana de procedencia y derechos
del código y de los datos sigue siendo necesaria.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PATRONES = {
    "clave privada": re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "token de GitHub": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "clave de acceso AWS": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "correo electrónico": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ruta de usuario Windows": re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+"),
}
EXTENSIONES_NO_PUBLICABLES = {".db", ".sqlite", ".sqlite3", ".pfx", ".pem", ".key"}


def main() -> int:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                            capture_output=True).stdout
    archivos = [Path(raw.decode("utf-8")) for raw in listed.split(b"\0") if raw]
    hallazgos: list[str] = []
    for relative in archivos:
        path = ROOT / relative
        if relative.suffix.lower() in EXTENSIONES_NO_PUBLICABLES:
            hallazgos.append(f"{relative}: formato privado o binario")
            continue
        data = path.read_bytes()
        for nombre, patron in PATRONES.items():
            if patron.search(data):
                hallazgos.append(f"{relative}: posible {nombre}")
    if hallazgos:
        print("Revisar antes de publicar:")
        for item in hallazgos:
            print(f"- {item}")
        return 1
    print(f"Revisión automática sin hallazgos en {len(archivos)} archivos de Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
