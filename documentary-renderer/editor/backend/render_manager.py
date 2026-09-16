"""Single-process background render coordinator."""

from __future__ import annotations

import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any


class RenderManager:
    def __init__(self, root: Path, renderer_root: Path | None = None) -> None:
        self.root = root.resolve()
        self.renderer_root = (renderer_root or root).resolve()
        self._state = "idle"
        self._logs: deque[str] = deque(maxlen=120)
        self._lock = threading.Lock()

    def start(self, manifest_path: Path) -> bool:
        with self._lock:
            if self._state == "rendering":
                return False
            self._state = "rendering"
            self._logs.clear()
        thread = threading.Thread(target=self._run, args=(manifest_path.resolve(),), daemon=True)
        thread.start()
        return True

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {"state": self._state, "logs": list(self._logs)}

    def _run(self, manifest_path: Path) -> None:
        try:
            relative_manifest = manifest_path.relative_to(self.renderer_root)
            process = subprocess.Popen(
                [sys.executable, "render.py", "--v2", "--ignore-qc", str(relative_manifest)],
                cwd=self.renderer_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._append_log(line.rstrip())
            return_code = process.wait()
            with self._lock:
                self._state = "success" if return_code == 0 else "error"
        except Exception as exc:  # The UI must receive startup failures as render state.
            self._append_log(f"Render failed to start: {exc}")
            with self._lock:
                self._state = "error"

    def _append_log(self, line: str) -> None:
        if line:
            with self._lock:
                self._logs.append(line)
