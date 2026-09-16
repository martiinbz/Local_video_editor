import { describe, expect, it } from 'vitest'
import { addAudioClip, addEffect, addKeyframe, addTextOverlay, addTextTrack, clearTrack, deleteSelection, findSceneAtTime, findSnapTime, insertScene, loadSubtitles, moveAudioClip, moveScene, moveTimedItem, normalizeTrackOrder, reorderTrack, resizeAudioClip, resizeSceneBoundary, resizeTimedItem, shiftSubtitles, snapTime, splitSubtitle, updateNarration, updateProjectFormat, updateScene, updateTrackSettings, updateVisualItem } from './editorState'

const project = {
  duration: 5,
  visualTrack: [
    { sceneId: 'SCENE_1', start: 0, end: 2, duration: 2, motion: 'static' },
    { sceneId: 'SCENE_2', start: 2, end: 5, duration: 3, motion: 'zoom_in' },
  ],
}

describe('editor timeline state', () => {
  it('finds the scene under the playhead', () => {
    expect(findSceneAtTime(project.visualTrack, 3.2).sceneId).toBe('SCENE_2')
  })

  it('updates a scene and recalculates all following times', () => {
    const updated = updateScene(project, 0, { duration: 4, motion: 'pan_left' })

    expect(updated.visualTrack[0]).toMatchObject({ start: 0, end: 4, duration: 4, motion: 'pan_left' })
    expect(updated.visualTrack[1]).toMatchObject({ start: 4, end: 7 })
    expect(updated.duration).toBe(7)
    expect(project.duration).toBe(5)
  })

  it('resizes a scene boundary and keeps the following scenes in cascade', () => {
    const updated = resizeSceneBoundary(project, 0, 3.4)

    expect(updated.visualTrack.map(({ start, end }) => [start, end])).toEqual([[0, 3.4], [3.4, 6.4]])
    expect(updated.duration).toBe(6.4)
  })

  it('reorders a scene and recalculates its consecutive timeline positions', () => {
    const updated = moveScene(project, 1, 0)

    expect(updated.visualTrack.map((scene) => scene.sceneId)).toEqual(['SCENE_2', 'SCENE_1'])
    expect(updated.visualTrack.map(({ start, end }) => [start, end])).toEqual([[0, 3], [3, 5]])
  })

  it('inserts a dragged image as a five-second new scene at the requested position', () => {
    const updated = insertScene(project, 1, 'assets/images/new-evidence.jpg')

    expect(updated.visualTrack.map((scene) => scene.sceneId)).toEqual(['SCENE_1', 'SCENE_3', 'SCENE_2'])
    expect(updated.visualTrack[1]).toMatchObject({ file: 'assets/images/new-evidence.jpg', flowFile: 'assets/images/new-evidence.jpg', duration: 5, start: 2, end: 7 })
    expect(updated.duration).toBe(10)
  })
})

describe('audio timeline state', () => {
  const audioProject = {
    duration: 20,
    visualTrack: [
      { sceneId: 'SCENE_1', start: 0, end: 5, duration: 5 },
      { sceneId: 'SCENE_2', start: 5, end: 20, duration: 15 },
    ],
    musicTrack: [], ambienceTrack: [], sfxTrack: [],
    narrationTrack: { id: 'narration', start: 0, sourceIn: 0, sourceOut: 10, duration: 10, end: 10 },
  }

  it('clears every eligible track without changing other tracks', () => {
    const source = { ...audioProject, narrationTrack: { file: 'project/narration.mp3' }, musicTrack: [{ id: 'music-1' }], ambienceTrack: [{ id: 'ambience-1' }], sfxTrack: [{ id: 'sfx-1' }], subtitleTrack: [{ id: 'subtitle-1' }], textTracks: [{ id: 'text-1', overlays: [{ id: 'overlay-1' }] }] }
    expect(clearTrack(source, 'music').musicTrack).toEqual([])
    expect(clearTrack(source, 'ambience').ambienceTrack).toEqual([])
    expect(clearTrack(source, 'sfx').sfxTrack).toEqual([])
    expect(clearTrack(source, 'subtitles').subtitleTrack).toEqual([])
    expect(clearTrack(source, 'text:text-1').textTracks[0].overlays).toEqual([])
    expect(clearTrack(source, 'narration').narrationTrack.file).toBe('')
  })

  it('snaps to tenths and nearby scene edges', () => {
    expect(snapTime(4.87, audioProject.visualTrack)).toBe(5)
    expect(snapTime(3.141, audioProject.visualTrack)).toBe(3.1)
  })

  it('adds full audio and rejects overlap on music track', () => {
    const asset = { path: 'assets/music/score.mp3', name: 'score.mp3', duration: 6, type: 'music' }
    const first = addAudioClip(audioProject, 'music', asset, 2)
    const collision = addAudioClip(first.project, 'music', asset, 4)

    expect(first.error).toBeNull()
    expect(first.project.musicTrack[0]).toMatchObject({ start: 2, end: 8, duration: 6, loop: true, volume: 0.12 })
    expect(collision.error).toMatch(/solapa/i)
    expect(collision.project.musicTrack).toHaveLength(1)
  })

  it('stretches music beyond source duration for looping', () => {
    const asset = { path: 'assets/music/score.mp3', name: 'score.mp3', duration: 6, type: 'music' }
    const first = addAudioClip(audioProject, 'music', asset, 2)
    const stretched = resizeAudioClip(first.project, 'music', first.project.musicTrack[0].id, 'right', 15)

    expect(stretched.error).toBeNull()
    expect(stretched.project.musicTrack[0]).toMatchObject({ start: 2, end: 15, duration: 13, sourceDuration: 6, loop: true })
  })

  it('keeps SFX on the same track separate and moves clips with snapping', () => {
    const asset = { path: 'assets/sfx/hit.mp3', name: 'hit.mp3', duration: 1, type: 'sfx' }
    const first = addAudioClip(audioProject, 'sfx', asset, 1)
    const second = addAudioClip(first.project, 'sfx', asset, 1.2)
    expect(second.error).toMatch(/solapa/i)
    const secondAtFour = addAudioClip(first.project, 'sfx', asset, 4)
    const moved = moveAudioClip(secondAtFour.project, 'sfx', secondAtFour.project.sfxTrack[1].id, 4.92)

    expect(secondAtFour.project.sfxTrack).toHaveLength(2)
    expect(moved.project.sfxTrack[1].start).toBe(5)
  })

  it('edits narration trim without changing visual scenes', () => {
    const updated = updateNarration(audioProject, { start: 2, sourceIn: 1, sourceOut: 6 })

    expect(updated.narrationTrack).toMatchObject({ start: 2, sourceIn: 1, sourceOut: 6, duration: 5, end: 7 })
    expect(updated.visualTrack).toEqual(audioProject.visualTrack)
    expect(updated.duration).toBe(20)
  })
})

describe('visual and text state', () => {
  const audioProject = {
    duration: 10,
    visualTrack: [{ sceneId: 'SCENE_1', start: 0, end: 10, duration: 10 }],
    sfxTrack: [],
  }
  const visualProject = {
    duration: 10,
    visualTrack: [{ sceneId: 'SCENE_1', start: 0, end: 10, duration: 10, keyframes: [], effects: [] }],
    subtitleTrack: [], textTracks: [],
  }

  it('adds and updates scene keyframes and effects', () => {
    const keyed = addKeyframe(visualProject, 0, 4)
    const effected = addEffect(keyed, 0, 'blur', 2)
    const changed = updateVisualItem(effected, { kind: 'effect', sceneIndex: 0, id: effected.visualTrack[0].effects[0].id }, { intensity: 0.8 })

    expect(keyed.visualTrack[0].keyframes[0]).toMatchObject({ time: 4, scale: 1, x: 0.5, y: 0.5 })
    expect(changed.visualTrack[0].effects[0]).toMatchObject({ type: 'blur', start: 2, end: 4, intensity: 0.8 })
  })

  it('switches to Shorts and centers text and subtitle overlays', () => {
    const source = { ...visualProject, width: 1920, height: 1080, subtitleTrack: [{ id: 'sub', x: 0.2, y: 0.8 }], textTracks: [{ id: 'text', overlays: [{ id: 'title', x: 0.1, y: 0.2 }] }] }
    const vertical = updateProjectFormat(source, 1080, 1920)
    expect(vertical).toMatchObject({ width: 1080, height: 1920 })
    expect(vertical.subtitleTrack[0]).toMatchObject({ x: 0.5, y: 0.5 })
    expect(vertical.textTracks[0].overlays[0]).toMatchObject({ x: 0.5, y: 0.5 })
  })

  it('keeps visual edits inside their scene and project bounds', () => {
    const keyed = addKeyframe(visualProject, 0, 4)
    const effected = addEffect(keyed, 0, 'blur', 2)
    const keyframe = effected.visualTrack[0].keyframes[0]
    const effect = effected.visualTrack[0].effects[0]
    const movedKey = updateVisualItem(effected, { kind: 'keyframe', sceneIndex: 0, id: keyframe.id }, { time: 20 })
    const stretched = updateVisualItem(movedKey, { kind: 'effect', sceneIndex: 0, id: effect.id }, { start: -2, end: 30 })

    expect(stretched.visualTrack[0].keyframes[0].time).toBe(10)
    expect(stretched.visualTrack[0].effects[0]).toMatchObject({ start: 0, end: 10 })
  })

  it('loads, shifts and splits subtitles', () => {
    const loaded = loadSubtitles(visualProject, 'project/subtitles/es.srt', [{ id: 's1', start: 1, end: 3, text: 'Hola mundo' }])
    const shifted = shiftSubtitles(loaded, 0.5)
    const split = splitSubtitle(shifted, 's1', 2.5)

    expect(split.subtitleFile).toBe('project/subtitles/es.srt')
    expect(split.subtitleTrack).toHaveLength(2)
    expect(split.subtitleTrack.map((cue) => [cue.start, cue.end])).toEqual([[1.5, 2.5], [2.5, 3.5]])
  })

  it('creates multiple text tracks and overlays', () => {
    const withTrack = addTextTrack(visualProject)
    const withSecond = addTextTrack(withTrack)
    const withText = addTextOverlay(withSecond, withSecond.textTracks[0].id, 1)

    expect(withText.textTracks.map((track) => track.name)).toEqual(['Texto 1', 'Texto 2'])
    expect(withText.textTracks[0].overlays[0]).toMatchObject({ text: 'Nuevo texto', start: 1, end: 4 })
  })

  it('reorders tracks and applies shared settings to every item', () => {
    const withText = addTextTrack({ ...visualProject, musicTrack: [{ id: 'm1', volume: 0.2 }], trackOrder: ['visual', 'subtitles', 'narration', 'music', 'sfx'] })
    const reordered = reorderTrack(withText, 'music', -1)
    const settings = updateTrackSettings(reordered, `text:${withText.textTracks[0].id}`, { font_size: 42, color: '#00ff00' })
    const subtitles = loadSubtitles(settings, 'project/subtitles/captions.srt', [{ start: 0, end: 1, text: 'Hola' }])

    expect(normalizeTrackOrder(reordered).indexOf('music')).toBeLessThan(normalizeTrackOrder(reordered).indexOf('narration'))
    expect(settings.textTracks[0].overlays).toEqual([])
    expect(subtitles.subtitleTrack[0]).toMatchObject({ font_size: 4 })
  })

  it('moves and resizes a text overlay without crossing another item on its track', () => {
    const timedProject = {
      ...visualProject,
      textTracks: [{ id: 'text-1', overlays: [
        { id: 'text-a', text: 'A', start: 1, end: 3 },
        { id: 'text-b', text: 'B', start: 5, end: 7 },
      ] }],
    }
    const moved = moveTimedItem(timedProject, { kind: 'text', trackId: 'text-1', id: 'text-a' }, 4.9)
    const resized = resizeTimedItem(moved.project, { kind: 'text', trackId: 'text-1', id: 'text-a' }, 'right', 8)

    expect(moved.project.textTracks[0].overlays[0]).toMatchObject({ start: 3, end: 5 })
    expect(resized.project.textTracks[0].overlays[0]).toMatchObject({ start: 3, end: 5 })
  })

  it('resizes SFX from either edge', () => {
    const timedProject = { ...audioProject, sfxTrack: [{ id: 'sfx-1', start: 2, end: 3, duration: 1 }] }
    const left = resizeTimedItem(timedProject, { kind: 'audio', type: 'sfx', id: 'sfx-1' }, 'left', 1)
    const right = resizeTimedItem(left.project, { kind: 'audio', type: 'sfx', id: 'sfx-1' }, 'right', 4)

    expect(right.project.sfxTrack[0]).toMatchObject({ start: 1, end: 4, duration: 3 })
  })

  it('snaps to a block edge across tracks and deletes the selected item', () => {
    const timedProject = {
      ...audioProject,
      sfxTrack: [{ id: 'sfx-1', start: 1, end: 2, duration: 1 }],
      textTracks: [{ id: 'text-1', overlays: [{ id: 'text-1-a', start: 5, end: 6, text: 'A' }] }],
    }
    expect(findSnapTime(4.88, timedProject, { kind: 'audio', type: 'sfx', id: 'sfx-1' })).toMatchObject({ time: 5, snapped: true })
    const deleted = deleteSelection(timedProject, { kind: 'audio', type: 'sfx', id: 'sfx-1' })
    expect(deleted.sfxTrack).toEqual([])
  })
})
