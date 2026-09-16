"""Build-free launcher for the local editor production bundle."""

from __future__ import annotations

import sys
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from editor.backend.app import create_app  # noqa: E402


def main() -> None:
    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"
    if port_is_in_use(host, port):
        print(f"El editor ya está activo en {url}. No es necesario ejecutarlo otra vez.")
        webbrowser.open(url)
        return
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(ROOT), host=host, port=port)


def port_is_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.25)
        return probe.connect_ex((host, port)) == 0


if __name__ == "__main__":
    main()
