# Timeline interaction improvements

## Goal

Make timeline blocks predictable to move and resize, with CapCut-style cross-track snapping and keyboard deletion.

## Behavior

- Audio clips, subtitles, text overlays, effects, and visual scene boundaries use consistent pointer interactions.
- Dragging a block body moves its interval while preserving its duration.
- Dragging a left or right handle changes the corresponding edge.
- Every interval stays inside the project duration and has a minimum duration of 0.1 seconds.
- Blocks on the same track may not overlap. Invalid moves and resizes are clamped to the nearest valid position rather than rejected unpredictably.
- SFX can be moved and resized like other timed clips.
- Moving or resizing compares both edges of the active block with the edges of blocks on other tracks, the project boundaries, and the playhead. Within 0.2 seconds, the closest matching time is used and a blue vertical guide is shown.
- Delete removes the currently selected audio or visual block and clears selection. Backspace is unchanged.

## Architecture

- Keep timeline calculations in pure functions in `editor/frontend/src/editorState.js`.
- Use one pointer-session path in `AudioTimeline.jsx` for move and resize, with stable pointer capture and document-level cleanup.
- Pass the active snap guide time from the timeline interaction state into the timeline content and render one blue vertical guide.
- Keep scene-boundary editing as a special case because changing a scene duration changes the project duration and subsequent scene positions.

## Testing

- Unit tests cover move and resize for SFX/text, project-boundary clamping, same-track collision prevention, cross-track snapping, and deletion.
- Component tests cover pointer interaction wiring and guide visibility.
- Run the frontend test suite and production build after implementation.
