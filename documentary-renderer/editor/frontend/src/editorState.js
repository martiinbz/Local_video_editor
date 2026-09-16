export function findSceneAtTime(scenes, time) {
  if (!scenes?.length) return null
  return scenes.find((scene) => time >= scene.start && time < scene.end) ?? scenes.at(-1)
}

export function updateScene(project, index, changes) {
  const visualTrack = project.visualTrack.map((scene, sceneIndex) =>
    sceneIndex === index ? { ...scene, ...changes } : { ...scene },
  )
  let cursor = 0
  visualTrack.forEach((scene) => {
    const duration = Math.max(0.1, Number(scene.duration) || 0.1)
    scene.duration = Math.round(duration * 1000) / 1000
    scene.start = Math.round(cursor * 1000) / 1000
    cursor += duration
    scene.end = Math.round(cursor * 1000) / 1000
  })
  return { ...project, visualTrack, duration: Math.round(cursor * 1000) / 1000 }
}

export function updateProjectFormat(project, width, height) {
  const vertical = Number(width) === 1080 && Number(height) === 1920
  const center = (item) => vertical ? { ...item, x: 0.5, y: 0.5 } : item
  return {
    ...project, width: Number(width), height: Number(height),
    subtitleTrack: (project.subtitleTrack || []).map(center),
    textTracks: (project.textTracks || []).map((track) => ({ ...track, overlays: (track.overlays || []).map(center) })),
  }
}

function normalizeScenes(project, scenes) {
  let cursor = 0
  const visualTrack = scenes.map((scene, index) => {
    const duration = Math.max(0.1, Number(scene.duration) || 0.1)
    const start = Math.round(cursor * 1000) / 1000
    cursor += duration
    return { ...scene, index, duration: Math.round(duration * 1000) / 1000, start, end: Math.round(cursor * 1000) / 1000 }
  })
  return { ...project, visualTrack, duration: Math.round(cursor * 1000) / 1000 }
}

export function moveScene(project, fromIndex, toIndex) {
  const scenes = [...(project.visualTrack || [])]
  if (fromIndex < 0 || fromIndex >= scenes.length) return project
  const [scene] = scenes.splice(fromIndex, 1)
  const destination = Math.max(0, Math.min(toIndex, scenes.length))
  scenes.splice(destination, 0, scene)
  return normalizeScenes(project, scenes)
}

function nextSceneId(scenes) {
  const highest = scenes.reduce((max, scene) => {
    const match = String(scene.sceneId || '').match(/^SCENE_(\d+)$/i)
    return match ? Math.max(max, Number(match[1])) : max
  }, 0)
  return `SCENE_${highest + 1}`
}

export function insertScene(project, index, file, duration = 5) {
  const scenes = [...(project.visualTrack || [])]
  const sceneId = nextSceneId(scenes)
  const scene = {
    id: sceneId,
    sceneId,
    duration: Math.max(0.1, Number(duration) || 5),
    file,
    flowFile: file,
    motion: 'static',
    motionSpeed: 0.5,
    crop: 'wide',
    focalPoint: [0.5, 0.5],
    transition: 'hard_cut',
    transitionDuration: 0.5,
    beat: '',
    visualType: '',
    visualLevel: '',
    focus: '',
    keyframes: [],
    effects: [],
  }
  scenes.splice(Math.max(0, Math.min(index, scenes.length)), 0, scene)
  return normalizeScenes(project, scenes)
}

export function resizeSceneBoundary(project, index, boundary) {
  const scene = project.visualTrack[index]
  if (!scene) return project
  const minimum = (scene.start || 0) + 0.1
  const maximum = index === project.visualTrack.length - 1 ? Math.max(project.duration, boundary) : project.duration
  const nextBoundary = Math.min(maximum, Math.max(minimum, snapTime(boundary, project.visualTrack)))
  return updateScene(project, index, { duration: nextBoundary - scene.start })
}

export function formatTime(value) {
  const seconds = Math.max(0, Number(value) || 0)
  const minutes = Math.floor(seconds / 60)
  const rest = seconds - minutes * 60
  return `${String(minutes).padStart(2, '0')}:${rest.toFixed(1).padStart(4, '0')}`
}

const TRACK_KEYS = { music: 'musicTrack', ambience: 'ambienceTrack', sfx: 'sfxTrack' }
const DEFAULT_VOLUMES = { music: 0.12, ambience: 0.04, sfx: 0.9 }
let nextAudioId = 1

export function snapTime(value, scenes = []) {
  const rounded = Math.round(Math.max(0, Number(value) || 0) * 10) / 10
  const edges = scenes.flatMap((scene) => [scene.start, scene.end])
  const nearby = edges.find((edge) => Math.abs(edge - value) <= 0.2)
  return Math.round((nearby ?? rounded) * 1000) / 1000
}

function overlaps(track, candidate, ignoredId = null) {
  return track.some((clip) => clip.id !== ignoredId && candidate.start < clip.end && candidate.end > clip.start)
}

function timedCollection(project, selection) {
  if (selection?.kind === 'text') {
    const track = (project.textTracks || []).find((item) => item.id === selection.trackId)
    return { items: track?.overlays || [], replace: (items) => ({ ...project, textTracks: project.textTracks.map((item) => item.id === selection.trackId ? { ...item, overlays: items } : item) }) }
  }
  if (selection?.kind === 'subtitle') return { items: project.subtitleTrack || [], replace: (items) => ({ ...project, subtitleTrack: items }) }
  if (selection?.kind === 'audio') {
    if (selection.type === 'narration') return { items: project.narrationTrack?.file ? [project.narrationTrack] : [], replace: (items) => ({ ...project, narrationTrack: items[0] || { ...project.narrationTrack, file: '' } }) }
    const key = TRACK_KEYS[selection.type]
    return { items: project[key] || [], replace: (items) => ({ ...project, [key]: items }) }
  }
  return null
}

function timedEdges(project, ignoredSelection = null) {
  const edges = [0, project.duration]
  for (const scene of project.visualTrack || []) edges.push(scene.start, scene.end)
  for (const item of project.subtitleTrack || []) {
    if (ignoredSelection?.kind === 'subtitle' && ignoredSelection.id === item.id) continue
    edges.push(item.start, item.end)
  }
  for (const track of project.textTracks || []) for (const item of track.overlays || []) {
    if (ignoredSelection?.kind === 'text' && ignoredSelection.trackId === track.id && ignoredSelection.id === item.id) continue
    edges.push(item.start, item.end)
  }
  for (const type of Object.keys(TRACK_KEYS)) for (const item of project[TRACK_KEYS[type]] || []) {
    if (ignoredSelection?.kind === 'audio' && ignoredSelection.type === type && ignoredSelection.id === item.id) continue
    edges.push(item.start, item.end)
  }
  if (project.narrationTrack?.file && !(ignoredSelection?.kind === 'audio' && ignoredSelection.type === 'narration')) edges.push(project.narrationTrack.start || 0, project.narrationTrack.end || project.duration)
  return edges.filter((edge) => Number.isFinite(edge))
}

export function findSnapTime(value, project, ignoredSelection = null, extraEdges = []) {
  const requested = Math.max(0, Number(value) || 0)
  const candidates = [...timedEdges(project, ignoredSelection), ...extraEdges].filter((edge) => Math.abs(edge - requested) <= 0.2)
  if (!candidates.length) return { time: Math.round(requested * 1000) / 1000, snapped: false, distance: null }
  const time = candidates.sort((a, b) => Math.abs(a - requested) - Math.abs(b - requested))[0]
  return { time: Math.round(time * 1000) / 1000, snapped: true, distance: Math.abs(time - requested) }
}

function validMoveStart(track, requestedStart, duration, projectDuration, ignoredId) {
  const maxStart = Math.max(0, projectDuration - duration)
  const candidates = [requestedStart, 0, maxStart, ...track.filter((item) => item.id !== ignoredId).flatMap((item) => [item.end, item.start - duration])]
    .map((start) => Math.min(maxStart, Math.max(0, start)))
    .filter((start, index, values) => values.indexOf(start) === index)
    .filter((start) => !overlaps(track, { start, end: start + duration }, ignoredId))
  return candidates.sort((a, b) => Math.abs(a - requestedStart) - Math.abs(b - requestedStart))[0] ?? Math.min(maxStart, Math.max(0, requestedStart))
}

export function moveTimedItem(project, selection, requestedStart) {
  const collection = timedCollection(project, selection)
  if (!collection) return { project, error: 'Elemento no encontrado' }
  const current = selection.kind === 'audio' && selection.type === 'narration' ? collection.items[0] : collection.items.find((item) => item.id === selection.id)
  if (!current) return { project, error: 'Elemento no encontrado' }
  const duration = Math.max(0.1, Number(current.duration) || (Number(current.end) - Number(current.start)) || 0.1)
  const start = validMoveStart(collection.items, Math.max(0, Number(requestedStart) || 0), duration, project.duration, selection.id)
  const next = { ...current, start: Math.round(start * 1000) / 1000, end: Math.round((start + duration) * 1000) / 1000, duration: Math.round(duration * 1000) / 1000 }
  return { project: collection.replace(collection.items.map((item) => item.id === selection.id ? next : item)), error: null }
}

export function resizeTimedItem(project, selection, edge, requestedTime) {
  const collection = timedCollection(project, selection)
  if (!collection) return { project, error: 'Elemento no encontrado' }
  const current = selection.kind === 'audio' && selection.type === 'narration' ? collection.items[0] : collection.items.find((item) => item.id === selection.id)
  if (!current) return { project, error: 'Elemento no encontrado' }
  const others = collection.items.filter((item) => item.id !== selection.id)
  const currentStart = Number(current.start) || 0
  const currentEnd = Number(current.end) || currentStart + Math.max(0.1, Number(current.duration) || 0.1)
  let start = currentStart
  let end = currentEnd
  const time = Math.min(project.duration, Math.max(0, Number(requestedTime) || 0))
  if (edge === 'left') {
    const lower = Math.max(0, ...others.filter((item) => item.end <= currentStart).map((item) => item.end))
    start = Math.min(currentEnd - 0.1, Math.max(lower, time))
  } else {
    const upper = Math.min(project.duration, ...others.filter((item) => item.start >= currentEnd).map((item) => item.start), project.duration)
    end = Math.max(currentStart + 0.1, Math.min(upper, time))
  }
  const next = { ...current, start: Math.round(start * 1000) / 1000, end: Math.round(end * 1000) / 1000, duration: Math.round((end - start) * 1000) / 1000 }
  return { project: collection.replace(collection.items.map((item) => item.id === selection.id ? next : item)), error: null }
}

export function addAudioClip(project, type, asset, requestedStart) {
  const trackKey = TRACK_KEYS[type]
  if (!trackKey) return { project, error: 'Tipo de pista no valido' }
  const start = Math.min(project.duration, snapTime(requestedStart, project.visualTrack))
  const sourceDuration = Math.max(0.1, Number(asset.duration) || 0.1)
  const end = Math.min(project.duration, Math.round((start + sourceDuration) * 1000) / 1000)
  const clip = {
    id: asset.id || `${type}-${nextAudioId++}`,
    type,
    file: asset.path,
    name: asset.name,
    start,
    end,
    duration: Math.max(0, end - start),
    sourceDuration,
    loop: type === 'music' || type === 'ambience',
    volume: DEFAULT_VOLUMES[type],
  }
  const track = project[trackKey] || []
  if (overlaps(track, clip)) return { project, error: `El clip se solapa en la pista de ${type}` }
  return { project: { ...project, [trackKey]: [...track, clip] }, error: null }
}

export function resizeAudioClip(project, type, id, edge, requestedTime) {
  if (type === 'sfx') return resizeTimedItem(project, { kind: 'audio', type, id }, edge, requestedTime)
  const trackKey = TRACK_KEYS[type]
  if (!trackKey) return { project, error: 'Este clip no se puede estirar' }
  const track = project[trackKey] || []
  const current = track.find((clip) => clip.id === id)
  if (!current) return { project, error: 'Clip no encontrado' }
  const start = current.start || 0
  const end = current.end ?? start + current.duration
  let candidate = { ...current }
  const time = Math.min(project.duration, Math.max(0, snapTime(requestedTime, project.visualTrack)))
  if (edge === 'left') candidate.start = Math.min(end - 0.1, time)
  else candidate.end = Math.max(start + 0.1, time)
  candidate.duration = Math.round((candidate.end - candidate.start) * 1000) / 1000
  candidate.loop = true
  if (overlaps(track, candidate, id)) return { project, error: `El clip se solapa en la pista de ${type}` }
  return { project: { ...project, [trackKey]: track.map((clip) => clip.id === id ? candidate : clip) }, error: null }
}

export function moveAudioClip(project, type, id, requestedStart) {
  return moveTimedItem(project, { kind: 'audio', type, id }, snapTime(requestedStart, project.visualTrack))
}

export function updateAudioClip(project, type, id, changes) {
  const trackKey = TRACK_KEYS[type]
  return { ...project, [trackKey]: (project[trackKey] || []).map((clip) => {
    if (clip.id !== id) return clip
    const next = { ...clip, ...changes }
    if (changes.duration != null) { next.duration = Math.max(0.1, Number(changes.duration) || 0.1); next.end = next.start + next.duration }
    return next
  }) }
}

export function duplicateSelected(project, selection) {
  if (!selection) return project
  const id = `${selection.id || selection.type || 'item'}-copy-${Date.now()}`
  if (selection.kind === 'scene') {
    const source = project.visualTrack?.[selection.index]
    if (!source) return project
    const copy = { ...source, id, sceneId: `${source.sceneId}_COPY`, index: selection.index + 1 }
    const visualTrack = [...project.visualTrack.slice(0, selection.index + 1), copy, ...project.visualTrack.slice(selection.index + 1)]
    let cursor = 0
    const normalized = visualTrack.map((scene, index) => {
      const duration = Math.max(0.1, Number(scene.duration) || 0.1)
      const next = { ...scene, index, start: Math.round(cursor * 1000) / 1000, end: Math.round((cursor + duration) * 1000) / 1000, duration }
      cursor += duration
      return next
    })
    return { ...project, visualTrack: normalized, duration: Math.round(cursor * 1000) / 1000 }
  }
  if (selection.kind === 'text') return { ...project, textTracks: project.textTracks.map((track) => track.id === selection.trackId ? { ...track, overlays: [...track.overlays, { ...track.overlays.find((item) => item.id === selection.id), id, start: Math.min(project.duration, (track.overlays.find((item) => item.id === selection.id)?.start || 0) + 0.1), end: Math.min(project.duration, (track.overlays.find((item) => item.id === selection.id)?.end || 0) + 0.1) }] } : track) }
  if (selection.kind === 'subtitle') return { ...project, subtitleTrack: [...project.subtitleTrack, { ...project.subtitleTrack.find((item) => item.id === selection.id), id, start: Math.min(project.duration, (project.subtitleTrack.find((item) => item.id === selection.id)?.start || 0) + 0.1) }] }
  if (selection.kind === 'keyframe' || selection.kind === 'effect') return updateVisualScene(project, selection.sceneIndex, (scene) => ({ ...scene, [selection.kind === 'keyframe' ? 'keyframes' : 'effects']: [...(scene[selection.kind === 'keyframe' ? 'keyframes' : 'effects'] || []), { ...scene[selection.kind === 'keyframe' ? 'keyframes' : 'effects'].find((item) => item.id === selection.id), id }] }))
  if (selection.type === 'narration') return { ...project, narrationTrack: { ...project.narrationTrack, start: Math.min(project.duration, (project.narrationTrack.start || 0) + 0.1) } }
  if (selection.type) { const key = `${selection.type}Track`; const item = (project[key] || []).find((clip) => clip.id === selection.id); return item ? { ...project, [key]: [...project[key], { ...item, id, start: Math.min(project.duration, (item.start || 0) + 0.1), end: Math.min(project.duration, (item.end || 0) + 0.1) }] } : project }
  return project
}

export function removeSelected(project, selection) {
  if (!selection) return project
  if (selection.kind) return removeVisualItem(project, selection)
  if (selection.type === 'narration') return { ...project, narrationTrack: { ...project.narrationTrack, file: '' } }
  if (selection.type) return removeAudioClip(project, selection.type, selection.id)
  return project
}

export function removeAudioClip(project, type, id) {
  const trackKey = TRACK_KEYS[type]
  return { ...project, [trackKey]: (project[trackKey] || []).filter((clip) => clip.id !== id) }
}

export function clearTrack(project, trackId) {
  if (trackId === 'narration') return { ...project, narrationTrack: { ...(project.narrationTrack || {}), file: '' } }
  if (trackId === 'subtitles') return { ...project, subtitleTrack: [] }
  if (trackId.startsWith('text:')) {
    const id = trackId.slice(5)
    return { ...project, textTracks: (project.textTracks || []).map((track) => track.id === id ? { ...track, overlays: [] } : track) }
  }
  const key = TRACK_KEYS[trackId]
  return key ? { ...project, [key]: [] } : project
}

export function deleteSelection(project, selection) {
  if (!selection) return project
  if (selection.kind === 'audio') {
    if (selection.type === 'narration') return { ...project, narrationTrack: { ...project.narrationTrack, file: '' } }
    return removeAudioClip(project, selection.type, selection.id)
  }
  return removeVisualItem(project, selection)
}

export function updateNarration(project, changes) {
  const narration = { ...project.narrationTrack, ...changes }
  narration.start = snapTime(narration.start, project.visualTrack)
  narration.sourceIn = Math.max(0, Number(narration.sourceIn) || 0)
  narration.sourceOut = Math.max(narration.sourceIn + 0.1, Number(narration.sourceOut) || narration.sourceIn + 0.1)
  narration.duration = Math.round((narration.sourceOut - narration.sourceIn) * 1000) / 1000
  narration.end = Math.round((narration.start + narration.duration) * 1000) / 1000
  return { ...project, narrationTrack: narration }
}

let nextVisualId = 1

export const DEFAULT_TRACK_ORDER = ['visual', 'effects', 'subtitles', 'narration', 'music', 'ambience', 'sfx']

export function normalizeTrackOrder(project) {
  const known = new Set(DEFAULT_TRACK_ORDER)
  const custom = (project.textTracks || []).map((track) => `text:${track.id}`)
  const requested = Array.isArray(project.trackOrder) ? project.trackOrder : DEFAULT_TRACK_ORDER
  const order = requested.filter((id) => known.has(id) || custom.includes(id))
  return [...order, ...DEFAULT_TRACK_ORDER.filter((id) => !order.includes(id)), ...custom.filter((id) => !order.includes(id))]
}

export function reorderTrack(project, trackId, direction) {
  const order = normalizeTrackOrder(project)
  const index = order.indexOf(trackId)
  const nextIndex = index + direction
  if (index < 0 || nextIndex < 0 || nextIndex >= order.length) return project
  const next = [...order]
  ;[next[index], next[nextIndex]] = [next[nextIndex], next[index]]
  return { ...project, trackOrder: next }
}

export function updateTrackSettings(project, trackId, changes) {
  const trackSettings = { ...(project.trackSettings || {}), [trackId]: { ...(project.trackSettings?.[trackId] || {}), ...changes } }
  let next = { ...project, trackSettings }
  if (trackId === 'subtitles') {
    next.subtitleTrack = (project.subtitleTrack || []).map((item) => ({ ...item, ...changes }))
  } else if (trackId.startsWith('text:')) {
    const id = trackId.slice(5)
    next.textTracks = (project.textTracks || []).map((track) => track.id === id ? { ...track, settings: { ...(track.settings || {}), ...changes }, overlays: track.overlays.map((item) => ({ ...item, ...changes })) } : track)
  } else if (['narration', 'music', 'ambience', 'sfx'].includes(trackId) && changes.volume != null) {
    const key = trackId === 'narration' ? 'narrationTrack' : `${trackId}Track`
    next[key] = trackId === 'narration' ? { ...project[key], volume: changes.volume } : (project[key] || []).map((item) => ({ ...item, volume: changes.volume }))
  }
  return next
}

function updateVisualScene(project, sceneIndex, updater) {
  return {
    ...project,
    visualTrack: project.visualTrack.map((scene, index) => index === sceneIndex ? updater({ ...scene }) : scene),
  }
}

export function addKeyframe(project, sceneIndex, time) {
  return updateVisualScene(project, sceneIndex, (scene) => {
    const keyframe = { id: `keyframe-${nextVisualId++}`, time: Math.min(scene.duration, Math.max(0, Math.round(time * 10) / 10)), scale: 1, x: 0.5, y: 0.5, rotation: 0 }
    scene.keyframes = [...(scene.keyframes || []), keyframe].sort((a, b) => a.time - b.time)
    return scene
  })
}

export function addEffect(project, sceneIndex, type, time) {
  return updateVisualScene(project, sceneIndex, (scene) => {
    const start = Math.min(scene.duration - 0.1, Math.max(0, Math.round(time * 10) / 10))
    const effect = { id: `effect-${nextVisualId++}`, type, start, end: Math.min(scene.duration, start + 2), intensity: 0.5, enabled: true, params: {} }
    scene.effects = [...(scene.effects || []), effect]
    return scene
  })
}

export function updateVisualItem(project, selection, changes) {
  if (selection.kind === 'keyframe' || selection.kind === 'effect') {
    const key = selection.kind === 'keyframe' ? 'keyframes' : 'effects'
    return updateVisualScene(project, selection.sceneIndex, (scene) => {
      scene[key] = (scene[key] || []).map((item) => {
        if (item.id !== selection.id) return item
        const next = { ...item, ...changes }
        if (selection.kind === 'keyframe') next.time = Math.min(scene.duration, Math.max(0, Number(next.time) || 0))
        else {
          next.start = Math.min(scene.duration - 0.1, Math.max(0, Number(next.start) || 0))
          next.end = Math.min(scene.duration, Math.max(next.start + 0.1, Number(next.end) || next.start + 0.1))
        }
        return next
      })
      if (selection.kind === 'keyframe') scene[key].sort((a, b) => a.time - b.time)
      return scene
    })
  }
  if (selection.kind === 'subtitle') {
    return { ...project, subtitleTrack: (project.subtitleTrack || []).map((item) => item.id === selection.id ? clampTimedItem({ ...item, ...changes }, project.duration) : item) }
  }
  if (selection.kind === 'text') {
    return { ...project, textTracks: (project.textTracks || []).map((track) => track.id === selection.trackId ? { ...track, overlays: track.overlays.map((item) => item.id === selection.id ? clampTimedItem({ ...item, ...changes }, project.duration) : item) } : track) }
  }
  return project
}

function clampTimedItem(item, duration) {
  const start = Math.min(Math.max(0, duration - 0.1), Math.max(0, Number(item.start) || 0))
  const end = Math.min(duration, Math.max(start + 0.1, Number(item.end) || start + 0.1))
  return { ...item, start, end }
}

export function removeVisualItem(project, selection) {
  if (selection.kind === 'keyframe' || selection.kind === 'effect') {
    const key = selection.kind === 'keyframe' ? 'keyframes' : 'effects'
    return updateVisualScene(project, selection.sceneIndex, (scene) => ({ ...scene, [key]: (scene[key] || []).filter((item) => item.id !== selection.id) }))
  }
  if (selection.kind === 'subtitle') return { ...project, subtitleTrack: project.subtitleTrack.filter((item) => item.id !== selection.id) }
  if (selection.kind === 'text') return { ...project, textTracks: project.textTracks.map((track) => track.id === selection.trackId ? { ...track, overlays: track.overlays.filter((item) => item.id !== selection.id) } : track) }
  return project
}

export function loadSubtitles(project, path, cues) {
  const settings = { ...(project.trackSettings?.subtitles || {}), font_size: project.trackSettings?.subtitles?.font_size ?? 4 }
  return { ...project, subtitleFile: path, trackSettings: { ...(project.trackSettings || {}), subtitles: settings }, subtitleTrack: cues.map((cue, index) => ({ ...cue, id: cue.id || `subtitle-${index + 1}`, font_size: settings.font_size, ...settings })) }
}

export function shiftSubtitles(project, delta) {
  return { ...project, subtitleTrack: (project.subtitleTrack || []).map((cue) => ({ ...cue, start: Math.max(0, cue.start + delta), end: Math.max(0.1, cue.end + delta) })) }
}

export function splitSubtitle(project, id, time) {
  const result = []
  for (const cue of project.subtitleTrack || []) {
    if (cue.id !== id || time <= cue.start || time >= cue.end) result.push(cue)
    else result.push({ ...cue, end: time }, { ...cue, id: `${cue.id}-split-${nextVisualId++}`, start: time })
  }
  return { ...project, subtitleTrack: result }
}

export function mergeSubtitle(project, id) {
  const cues = [...(project.subtitleTrack || [])]
  const index = cues.findIndex((cue) => cue.id === id)
  if (index < 0 || index >= cues.length - 1) return project
  cues.splice(index, 2, { ...cues[index], end: cues[index + 1].end, text: `${cues[index].text}\n${cues[index + 1].text}` })
  return { ...project, subtitleTrack: cues }
}

export function addTextTrack(project) {
  const number = (project.textTracks || []).length + 1
  return { ...project, textTracks: [...(project.textTracks || []), { id: `text-track-${nextVisualId++}`, name: `Texto ${number}`, settings: { font_size: 56, color: '#ffffff' }, overlays: [] }] }
}

export function addTextOverlay(project, trackId, start) {
  const settings = project.trackSettings?.[trackId] || project.textTracks?.find((track) => track.id === trackId)?.settings || {}
  const overlay = {
    id: `text-${nextVisualId++}`, text: 'Nuevo texto', start, end: Math.min(project.duration, start + 3),
    font: '', font_size: 56, color: '#ffffff', opacity: 1, bold: false, italic: false, underline: false,
    align: 'center', x: 0.5, y: 0.5, outline: 2, shadow: 0, animation_in: 'fade', animation_out: 'fade', transition_duration: 0.3,
    ...settings,
  }
  return { ...project, textTracks: project.textTracks.map((track) => track.id === trackId ? { ...track, overlays: [...track.overlays, overlay] } : track) }
}
