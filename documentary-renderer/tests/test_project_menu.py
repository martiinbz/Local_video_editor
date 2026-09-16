from __future__ import annotations

from pathlib import Path

import pytest

import render
from project_menu import discover_projects, choose_project_manifest


def test_discover_projects_lists_directories_with_manifest(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    (projects_dir / "case-b").mkdir(parents=True)
    (projects_dir / "case-a").mkdir()
    (projects_dir / "case-a" / "manifest.json").write_text("{}", encoding="utf-8")
    (projects_dir / "case-b" / "manifest.json").write_text("{}", encoding="utf-8")

    projects = discover_projects(projects_dir)

    assert [project.name for project in projects] == ["case-a", "case-b"]


def test_choose_project_manifest_uses_numeric_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projects_dir = tmp_path / "projects"
    (projects_dir / "case-a").mkdir(parents=True)
    (projects_dir / "case-b").mkdir()
    (projects_dir / "case-a" / "manifest.json").write_text("{}", encoding="utf-8")
    (projects_dir / "case-b" / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "2")

    manifest = choose_project_manifest(projects_dir)

    assert manifest == projects_dir / "case-b" / "manifest.json"


def test_cli_without_input_uses_project_menu(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = tmp_path / "projects" / "case-a" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    called: dict[str, Path] = {}

    class FakeRenderer:
        def __init__(self, logger=None) -> None:
            pass

        def render_manifest(self, path: Path, ignore_qc: bool = False) -> Path:
            called["path"] = path
            return tmp_path / "projects" / "case-a" / "output" / "documentary.mp4"

    monkeypatch.setattr(render, "DocumentaryRenderer", FakeRenderer)
    monkeypatch.setattr(render, "choose_project_manifest", lambda projects_dir: manifest)

    result = render.main([])

    assert result == 0
    assert called["path"] == manifest
