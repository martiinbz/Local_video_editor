# Render preview and track controls design

## Objective

Make the editor preview use the same rendered media as the final MP4, make track volumes reliably audible and editable, support clearing a complete track, and avoid unnecessary preview preparation without reducing output quality.

## Current findings

- The audio preview is built with the final renderer's FFmpeg audio planner, but is always served at `.cache/editor-audio-preview.m4a`. Replacing a file at a stable URL allows a browser to reuse an earlier audio response.
- The visual monitor is a React/CSS approximation, while the final render uses FFmpeg. Their text layout, font metrics, effects, and motion cannot be exactly equivalent.
- Track-level volume state is propagated to clips, but the UI expresses it as a `0..1` range and editable number fields coerce incomplete values while typing.
- No state operation or timeline control clears every item in a track.

## Chosen architecture

### Content-addressed rendered preview

The backend will serialize the current editor project to its render manifest and derive a deterministic fingerprint from that manifest plus the render configuration. The fingerprint identifies a preview artifact in the project cache.

- A matching completed artifact is returned immediately.
- A changed manifest creates a new artifact and a versioned media URL containing its fingerprint. The browser can therefore never replay an older audio or video response for a newer edit.
- The preview artifact is produced by the same `DocumentaryRenderer` pipeline and render configuration as the final MP4. It is full-quality and contains the same video and audio output. Preview preparation is only skipped when its exact fingerprint is already cached.
- While the final-quality preview is being prepared, the monitor retains its existing frame and shows progress. There is no lower-quality fallback presented as an exact preview.

### Editor controls

Audio volume inputs will expose percent values (`0` to `100`) and convert to the manifest's normalized `0` to `1` value at the component boundary. Both a text input and range control remain synchronized. Text input keeps its draft string during typing and commits a validated number on blur or Enter, allowing users to replace any value freely.

Start, duration, and source trim inputs will follow the same draft-and-commit interaction. Duration is editable where the corresponding clip can be resized; committing it updates the clip boundary through existing state rules. Invalid or incomplete drafts do not overwrite project state.

Every track label receives a destructive `Vaciar pista` action with a confirmation. It removes all clips from audio tracks, all subtitle cues from subtitles, all overlays from a text track, and the narration clip for narration. The visual and effects tracks are excluded from this control in this change.

### Compatibility and validation

The manifest remains the single data source for render and preview. Cache artifacts are disposable and excluded from version control. Existing manifests retain normalized volume values and are displayed as their equivalent percentage.

## Tests

- Frontend state tests for per-track percentage conversion, validated draft commits, and clearing each eligible track.
- Backend tests proving distinct project manifests produce distinct preview fingerprints and URLs, while equal manifests reuse an artifact.
- Renderer/API tests proving the preview endpoint builds from the same manifest and configuration used by final render.
- Component tests for the free-form numeric controls and the track-clear confirmation/action.

## Acceptance criteria

1. A changed volume is audible in the next preview and in the final render, with no stale audio response.
2. Preview media is renderer-produced at final render quality and uses the same settings, including text size and audio mix.
3. A cached unchanged preview opens without regenerating it; changed content regenerates only the necessary preview artifact.
4. Users can type percentage volumes and time values naturally, including temporarily incomplete values while editing.
5. Users can clear all elements from any eligible track in one confirmed action.
