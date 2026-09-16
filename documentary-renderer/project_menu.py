"""Interactive project selection for the renderer CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class RenderProject:
    name: str
    directory: Path
    manifest: Path


def discover_projects(projects_dir: str | Path = "projects") -> list[RenderProject]:
    root = Path(projects_dir)
    if not root.exists():
        return []
    projects: list[RenderProject] = []
    for directory in sorted(item for item in root.iterdir() if item.is_dir()):
        manifest = directory / "manifest.json"
        if manifest.exists():
            projects.append(RenderProject(name=directory.name, directory=directory, manifest=manifest))
    return projects


def choose_project_manifest(projects_dir: str | Path = "projects") -> Path:
    projects = discover_projects(projects_dir)
    if not projects:
        raise ValidationError(f"No projects with manifest.json found in: {Path(projects_dir)}")

    print("Elige proyecto:")
    for index, project in enumerate(projects, start=1):
        print(f"{index}. {project.name}")

    raw = input("Número de proyecto: ").strip()
    try:
        selected = int(raw)
    except ValueError as exc:
        raise ValidationError(f"Invalid project selection: {raw}") from exc
    if selected < 1 or selected > len(projects):
        raise ValidationError(f"Project selection out of range: {selected}")
    return projects[selected - 1].manifest
