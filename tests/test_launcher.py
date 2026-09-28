"""El iniciador debe poder cargarse antes de instalar las dependencias."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_launcher_core_uses_only_standard_library_before_install():
    subprocess.run(
        [sys.executable, "-S", "-c",
         "import launcher_core; from pathlib import Path; "
         "assert launcher_core.ROOT == Path.cwd(); "
         "assert launcher_core.VENV == Path.cwd() / '.venv'"],
        cwd=ROOT, check=True, capture_output=True,
    )
