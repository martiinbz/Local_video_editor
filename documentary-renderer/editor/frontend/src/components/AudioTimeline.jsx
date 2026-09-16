import { useState } from 'react'
import { ArrowDown, ArrowUp, Captions, ChevronDown, Film, Gem, Headphones, Music2, Plus, Settings, Sparkles, Trash2, Trees, Type, Volume2, VolumeX } from 'lucide-react'
import { api } from '../api'
import { findSnapTime, formatTime, normalizeTrackOrder } from '../editorState'
import { Waveform } from './Waveform'

const AUDIO_TRACKS = [['narration', 'Narracion', Volume2], ['music', 'Musica', Music2], ['ambience', 'Ambiente', Trees], ['sfx', 'SFX', Sparkles]]

function AudioClip({ type, clip, px, selected, onSelect, beginPointer }) {
  const start = clip.start || 0
  const duration = clip.duration ?? Math.max(0.1, (clip.end || 0) - start)
  const name = (clip.file || clip.name || type).split('/').at(-1)
  const resize = (event, edge) => { event.preventDefault(); event.stopPropagation(); beginPointer(event, { kind: 'audio', type, id: clip.id || type }, edge, edge === 'left' ? start : start + duration) }
  return <button aria-label={`Seleccionar audio ${name}`} className={`audio-clip ${type} ${selected ? 'selected' : ''}`} style={{ left: start * px, width: Math.max(type === 'sfx' ? 28 : 42, duration * px) }} onClick={() => onSelect(type, clip.id || type)} onPointerDown={(event) => beginPointer(event, { kind: 'audio', type, id: clip.id || type }, 'move', start)}>
    <i className="resize-handle left" aria-label={`Ajustar inicio de ${name}`} onPointerDown={(event) => resize(event, 'left')} /><Waveform path={clip.file} /><span>{name}</span><i className="resize-handle right" aria-label={`Ajustar final de ${name}`} onPointerDown={(event) => resize(event, 'right')} />
  </button>
}

function VisualClip({ selection, label, start, end, px, selected, onSelect, beginPointer }) {
  const resize = (event, edge) => { event.preventDefault(); event.stopPropagation(); beginPointer(event, selection, edge, edge === 'left' ? start : end) }
  return <button className={`visual-item-clip ${selection.kind} ${selected ? 'selected' : ''}`} aria-label={`Seleccionar ${selection.kind === 'subtitle' ? 'subtitulo ' : ''}${label}`} style={{ left: start * px, width: Math.max(24, (end - start) * px) }} onClick={() => onSelect(selection)} onPointerDown={(event) => beginPointer(event, selection, 'move', start)}><i className="resize-handle left" aria-label={`Ajustar inicio de ${label}`} onPointerDown={(event) => resize(event, 'left')} /><span>{label}</span><i className="resize-handle right" aria-label={`Ajustar final de ${label}`} onPointerDown={(event) => resize(event, 'right')} /></button>
}

function TrackLabel({ id, label, Icon, audio, trackState, onMute, onSolo, onSettings, onReorder, onAddText, onClear }) {
  const clearable = audio || id === 'subtitles' || id.startsWith('text:')
  return <div className="track-label"><Icon size={13} /><span>{label}</span><button title={`Subir ${label}`} onClick={() => onReorder(id, -1)}><ArrowUp size={10} /></button><button title={`Bajar ${label}`} onClick={() => onReorder(id, 1)}><ArrowDown size={10} /></button><button title={`Ajustes de ${label}`} aria-label={`Ajustes de ${label}`} onClick={() => onSettings(id)}><Settings size={11} /></button>{id.startsWith('text:') && <button aria-label={`Anadir texto a ${label}`} onClick={() => onAddText(id.slice(5))}><Plus size={12} /></button>}{clearable && <button title={`Vaciar ${label}`} aria-label={`Vaciar ${label}`} onClick={() => onClear(id, label)}><Trash2 size={11} /></button>}{audio && <><button className={trackState.muted.has(id) ? 'active' : ''} title={`Silenciar ${label}`} onClick={() => onMute(id)}>{trackState.muted.has(id) ? <VolumeX size={11} /> : <Volume2 size={11} />}</button><button className={trackState.solo === id ? 'active' : ''} title={`Solo ${label}`} onClick={() => onSolo(id)}><Headphones size={11} /></button></>}</div>
}

export function AudioTimeline({ project, selectedScene, selectedAudio, selectedVisual, currentTime, zoom, trackState, onSelectScene, onSelectAudio, onSelectVisual, onOpenTrackSettings, onReorderTrack, onSeek, onInsertImage, onMoveScene, onDropAudio, onResizeScene, onResizeAudio, onMoveTimed, onResizeTimed, onMute, onSolo, onAddTextOverlay, onClearTrack }) {
  const px = zoom
  const width = Math.max(900, project.duration * px)
  const textTracks = project.textTracks || []
  const order = normalizeTrackOrder(project)
  const tracks = { narration: project.narrationTrack?.file ? [project.narrationTrack] : [], music: project.musicTrack || [], ambience: project.ambienceTrack || [], sfx: project.sfxTrack || [] }
  const [snapGuide, setSnapGuide] = useState(null)
  const selected = (item) => selectedVisual?.kind === item.kind && selectedVisual?.id === item.id
  const durationFor = (selection) => {
    if (selection.kind === 'audio') {
      const items = selection.type === 'narration' ? [project.narrationTrack] : (tracks[selection.type] || [])
      const item = items.find((value) => value && (selection.type === 'narration' || value.id === selection.id))
      return item ? Math.max(0.1, Number(item.duration) || ((item.end || 0) - (item.start || 0))) : 0.1
    }
    if (selection.kind === 'subtitle') { const item = (project.subtitleTrack || []).find((value) => value.id === selection.id); return item ? Math.max(0.1, item.end - item.start) : 0.1 }
    if (selection.kind === 'text') { const track = textTracks.find((value) => value.id === selection.trackId); const item = track?.overlays.find((value) => value.id === selection.id); return item ? Math.max(0.1, item.end - item.start) : 0.1 }
    if (selection.kind === 'effect') { const scene = project.visualTrack[selection.sceneIndex]; const item = scene?.effects?.find((value) => value.id === selection.id); return item ? Math.max(0.1, item.end - item.start) : 0.1 }
    return 0.1
  }

  const beginPointer = (event, selection, mode, anchor) => {
    event.preventDefault(); event.stopPropagation()
    const pointerTarget = event.currentTarget
    const pointerId = event.pointerId
    pointerTarget.setPointerCapture?.(pointerId)
    if (selection.kind === 'audio') onSelectAudio(selection.type, selection.id)
    else onSelectVisual(selection)
    const content = event.currentTarget.closest('.timeline-content')
    const pointerTime = (event.clientX - content.getBoundingClientRect().left) / px
    const offset = mode === 'move' ? pointerTime - anchor : 0
    const emit = (phase, clientX) => {
      const rawTime = (clientX - content.getBoundingClientRect().left) / px
      const requested = mode === 'move' ? rawTime - offset : rawTime
      if (mode === 'move') {
        const duration = durationFor(selection)
        const startSnap = findSnapTime(requested, project, selection)
        const endSnap = findSnapTime(requested + duration, project, selection)
        const chosen = endSnap.snapped && (!startSnap.snapped || endSnap.distance < startSnap.distance)
          ? { start: endSnap.time - duration, guide: endSnap.time, snapped: true }
          : { start: startSnap.time, guide: startSnap.time, snapped: startSnap.snapped }
        setSnapGuide(chosen.snapped ? chosen.guide : null)
        onMoveTimed(selection, chosen.start, phase, chosen.guide)
      } else {
        const snapped = findSnapTime(requested, project, selection)
        setSnapGuide(snapped.snapped ? snapped.time : null)
        if (selection.kind === 'audio') onResizeTimed(selection.type, selection.id, mode, snapped.time, phase, snapped.time)
        else onResizeTimed(selection, selection.id, mode, snapped.time, phase, snapped.time)
      }
    }
    const move = (nextEvent) => emit('move', nextEvent.clientX)
    const finish = (endEvent) => { emit('end', endEvent.clientX); setSnapGuide(null); pointerTarget.releasePointerCapture?.(pointerId); document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', finish) }
    document.addEventListener('pointermove', move); document.addEventListener('pointerup', finish, { once: true })
  }

  const resizeScene = (event, sceneIndex) => {
    event.preventDefault(); event.stopPropagation()
    const content = event.currentTarget.closest('.timeline-content'); let last = project.visualTrack[sceneIndex].end
    const update = (move) => { last = (move.clientX - content.getBoundingClientRect().left) / px; onResizeScene(sceneIndex, last, 'move') }
    const finish = () => { document.removeEventListener('pointermove', update); onResizeScene(sceneIndex, last, 'end') }
    onResizeScene(sceneIndex, (event.clientX - content.getBoundingClientRect().left) / px, 'start')
    document.addEventListener('pointermove', update); document.addEventListener('pointerup', finish, { once: true })
  }

  const labelFor = (id) => id.startsWith('text:') ? textTracks.find((track) => track.id === id.slice(5))?.name : ({ visual: 'Visual', effects: 'Efectos', subtitles: 'Subtitulos', narration: 'Narracion', music: 'Musica', ambience: 'Ambiente', sfx: 'SFX' }[id])
  const iconFor = (id) => ({ visual: Film, effects: Sparkles, subtitles: Captions, narration: Volume2, music: Music2, ambience: Trees, sfx: Sparkles }[id] || Type)

  const renderRow = (id) => {
    if (id === 'visual') return <div className="track visual-track">{project.visualTrack.map((scene, index) => <button key={scene.sceneId} draggable aria-label={`Seleccionar ${scene.sceneId}`} className={`scene-clip ${selectedScene === index ? 'selected' : ''}`} style={{ left: scene.start * px, width: Math.max(46, scene.duration * px) }} onClick={() => onSelectScene(index)} onDragStart={(event) => { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('application/x-editor-scene', String(index)) }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const rect = event.currentTarget.getBoundingClientRect(); const insertionIndex = index + (event.clientX >= rect.left + rect.width / 2 ? 1 : 0); const image = event.dataTransfer.getData('application/x-editor-media'); const movedIndex = event.dataTransfer.getData('application/x-editor-scene'); if (image) onInsertImage(insertionIndex, image); else if (movedIndex !== '') { const from = Number(movedIndex); onMoveScene(from, from < insertionIndex ? insertionIndex - 1 : insertionIndex) } }}>
      {index > 0 && <i className="scene-resize-handle left" aria-label={`Ajustar inicio de ${scene.sceneId}`} onPointerDown={(event) => resizeScene(event, index - 1)} />}<img src={api.mediaUrl(scene.file || scene.flowFile, project.projectId)} alt="" /><span className="clip-id">{scene.sceneId}</span><span className="clip-detail">{scene.duration.toFixed(1)}s · {scene.motion}</span>{scene.transition !== 'hard_cut' && <i className="transition-mark" title={scene.transition}><ChevronDown size={11} /></i>}{(scene.keyframes || []).map((keyframe) => <span role="button" key={keyframe.id} className={`keyframe-marker ${selected({ kind: 'keyframe', id: keyframe.id }) ? 'selected' : ''}`} aria-label={`Seleccionar keyframe ${scene.sceneId} ${keyframe.time.toFixed(1)}`} style={{ left: keyframe.time * px }} onClick={(event) => { event.stopPropagation(); onSelectVisual({ kind: 'keyframe', sceneIndex: index, id: keyframe.id }) }}><Gem size={10} /></span>)}<i className="scene-resize-handle right" aria-label={`Ajustar final de ${scene.sceneId}`} onPointerDown={(event) => resizeScene(event, index)} /></button>)}</div>
    if (id === 'effects') return <div className="track visual-effects-track">{project.visualTrack.flatMap((scene, sceneIndex) => (scene.effects || []).map((effect) => <VisualClip key={effect.id} selection={{ kind: 'effect', sceneIndex, id: effect.id }} label={effect.type} start={scene.start + effect.start} end={scene.start + effect.end} px={px} selected={selected({ kind: 'effect', id: effect.id })} onSelect={onSelectVisual} beginPointer={beginPointer} />))}</div>
    if (id === 'subtitles') return <div className="track subtitle-track">{(project.subtitleTrack || []).map((cue) => <VisualClip key={cue.id} selection={{ kind: 'subtitle', id: cue.id }} label={cue.text} start={cue.start} end={cue.end} px={px} selected={selected({ kind: 'subtitle', id: cue.id })} onSelect={onSelectVisual} beginPointer={beginPointer} />)}</div>
    if (id.startsWith('text:')) { const track = textTracks.find((item) => item.id === id.slice(5)); return <div className="track free-text-track">{(track?.overlays || []).map((overlay) => <VisualClip key={overlay.id} selection={{ kind: 'text', trackId: track.id, id: overlay.id }} label={overlay.text} start={overlay.start} end={overlay.end} px={px} selected={selected({ kind: 'text', id: overlay.id })} onSelect={onSelectVisual} beginPointer={beginPointer} />)}</div> }
    return <div className={`track audio-track ${id}-track`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const raw = event.dataTransfer.getData('application/x-audio-asset'); if (raw) { const rect = event.currentTarget.getBoundingClientRect(); onDropAudio(id, JSON.parse(raw), (event.clientX - rect.left) / px) } }}>{(tracks[id] || []).map((clip) => <AudioClip key={clip.id || id} type={id} clip={clip} px={px} selected={selectedAudio?.type === id && selectedAudio?.id === (clip.id || id)} onSelect={onSelectAudio} beginPointer={beginPointer} />)}</div>
  }

  return <section className="timeline-shell"><div className="timeline-body"><div className="track-labels"><div className="ruler-spacer" />{order.map((id) => <TrackLabel key={id} id={id} label={labelFor(id)} Icon={iconFor(id)} audio={AUDIO_TRACKS.some(([type]) => type === id)} trackState={trackState} onMute={onMute} onSolo={onSolo} onSettings={onOpenTrackSettings} onReorder={onReorderTrack} onAddText={onAddTextOverlay} onClear={onClearTrack} />)}</div><div className="timeline-scroll"><div className="timeline-content" style={{ width, minHeight: 28 + order.length * 46 }} onClick={(event) => { if (event.target.closest('button')) return; const rect = event.currentTarget.getBoundingClientRect(); onSeek(Math.min(project.duration, Math.max(0, (event.clientX - rect.left) / px))) }}><div className="ruler">{Array.from({ length: Math.ceil(project.duration / 10) + 1 }, (_, index) => <span key={index} style={{ left: index * 10 * px }}>{formatTime(index * 10)}</span>)}</div>{order.map((id) => <div key={id}>{renderRow(id)}</div>)}{snapGuide != null && <div className="snap-guide" style={{ left: snapGuide * px }} aria-label={`Ajuste en ${formatTime(snapGuide)}`} />}<div className="playhead" style={{ left: currentTime * px }}><i /></div></div></div></div></section>
}
