# Documentary Renderer

## Editor local de manifest

La Fase 1 del editor visual vive en `editor/`. Abre automáticamente
`project/manifest.json`, muestra las pistas de escenas, narración, música y SFX,
permite ajustar el montaje y guarda `project/manifest.editor.json` antes de renderizar.

```powershell
python -m pip install -r requirements.txt
Set-Location editor/frontend
npm install
npm run build
Set-Location ../..
python editor/start.py
```

Consulta `editor/README.md` para desarrollo, pruebas y solución del certificado npm.

Production-ready FFmpeg-based documentary renderer for automated YouTube documentary generation from a JSON storyboard.

Python orchestrates validation, timeline calculation, command generation, temporary files, and logging. FFmpeg performs the media processing.

## Requirements

- Python 3.12 or newer
- FFmpeg and FFprobe available on `PATH`
- `pytest` for running tests

## Installation

```bash
cd documentary-renderer
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## Folder Structure

```text
documentary-renderer/
  README.md
  requirements.txt
  render.py
  config.py
  utils.py
  logger.py
  exceptions.py
  constants.py
  ffmpeg_builder.py
  renderer.py
  audio.py
  motion.py
  transitions.py
  parser.py
  timeline.py
  validator.py
  models.py
  assets/
    music/
    sfx/
  output/
  examples/
    storyboard.json
  project/
    narration.mp3
    images/
    videos/
```

## Example JSON

```json
{
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "voice": "project/narration.mp3",
  "music": "assets/music/mystery.mp3",
  "music_volume": 0.15,
  "voice_volume": 1.0,
  "duck_amount": 0.35,
  "duck_fade_duration": 0.5,
  "output": "output/documentary.mp4",
  "scenes": [
    {
      "type": "image",
      "file": "project/images/001.png",
      "duration": 5,
      "motion": "zoom_in",
      "transition": "fade",
      "transition_duration": 0.5
    },
    {
      "type": "video",
      "file": "project/videos/002.mp4",
      "start_time": 0,
      "end_time": 8,
      "transition": "dip_to_black",
      "transition_duration": 0.75
    }
  ]
}
```

## How To Render

Place media files in the project folders, update `examples/storyboard.json`, then run:

```bash
python render.py examples/storyboard.json
```

For the V2 renderer workflow, put episodes in `projects/` and run without an input path:

```bash
python render.py
```

The CLI will show a menu with every folder in `projects/` that contains `manifest.json`.

You can still render a specific V2 manifest directly:

```bash
python render.py --v2 projects/my-episode/manifest.json
```

The V2 renderer also accepts flat Prompt 3 manifests with:

```json
{
  "manifest_version": "2.3",
  "scenes": []
}
```

In that format, each `scene` is converted internally into one asset and one shot. Scene files such as `project/images/SCENE_1.jpg` or `project/real/SCENE_4_REAL.jpg` are resolved inside the selected project folder.

The renderer logs progress:

```text
Loading project...
Validating storyboard...
Building FFmpeg pipeline...
Rendering scene 1/2...
Rendering scene 2/2...
Mixing audio...
Rendering final output...
Done.
```

The final MP4 is written to the `output` value from the storyboard.

## How To Add Music

Put music files in `assets/music/` and set:

```json
"music": "assets/music/mystery.mp3",
"music_volume": 0.15,
"duck_amount": 0.35,
"duck_fade_duration": 0.5
```

Music loops automatically to match the documentary duration. When narration exists, FFmpeg sidechain compression ducks the music under the voice.

## How To Add Narration

Place narration at `project/narration.mp3` or another path and set:

```json
"voice": "project/narration.mp3",
"voice_volume": 1.0
```

## How To Add Videos

Place clips in `project/videos/` and add a video scene:

```json
{
  "type": "video",
  "file": "project/videos/002.mp4",
  "start_time": 3.5,
  "end_time": 12,
  "transition": "hard_cut"
}
```

If `start_time` and `end_time` are omitted, the full clip is used. Mixed inputs are normalized to the storyboard resolution, frame rate, codec, and pixel format for reliable concatenation.

## Supported Motions

Image scenes support:

- `zoom_in`
- `zoom_out`
- `pan_left`
- `pan_right`
- `pan_up`
- `pan_down`
- `zoom_left`
- `zoom_right`
- `zoom_up`
- `zoom_down`
- `static`

Each motion can set a per-scene `motion_speed`.

## Supported Transitions

Scenes support:

- `fade`
- `crossfade`
- `hard_cut`
- `dip_to_black`

Set `transition_duration` per scene when needed. Crossfade is accepted in storyboards and represented in the timeline; the segment pipeline applies reliable fade behavior while keeping the architecture ready for a later single-graph `xfade` implementation.

## How To Create New Motions

Add a value to `MotionType` in `models.py`, then add its FFmpeg expressions in `MotionFilterFactory._expressions()` in `motion.py`. The renderer will pick it up through storyboard parsing and validation.

## How To Create New Transitions

Add a value to `TransitionType` in `models.py`, then implement its filter behavior in `TransitionFilterFactory.build_video_filter()` in `transitions.py`.

## Architecture

- `parser.py` reads JSON and creates typed models.
- `validator.py` enforces renderable storyboard rules.
- `timeline.py` calculates scene start and end times.
- `motion.py` owns image movement filters.
- `transitions.py` owns transition filter snippets.
- `ffmpeg_builder.py` constructs FFmpeg commands and executes them.
- `audio.py` constructs narration/music mixing commands.
- `renderer.py` coordinates the full render workflow.
- `render.py` exposes the command-line interface.

This keeps each module focused and makes future features easier to add without rewriting the renderer.

## Future Extensions

The architecture is ready for:

- Subtitles
- Voice synchronization
- Particle effects
- Film grain
- Color grading
- LUTs
- Watermarks
- Animated overlays
- Automatic scene timing
- Automatic zoom generation
- Automatic music selection
- Automatic sound effects
- JSON schema versioning

## V2 Renderer Workflow

V2 removes generative AI video clips from the render path. The renderer now supports a `MASTER_MANIFEST` style input where one visual `asset` can be reused by multiple `shots`.

Use this structure for new episodes:

```text
projects/
  my-episode/
  narration.mp3
  transcript.srt
  manifest.json
  images/
    ASSET_001.jpeg
    ASSET_002.jpeg
  real/
    SCENE_4_REAL.jpg
  generated/
  output/
assets/
  music/
  sfx/
  ambience/
  fonts/
  textures/
```

Run:

```bash
python render.py
```

The final MP4 and QC report are written inside the selected project:

```text
projects/my-episode/output/documentary.mp4
projects/my-episode/output/qc_report.txt
```

`assets/` is shared by all projects. Any manifest path beginning with `assets/` resolves from the renderer root, not from the project folder.

The V2 manifest supports:

- `assets`: reusable Flow or renderer-generated images.
- `shots`: timed visual presentations of assets.
- `crop`: `wide`, `medium`, `close`, `focal`.
- `focal_point`: normalized `[x, y]` coordinates from `0` to `1`.
- `motion`: existing Ken Burns motions plus `crop_push` and `focal_zoom`.
- `story_function`: `HOOK`, `CONTEXT`, `EVIDENCE`, `CONTRADICTION`, `REVEAL`, etc.
- `visual_type`: `RECONSTRUCTION`, `CHARACTER`, `LOCATION`, `EVIDENCE`, `DOCUMENT`, `CASE_FILE`, `TIMELINE`, `MAP`, `QUOTE`, etc.
- `visual_level`: `GRAPHIC`, `CINEMATIC`, `HERO`.
- `music_cues`: timed music sections. `SILENCE` is valid.
- `ambience_cues`: low-volume environmental beds.
- Renderer-generated `overlay` assets for `CASE_FILE`, `EVIDENCE`, `DOCUMENT`, `TIMELINE`, `MAP`, `QUOTE`, `DATE`, `LOCATION`, and `THEORY`.

See `examples/manifest.v2.json`.

### Renderer-Generated Maps, Documents, and Text

For V2 graphic moments, you do not need to create the image by hand. Declare an asset with `generation_source: "renderer"` and an `overlay` block. The renderer creates a PNG before validation and uses it as a normal visual asset.

Generated files are written inside the selected project:

```text
projects/my-episode/generated/
```

Evidence card:

```json
{
  "asset_id": "ASSET_EVIDENCE_001",
  "type": "image",
  "generation_source": "renderer",
  "visual_level": "GRAPHIC",
  "overlay": {
    "type": "EVIDENCE",
    "data": {
      "evidence_number": "03",
      "evidence_type": "REGISTRO TELEFÓNICO",
      "time": "23:17:42",
      "short_description": "Última llamada registrada"
    }
  }
}
```

Timeline:

```json
{
  "asset_id": "ASSET_TIMELINE_001",
  "type": "image",
  "generation_source": "renderer",
  "visual_level": "GRAPHIC",
  "overlay": {
    "type": "TIMELINE",
    "data": {
      "title": "Últimas horas",
      "events": [
        { "time": "22:17", "label": "SALE DEL HOTEL" },
        { "time": "22:48", "label": "ÚLTIMA LLAMADA" },
        { "time": "23:06", "label": "CÁMARA" },
        { "time": "23:41", "label": "DESAPARECE" }
      ]
    }
  }
}
```

Map:

```json
{
  "asset_id": "ASSET_MAP_001",
  "type": "image",
  "generation_source": "renderer",
  "visual_level": "GRAPHIC",
  "overlay": {
    "type": "MAP",
    "data": {
      "title": "Ruta reconstruida",
      "points": [
        { "label": "Hotel", "x": 0.32, "y": 0.48 },
        { "label": "Cabina", "x": 0.58, "y": 0.44 },
        { "label": "Último avistamiento", "x": 0.71, "y": 0.61 }
      ],
      "lines": [[0, 1], [1, 2]]
    }
  }
}
```

Quote:

```json
{
  "asset_id": "ASSET_QUOTE_001",
  "type": "image",
  "generation_source": "renderer",
  "visual_level": "GRAPHIC",
  "overlay": {
    "type": "QUOTE",
    "data": {
      "quote": "La llamada nunca apareció en el registro oficial.",
      "source": "Informe policial"
    }
  }
}
```

### V2 Assets You Need To Provide

Add Flow images here:

```text
project/images/ASSET_001.jpeg
project/images/ASSET_002.jpeg
```

Add music here:

```text
assets/music/mystery_01.mp3
assets/music/investigation_01.mp3
assets/music/tension_01.mp3
assets/music/emotional_01.mp3
assets/music/revelation_01.mp3
assets/music/dark_neutral_01.mp3
```

Add ambience here:

```text
assets/ambience/room_tone.mp3
assets/ambience/urban_night.mp3
assets/ambience/rain.mp3
assets/ambience/office.mp3
assets/ambience/forest.mp3
assets/ambience/wind.mp3
assets/ambience/industrial.mp3
assets/ambience/crowd_distant.mp3
assets/ambience/fluorescent_room.mp3
```

The project already includes several SFX. Add these missing V2 staples when possible:

```text
assets/sfx/paper_rustle.mp3
assets/sfx/page_turn.mp3
assets/sfx/typewriter_key.mp3
assets/sfx/phone_ring.mp3
assets/sfx/subtle_whoosh.mp3
```

Add optional brand assets:

```text
assets/fonts/noir_title.ttf
assets/fonts/noir_body.ttf
assets/fonts/mono_evidence.ttf
assets/textures/paper_cream.png
assets/textures/paper_gray.png
assets/textures/ink_grain.png
assets/textures/dust_overlay.png
assets/textures/vignette.png
```

Recommended sources:

- YouTube Audio Library for music/SFX.
- Mixkit for quick commercial-friendly music/SFX.
- Freesound only when each individual license is checked; avoid non-commercial licenses for monetized videos.

### V2 QC

Before rendering, the V2 path writes:

```text
output/qc_report.txt
```

If the report contains blocking errors, rendering aborts before FFmpeg work begins. Current checks include missing assets, empty manifests, short shots, repeated zooms, and overly close `dark_impact` cues.

## Testing

```bash
python -m pytest -q
python -m compileall .
```

## Output Settings

The default export uses:

- H264 video
- AAC audio
- 1920x1080
- 30 fps
- CRF 18
- `+faststart` for web playback
