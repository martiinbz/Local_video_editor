from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from manifest_paths import normalize_manifest_paths
from models import (
    AmbienceCue,
    Asset,
    AssetType,
    GenerationSource,
    Manifest,
    MusicCue,
    MusicState,
    ProjectConfig,
    Shot,
    SoundEffectCue,
    StoryFunction,
    VisualLevel,
    VisualType,
)


def test_normalize_manifest_paths_keeps_assets_shared_and_project_media_local(tmp_path: Path) -> None:
    renderer_root = tmp_path / "renderer"
    project_dir = renderer_root / "projects" / "case-a"
    manifest = Manifest(
        project=ProjectConfig(
            title="Case A",
            voice=Path("project/narration.mp3"),
            output=Path("output/documentary.mp4"),
        ),
        assets={
            "ASSET_001": Asset(
                asset_id="ASSET_001",
                type=AssetType.IMAGE,
                generation_source=GenerationSource.FLOW,
                file=Path("project/images/SCENE_1.jpg"),
                visual_level=VisualLevel.GRAPHIC,
            )
        },
        shots=[
            Shot(
                shot_id="SHOT_001",
                asset_id="ASSET_001",
                duration=3,
                story_function=StoryFunction.HOOK,
                visual_type=VisualType.RECONSTRUCTION,
                visual_level=VisualLevel.GRAPHIC,
                importance=8,
                sfx=[SoundEffectCue(name="hit", file=Path("assets/sfx/deep_hit.mp3"), at=0.2)],
            )
        ],
        music_cues=[MusicCue(state=MusicState.MYSTERY, start=0, end=3, track=Path("assets/music/mystery_01.mp3"))],
        ambience_cues=[AmbienceCue(name="office", file=Path("assets/ambience/office.mp3"), start=0, end=3)],
    )

    normalized = normalize_manifest_paths(manifest, project_dir=project_dir, renderer_root=renderer_root)

    assert normalized.project.voice == project_dir / "narration.mp3"
    assert normalized.project.output == project_dir / "output" / "documentary.mp4"
    assert normalized.assets["ASSET_001"].file == project_dir / "images" / "SCENE_1.jpg"
    assert normalized.music_cues[0].track == renderer_root / "assets" / "music" / "mystery_01.mp3"
    assert normalized.ambience_cues[0].file == renderer_root / "assets" / "ambience" / "office.mp3"
    assert normalized.shots[0].sfx[0].file == renderer_root / "assets" / "sfx" / "deep_hit.mp3"


def test_normalize_manifest_paths_allows_bare_project_relative_files(tmp_path: Path) -> None:
    renderer_root = tmp_path / "renderer"
    project_dir = renderer_root / "projects" / "case-a"
    manifest = Manifest(
        project=ProjectConfig(title="Case A", voice=Path("narration.mp3"), output=Path("documentary.mp4")),
        assets={
            "ASSET_001": Asset(
                asset_id="ASSET_001",
                type=AssetType.IMAGE,
                generation_source=GenerationSource.FLOW,
                file=Path("images/SCENE_1.jpg"),
                visual_level=VisualLevel.GRAPHIC,
            )
        },
        shots=[
            Shot(
                shot_id="SHOT_001",
                asset_id="ASSET_001",
                duration=3,
                story_function=StoryFunction.HOOK,
                visual_type=VisualType.RECONSTRUCTION,
                visual_level=VisualLevel.GRAPHIC,
                importance=8,
            )
        ],
    )

    normalized = normalize_manifest_paths(manifest, project_dir=project_dir, renderer_root=renderer_root)

    assert normalized.project.voice == project_dir / "narration.mp3"
    assert normalized.project.output == project_dir / "documentary.mp4"
    assert normalized.assets["ASSET_001"].file == project_dir / "images" / "SCENE_1.jpg"
