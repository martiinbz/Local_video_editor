"""FastAPI application for the local manifest editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import tempfile

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .manifest_adapter import ManifestValidationError, manifest_from_editor_project
from .audio_analysis import AudioAnalysisError, AudioAnalysisService
from .project_service import ProjectService, UnsafeMediaPathError
from .render_manager import RenderManager
from .srt_parser import SrtParseError, parse_srt
from renderer import DocumentaryRenderer


def create_app(root: Path | None = None, render_manager: Any | None = None, audio_analysis: Any | None = None) -> FastAPI:
    renderer_root = (root or Path(__file__).resolve().parents[2]).resolve()
    analyzer = audio_analysis or AudioAnalysisService(renderer_root / ".cache" / "editor-waveforms")
    active_file = renderer_root / "projects" / ".active"

    def project_names() -> list[dict[str, str]]:
        items = [{"id": "default", "name": "Proyecto actual"}]
        projects_root = renderer_root / "projects"
        if projects_root.exists():
            items.extend(
                {"id": path.name, "name": path.name}
                for path in sorted(projects_root.iterdir())
                if path.is_dir() and ((path / "manifest.json").is_file() or (path / "project" / "manifest.json").is_file())
            )
        return items

    def active_project(requested: str | None = None) -> str:
        if requested and any(item["id"] == requested for item in project_names()):
            active_file.parent.mkdir(parents=True, exist_ok=True)
            active_file.write_text(requested, encoding="utf-8")
            return requested
        if active_file.is_file():
            saved = active_file.read_text(encoding="utf-8").strip()
            if any(item["id"] == saved for item in project_names()):
                return saved
        return "default"

    services: dict[str, ProjectService] = {}
    managers: dict[str, Any] = {}

    def get_service(project: str | None = None) -> ProjectService:
        project_id = active_project(project)
        if project_id not in services:
            services[project_id] = ProjectService(renderer_root, audio_analysis=analyzer, project_name=None if project_id == "default" else project_id)
        return services[project_id]

    def get_manager(project: str | None = None) -> Any:
        project_id = active_project(project)
        if project_id not in managers:
            managers[project_id] = render_manager or RenderManager(
                get_service(project_id).project_root,
                renderer_root=renderer_root,
            )
        return managers[project_id]
    manager = render_manager or RenderManager(renderer_root)
    app = FastAPI(title="Documentary Manifest Editor", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        return {"active": active_project(), "projects": project_names()}

    @app.get("/api/project")
    def get_project(project: str | None = Query(default=None)) -> dict[str, Any]:
        try:
            return get_service(project).load()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/project/save")
    def save_project(project: dict[str, Any], project_id: str | None = Query(default=None)) -> dict[str, Any]:
        try:
            path = get_service(project_id or project.get("projectId")).save(project)
        except (OSError, ManifestValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"status": "saved", "path": path.relative_to(renderer_root).as_posix()}

    @app.post("/api/project/render", status_code=202)
    def render_project(project: dict[str, Any], project_id: str | None = Query(default=None)) -> dict[str, str]:
        try:
            selected = project_id or project.get("projectId")
            path = get_service(selected).save(project)
        except (OSError, ManifestValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not get_manager(selected).start(path):
            raise HTTPException(status_code=409, detail="A render is already running")
        return {"status": "rendering"}

    @app.post("/api/project/audio-preview")
    def audio_preview(project: dict[str, Any]) -> dict[str, str]:
        preview_manifest: Path | None = None
        try:
            project_id = project.get("projectId")
            service = get_service(project_id)
            service._validate_editor_paths(project)
            manifest_payload = manifest_from_editor_project(project)
            fingerprint = hashlib.sha256(json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
            with tempfile.NamedTemporaryFile(mode="w", suffix=".preview.json", dir=service.editor_path.parent, delete=False, encoding="utf-8") as temporary:
                json.dump(manifest_payload, temporary, ensure_ascii=False)
                preview_manifest = Path(temporary.name)
            relative_output = f".cache/editor-audio-preview-{fingerprint}.m4a"
            output = service.project_root / relative_output
            mixed = output if output.is_file() else DocumentaryRenderer(renderer_root=renderer_root).render_manifest_audio_preview(preview_manifest, output)
            if mixed is None:
                raise ManifestValidationError("The project has no audio to preview")
            return {"url": f"/api/media?path={relative_output}&project={project_id or 'default'}&v={fingerprint}"}
        except (OSError, ManifestValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            if preview_manifest is not None:
                preview_manifest.unlink(missing_ok=True)

    @app.post("/api/project/render-preview")
    def render_preview(project: dict[str, Any], time: float = Query(default=0, ge=0), window: float = Query(default=12, gt=0, le=30)) -> dict[str, str]:
        preview_manifest: Path | None = None
        try:
            project_id = project.get("projectId")
            service = get_service(project_id)
            service._validate_editor_paths(project)
            payload = manifest_from_editor_project(project)
            fingerprint = hashlib.sha256((json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + f":window-v2:{time:.3f}:{window:.3f}").encode("utf-8")).hexdigest()[:16]
            relative_output = f".cache/editor-render-preview-{fingerprint}.mp4"
            output = service.project_root / relative_output
            if not output.is_file():
                with tempfile.NamedTemporaryFile(mode="w", suffix=".preview.json", dir=service.editor_path.parent, delete=False, encoding="utf-8") as temporary:
                    json.dump(payload, temporary, ensure_ascii=False)
                    preview_manifest = Path(temporary.name)
                DocumentaryRenderer(renderer_root=renderer_root).render_manifest_window(preview_manifest, output, time, window)
            return {"url": f"/api/media?path={relative_output}&project={project_id or 'default'}&v={fingerprint}"}
        except (OSError, ManifestValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            if preview_manifest is not None:
                preview_manifest.unlink(missing_ok=True)

    @app.get("/api/render/status")
    def render_status() -> dict[str, Any]:
        return get_manager().status()

    @app.get("/api/media")
    def get_media(path: str = Query(min_length=1), project: str | None = Query(default=None)) -> FileResponse:
        try:
            media_path = get_service(project).resolve_media(path)
        except UnsafeMediaPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Images and audio are edited in place while the editor is open.
        # Prevent the browser from reusing an older response after a file
        # has been replaced on disk.
        return FileResponse(media_path, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    @app.get("/api/audio/waveform")
    def get_waveform(path: str = Query(min_length=1), points: int = Query(default=4096, ge=256, le=8192)) -> dict[str, Any]:
        try:
            media_path = get_service().resolve_audio(path)
            return analyzer.waveform(media_path, points)
        except UnsafeMediaPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AudioAnalysisError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/project/subtitles")
    def list_subtitles() -> list[dict[str, str]]:
        return get_service().list_subtitles()

    @app.get("/api/subtitles")
    def get_subtitles(path: str = Query(min_length=1)) -> dict[str, Any]:
        try:
            subtitle_path = get_service().resolve_subtitle(path)
            return {"path": path, "cues": parse_srt(subtitle_path)}
        except UnsafeMediaPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (OSError, SrtParseError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/fonts")
    def list_fonts() -> list[dict[str, str]]:
        return get_service().list_fonts()

    @app.get("/api/fonts/file")
    def get_font(path: str = Query(min_length=1)) -> FileResponse:
        try:
            return FileResponse(get_service().resolve_font(path))
        except UnsafeMediaPathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    frontend_dist = renderer_root / "editor" / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def frontend(full_path: str) -> FileResponse:
            requested = frontend_dist / full_path
            return FileResponse(requested if requested.is_file() else frontend_dist / "index.html")

    return app


app = create_app()
