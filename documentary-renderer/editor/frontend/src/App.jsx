import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check, ChevronDown, CircleAlert, Film, FolderOpen, Image, LoaderCircle,
  Gem, Maximize2, Minimize2, Music2, Pause, Play, Plus, RotateCcw, Save, SlidersHorizontal, Sparkles, Undo2, Volume2, X,
} from 'lucide-react'
import { api } from './api'
import { addAudioClip, addEffect, addKeyframe, addTextOverlay, addTextTrack, clearTrack, deleteSelection, duplicateSelected, findSceneAtTime, formatTime, insertScene, loadSubtitles, mergeSubtitle, moveAudioClip, moveScene, moveTimedItem, normalizeTrackOrder, removeAudioClip, removeSelected, removeVisualItem, reorderTrack, resizeAudioClip, resizeSceneBoundary, resizeTimedItem, shiftSubtitles, splitSubtitle, updateAudioClip, updateNarration, updateProjectFormat, updateScene, updateTrackSettings, updateVisualItem } from './editorState'
import { AudioEngine } from './AudioEngine'
import { AudioLibrary } from './components/AudioLibrary'
import { AudioTimeline } from './components/AudioTimeline'
import { AudioInspector } from './components/AudioInspector'
import { VisualInspector } from './components/VisualInspector'
import { TrackSettingsInspector } from './components/TrackSettingsInspector'

const MOTIONS = [
  'static', 'zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'pan_up', 'pan_down',
  'zoom_left', 'zoom_right', 'zoom_up', 'zoom_down', 'focal_zoom', 'crop_push',
]
const TRANSITIONS = ['hard_cut', 'fade', 'crossfade', 'dip_to_black']
const CROPS = ['wide', 'medium', 'close', 'focal']
const readSession = (key) => {
  try {
    if (typeof window === 'undefined' || typeof window.localStorage?.getItem !== 'function') return null
    return JSON.parse(window.localStorage.getItem(key) || 'null')
  } catch { return null }
}
const writeSession = (key, value) => {
  try {
    if (typeof window !== 'undefined' && typeof window.localStorage?.setItem === 'function') window.localStorage.setItem(key, JSON.stringify(value))
  } catch { /* storage can be unavailable in private/browser test contexts */ }
}

function normalizeEditorIds(project) {
  return {
    ...project,
    visualTrack: (project.visualTrack || []).map((scene, sceneIndex) => ({
      ...scene,
      keyframes: (scene.keyframes || []).map((item, index) => ({ ...item, id: item.id || `${scene.sceneId}-keyframe-${index + 1}` })),
      effects: (scene.effects || []).map((item, index) => ({ ...item, id: item.id || `${scene.sceneId}-effect-${index + 1}` })),
    })),
    subtitleTrack: (project.subtitleTrack || []).map((item, index) => ({ ...item, id: item.id || `subtitle-${index + 1}` })),
    textTracks: (project.textTracks || []).map((track, trackIndex) => ({
      ...track, id: track.id || `text-track-${trackIndex + 1}`,
      overlays: (track.overlays || []).map((item, index) => ({ ...item, id: item.id || `text-${trackIndex + 1}-${index + 1}` })),
    })),
    trackOrder: normalizeTrackOrder(project),
    trackSettings: { subtitles: { font_size: 4 }, ...(project.trackSettings || {}) },
  }
}

function interpolateKeyframes(scene, time) {
  const keys = [...(scene?.keyframes || [])].sort((a, b) => a.time - b.time)
  if (!keys.length) return null
  if (time <= keys[0].time) return keys[0]
  if (time >= keys.at(-1).time) return keys.at(-1)
  const right = keys.find((key) => key.time >= time)
  const left = keys[keys.indexOf(right) - 1]
  const progress = (time - left.time) / Math.max(0.001, right.time - left.time)
  const value = (field, fallback) => (left[field] ?? fallback) + ((right[field] ?? fallback) - (left[field] ?? fallback)) * progress
  return { scale: value('scale', 1), x: value('x', 0.5), y: value('y', 0.5), rotation: value('rotation', 0) }
}

export function previewScaleForWidth(width, canvasWidth = 1920) {
  return width > 0 ? width / canvasWidth : 1
}

function overlayStyle(item, currentTime, fontFamily, previewScale) {
  const duration = Math.max(0.01, item.transition_duration || 0.3)
  const entering = Math.min(1, Math.max(0, (currentTime - item.start) / duration))
  const leaving = Math.min(1, Math.max(0, (item.end - currentTime) / duration))
  const progress = Math.min(entering, leaving)
  const animation = entering < 1 ? item.animation_in : leaving < 1 ? item.animation_out : 'none'
  let translateX = '-50%'; let translateY = '-50%'
  if (animation === 'slide_left') translateX = `calc(-50% + ${(1 - progress) * (entering < 1 ? -100 : 100)}%)`
  if (animation === 'slide_right') translateX = `calc(-50% + ${(1 - progress) * (entering < 1 ? 100 : -100)}%)`
  if (animation === 'slide_up') translateY = `calc(-50% + ${(1 - progress) * (entering < 1 ? -100 : 100)}%)`
  if (animation === 'slide_down') translateY = `calc(-50% + ${(1 - progress) * (entering < 1 ? 100 : -100)}%)`
  return {
    left: `${(item.x ?? 0.5) * 100}%`, top: `${(item.y ?? 0.85) * 100}%`,
    transform: `translate(${translateX}, ${translateY})`, color: item.color || '#ffffff',
    opacity: (item.opacity ?? 1) * ((item.animation_in === 'fade' || item.animation_out === 'fade') ? progress : 1),
    fontFamily, fontSize: `${Math.max(1, (item.font_size || 48) * previewScale)}px`,
    fontWeight: item.bold ? 700 : 400, fontStyle: item.italic ? 'italic' : 'normal', textDecoration: item.underline ? 'underline' : 'none',
    textAlign: item.align || 'center', whiteSpace: 'pre-line', textShadow: item.outline ? `0 0 ${Math.max(1, item.outline * previewScale)}px #000, 0 ${Math.max(1, previewScale)}px ${Math.max(1, 2 * previewScale)}px #000` : 'none',
  }
}

function ScenePreview({ project, scene, currentTime, playing }) {
  const [failed, setFailed] = useState(false)
  const previewRef = useRef(null)
  const [previewScale, setPreviewScale] = useState(1)
  useEffect(() => {
    const element = previewRef.current
    if (!element) return undefined
    const update = () => setPreviewScale(previewScaleForWidth(element.clientWidth, project.width || 1920))
    update()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(update)
    observer?.observe(element)
    window.addEventListener('resize', update)
    return () => { observer?.disconnect(); window.removeEventListener('resize', update) }
  }, [project.width])
  if (!scene) return <div className="preview-empty"><Film size={36} /><span>Sin escena</span></div>
  const localTime = Math.max(0, currentTime - scene.start)
  const keyframe = interpolateKeyframes(scene, localTime)
  const effects = (scene.effects || []).filter((effect) => effect.enabled !== false && localTime >= effect.start && localTime <= effect.end)
  const amount = (type) => effects.find((effect) => effect.type === type)?.intensity || 0
  const filters = []
  if (amount('blur')) filters.push(`blur(${amount('blur') * 10}px)`)
  if (amount('brightness')) filters.push(`brightness(${1 + amount('brightness') * 0.6})`)
  if (amount('contrast')) filters.push(`contrast(${1 + amount('contrast')})`)
  if (amount('saturation')) filters.push(`saturate(${1 + amount('saturation') * 2})`)
  if (amount('grayscale')) filters.push(`grayscale(${amount('grayscale')})`)
  if (amount('chromatic_aberration')) filters.push(`drop-shadow(${amount('chromatic_aberration') * 5}px 0 #ff003388) drop-shadow(${-amount('chromatic_aberration') * 5}px 0 #00d9ff88)`)
  const imageStyle = keyframe ? {
    transform: `translate(${(0.5 - keyframe.x) * 100}%, ${(0.5 - keyframe.y) * 100}%) scale(${keyframe.scale}) rotate(${keyframe.rotation || 0}deg)`,
    filter: filters.join(' '),
  } : { filter: filters.join(' ') }
  if (amount('shake')) imageStyle.translate = `${Math.sin(currentTime * 45) * amount('shake') * 8}px ${Math.cos(currentTime * 39) * amount('shake') * 6}px`
  const activeSubtitles = (project.subtitleTrack || []).filter((item) => currentTime >= item.start && currentTime <= item.end)
  const activeTexts = (project.textTracks || []).flatMap((track) => track.overlays || []).filter((item) => currentTime >= item.start && currentTime <= item.end)
  const fontFamily = (path) => project.fontLibrary?.find((font) => font.path === path)?.family || 'inherit'
  const style = {
    '--motion-duration': `${Math.max(0.2, scene.duration)}s`,
    '--focal-x': `${(scene.focalPoint?.[0] ?? 0.5) * 100}%`,
    '--focal-y': `${(scene.focalPoint?.[1] ?? 0.5) * 100}%`,
    '--preview-ratio': `${project.width || 1920} / ${project.height || 1080}`,
    aspectRatio: `${project.width || 1920} / ${project.height || 1080}`,
    height: (project.width || 1920) < (project.height || 1080) ? '100%' : undefined,
    width: (project.width || 1920) < (project.height || 1080) ? 'auto' : undefined,
  }
  return (
    <div ref={previewRef} className={`preview-media crop-${scene.crop || 'wide'}`} style={style}>
      {failed ? (
        <div className="preview-empty"><Image size={36} /><span>Archivo no disponible</span></div>
      ) : (
        <img
          key={`${scene.sceneId}-${playing}`}
          className={playing ? `motion-${scene.motion}` : ''}
          style={imageStyle}
          src={api.mediaUrl(scene.file || scene.flowFile, project.projectId)}
          alt={scene.sceneId}
          onError={() => setFailed(true)}
        />
      )}
      {amount('vignette') > 0 && <div className="preview-vignette" style={{ opacity: amount('vignette') }} />}
      {amount('flash') > 0 && <div className="preview-flash" style={{ opacity: amount('flash') * 0.75 }} />}
      {amount('film_grain') > 0 && <div className="preview-grain" style={{ opacity: amount('film_grain') * 0.35 }} />}
      {activeSubtitles.map((item) => <div className="preview-subtitle" key={item.id} style={overlayStyle({ ...item, x: item.x ?? 0.5, y: item.y ?? 0.87, font_size: item.font_size ?? 48, outline: item.outline ?? 3 }, currentTime, fontFamily(item.font), previewScale)}>{item.text}</div>)}
      {activeTexts.map((item) => <div className="preview-text" data-testid="preview-text" key={item.id} style={overlayStyle(item, currentTime, fontFamily(item.font), previewScale)}>{item.text}</div>)}
      <div className="frame-label">{scene.sceneId}</div>
    </div>
  )
}

function Library({ files }) {
  const [tab, setTab] = useState('images')
  const tabs = [
    ['images', Image, 'Imagenes'], ['music', Music2, 'Musica'], ['sfx', Sparkles, 'SFX'],
  ]
  return (
    <aside className="library panel">
      <div className="panel-title"><FolderOpen size={16} /><h2>Archivos</h2></div>
      <div className="segmented" aria-label="Tipo de archivo">
        {tabs.map(([key, Icon, label]) => (
          <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)} title={label}>
            <Icon size={15} /><span>{label}</span>
          </button>
        ))}
      </div>
      <div className="asset-list">
        {(files?.[tab] || []).map((path) => (
          <div
            className="asset-item" key={path} draggable={tab === 'images'}
            onDragStart={(event) => event.dataTransfer.setData('application/x-editor-media', path)}
          >
            <div className={`asset-thumb ${tab}`}>
              {tab === 'images' ? <img src={api.mediaUrl(path)} alt="" /> : tab === 'music' ? <Music2 size={18} /> : <Volume2 size={18} />}
            </div>
            <span title={path}>{path.split('/').at(-1)}</span>
          </div>
        ))}
        {!(files?.[tab] || []).length && <div className="empty-list">No hay archivos</div>}
      </div>
    </aside>
  )
}

function Field({ label, children, wide = false }) {
  return <label className={`field ${wide ? 'wide' : ''}`}><span>{label}</span>{children}</label>
}

function DurationInput({ value, onChange }) {
  const [draft, setDraft] = useState(String(value))
  useEffect(() => setDraft(String(value)), [value])
  return <input aria-label="Duracion" type="number" min="0.1" step="0.1" value={draft}
    onChange={(event) => {
      setDraft(event.target.value)
      const next = Number(event.target.value)
      if (event.target.value !== '' && next > 0) onChange(next)
    }}
    onBlur={() => { if (!draft || Number(draft) <= 0) setDraft(String(value)) }} />
}

function SceneInspector({ scene, onChange, onAddKeyframe, onAddEffect, open, onClose }) {
  if (!scene) return <aside className={`inspector panel ${open ? 'open' : ''}`}><div className="empty-list">Selecciona una escena</div></aside>
  const change = (key, value) => onChange({ [key]: value })
  return (
    <aside className={`inspector panel ${open ? 'open' : ''}`}>
      <div className="inspector-heading">
        <div><span className="eyebrow">Inspector</span><h2>{scene.sceneId}</h2></div>
        <span className="scene-duration">{scene.duration.toFixed(2)}s</span>
        <button className="inspector-close" aria-label="Cerrar inspector" onClick={onClose}><X size={16} /></button>
      </div>
      <div className="form-grid">
        <div className="visual-actions field wide"><span>Animacion</span><div>
          <button aria-label="Anadir keyframe" onClick={onAddKeyframe}><Gem size={13} />Keyframe</button>
          <button aria-label="Anadir efecto" onClick={() => onAddEffect('blur')}><Sparkles size={13} />Efecto</button>
        </div></div>
        <Field label="Duracion">
          <DurationInput value={scene.duration} onChange={(value) => change('duration', value)} />
        </Field>
        <Field label="Velocidad">
          <input aria-label="Velocidad" type="number" min="0" max="2" step="0.05" value={scene.motionSpeed}
            onChange={(e) => change('motionSpeed', Number(e.target.value))} />
        </Field>
        <Field label="Movimiento" wide>
          <select aria-label="Movimiento" value={scene.motion} onChange={(e) => change('motion', e.target.value)}>
            {MOTIONS.map((motion) => <option key={motion}>{motion}</option>)}
          </select>
        </Field>
        <Field label="Transicion" wide>
          <select aria-label="Transicion" value={scene.transition} onChange={(e) => change('transition', e.target.value)}>
            {TRANSITIONS.map((transition) => <option key={transition}>{transition}</option>)}
          </select>
        </Field>
        <Field label="Dur. transicion">
          <input type="number" min="0" max={scene.duration} step="0.1" value={scene.transitionDuration}
            onChange={(e) => change('transitionDuration', Number(e.target.value))} />
        </Field>
        <Field label="Recorte">
          <select value={scene.crop} onChange={(e) => change('crop', e.target.value)}>
            {CROPS.map((crop) => <option key={crop}>{crop}</option>)}
          </select>
        </Field>
        <Field label="Foco X">
          <input type="number" min="0" max="1" step="0.05" value={scene.focalPoint?.[0] ?? 0.5}
            onChange={(e) => change('focalPoint', [Number(e.target.value), scene.focalPoint?.[1] ?? 0.5])} />
        </Field>
        <Field label="Foco Y">
          <input type="number" min="0" max="1" step="0.05" value={scene.focalPoint?.[1] ?? 0.5}
            onChange={(e) => change('focalPoint', [scene.focalPoint?.[0] ?? 0.5, Number(e.target.value)])} />
        </Field>
        <Field label="Archivo" wide>
          <input value={scene.file} onChange={(e) => change('file', e.target.value)} />
        </Field>
        <Field label="Flow file" wide>
          <input value={scene.flowFile} onChange={(e) => change('flowFile', e.target.value)} />
        </Field>
      </div>
      <div className="metadata">
        <h3>Metadatos</h3>
        {[['Beat', scene.beat], ['Tipo visual', scene.visualType], ['Nivel', scene.visualLevel], ['Foco', scene.focus]].map(([key, value]) => (
          <div className="meta-row" key={key}><span>{key}</span><strong>{value || '-'}</strong></div>
        ))}
      </div>
    </aside>
  )
}

function Timeline({ project, selected, currentTime, zoom, onSelect, onSeek, onDropImage }) {
  const px = zoom
  const width = Math.max(900, project.duration * px)
  const position = (value) => `${value * px}px`
  return (
    <section className="timeline-shell">
      <div className="track-labels">
        <div className="ruler-spacer" />
        <div><Film size={14} />Visual</div><div><Volume2 size={14} />Narracion</div>
        <div><Music2 size={14} />Musica</div><div><Sparkles size={14} />SFX</div>
      </div>
      <div className="timeline-scroll">
        <div className="timeline-content" style={{ width }} onClick={(e) => {
          if (e.target.closest('button')) return
          const rect = e.currentTarget.getBoundingClientRect()
          onSeek(Math.min(project.duration, Math.max(0, (e.clientX - rect.left) / px)))
        }}>
          <div className="ruler">
            {Array.from({ length: Math.ceil(project.duration / 10) + 1 }, (_, index) => (
              <span key={index} style={{ left: position(index * 10) }}>{formatTime(index * 10)}</span>
            ))}
          </div>
          <div className="track visual-track">
            {project.visualTrack.map((scene, index) => (
              <button
                key={scene.sceneId} aria-label={`Seleccionar ${scene.sceneId}`}
                className={`scene-clip ${selected === index ? 'selected' : ''}`}
                style={{ left: position(scene.start), width: Math.max(46, scene.duration * px) }}
                onClick={() => onSelect(index)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => { e.preventDefault(); onDropImage(index, e.dataTransfer.getData('application/x-editor-media')) }}
              >
                <img src={api.mediaUrl(scene.file || scene.flowFile)} alt="" />
                <span className="clip-id">{scene.sceneId}</span>
                <span className="clip-detail">{scene.duration.toFixed(1)}s · {scene.motion}</span>
                {scene.transition !== 'hard_cut' && <i className="transition-mark" title={scene.transition}><ChevronDown size={11} /></i>}
              </button>
            ))}
          </div>
          <div className="track audio-track">
            {project.narrationTrack?.file && <div className="audio-clip narration" style={{ left: 0, width: position(Math.min(project.duration, project.narrationTrack.end || project.duration)) }}><Volume2 size={13} />narration.mp3</div>}
          </div>
          <div className="track audio-track">
            {project.musicTrack.map((cue, index) => <div key={index} className="audio-clip music" style={{ left: position(cue.start || 0), width: position((cue.end || project.duration) - (cue.start || 0)) }}><Music2 size={13} />{(cue.file || 'Music').split('/').at(-1)}</div>)}
          </div>
          <div className="track audio-track">
            {project.sfxTrack.map((cue) => <div key={cue.id} className="sfx-marker" style={{ left: position(cue.start) }} title={cue.file || cue.name}><Sparkles size={12} /></div>)}
          </div>
          <div className="playhead" style={{ left: position(currentTime) }}><i /></div>
        </div>
      </div>
    </section>
  )
}

export default function App() {
  const [project, setProject] = useState(null)
  const [projects, setProjects] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [preparingAudio, setPreparingAudio] = useState(false)
  const [zoom, setZoom] = useState(18)
  const [notice, setNotice] = useState(null)
  const [renderState, setRenderState] = useState('idle')
  const [renderLogs, setRenderLogs] = useState([])
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [selectedAudio, setSelectedAudio] = useState(null)
  const [selectedVisual, setSelectedVisual] = useState(null)
  const [selectedTrack, setSelectedTrack] = useState(null)
  const [panelState, setPanelState] = useState({ library: true, inspector: true, timeline: true, libraryWidth: 220, inspectorWidth: 286, timelineHeight: 270 })
  const [monitorMaximized, setMonitorMaximized] = useState(false)
  const clipboardRef = useRef(null)
  const sessionKey = `manifest-studio-session:${project?.projectId || 'default'}`
  const [preview, setPreview] = useState({ path: null, progress: 0 })
  const [renderedPreviewUrl, setRenderedPreviewUrl] = useState(null)
  const [renderedPreviewStart, setRenderedPreviewStart] = useState(0)
  const [trackState, setTrackState] = useState({ muted: new Set(), solo: null })
  const [historySize, setHistorySize] = useState(0)
  const audioEngineRef = useRef(new AudioEngine())
  const projectRef = useRef(null)
  const trackStateRef = useRef(trackState)
  const historyRef = useRef([])
  const resizeSessionRef = useRef(null)
  const timedEditSessionRef = useRef(null)
  const visualEditSessionRef = useRef(null)
  const animationRef = useRef(null)
  const playbackRequestRef = useRef(0)
  const startedAtRef = useRef(0)
  const selectedVisualRef = useRef(selectedVisual)
  const selectedAudioRef = useRef(selectedAudio)
  const currentTimeRef = useRef(currentTime)
  const selectedIndexRef = useRef(selectedIndex)
  const zoomRef = useRef(zoom)
  const panelStateRef = useRef(panelState)

  useEffect(() => {
    api.projects().then((result) => setProjects(result.projects || [])).catch(() => {})
    api.load().then(loadProject).catch((error) => setNotice({ type: 'error', text: error.message }))
  }, [])
  useEffect(() => { projectRef.current = project }, [project])
  useEffect(() => { selectedVisualRef.current = selectedVisual }, [selectedVisual])
  useEffect(() => { selectedAudioRef.current = selectedAudio }, [selectedAudio])
  useEffect(() => { currentTimeRef.current = currentTime }, [currentTime])
  useEffect(() => { selectedIndexRef.current = selectedIndex }, [selectedIndex])
  useEffect(() => { zoomRef.current = zoom }, [zoom])
  useEffect(() => { panelStateRef.current = panelState }, [panelState])
  useEffect(() => { trackStateRef.current = trackState }, [trackState])
  useEffect(() => {
    const saveSession = () => writeSession(sessionKey, { currentTime: currentTimeRef.current, selectedIndex: selectedIndexRef.current, zoom: zoomRef.current, panelState: panelStateRef.current })
    const timer = setInterval(async () => {
      if (!projectRef.current) return
      try { await api.save(projectRef.current); saveSession(); setNotice({ type: 'success', text: 'Guardado automatico' }) }
      catch (error) { setNotice({ type: 'error', text: `Autoguardado: ${error.message}` }) }
    }, 90000)
    window.addEventListener('beforeunload', saveSession)
    return () => { clearInterval(timer); window.removeEventListener('beforeunload', saveSession) }
  }, [])

  useEffect(() => {
    if (renderState !== 'rendering') return undefined
    const timer = setInterval(async () => {
      try {
        const status = await api.renderStatus()
        setRenderState(status.state)
        setRenderLogs(status.logs || [])
        if (status.state === 'success') setNotice({ type: 'success', text: 'Render MP4 completado' })
        if (status.state === 'error') setNotice({ type: 'error', text: 'El render ha fallado. Revisa el registro.' })
      } catch (error) { setNotice({ type: 'error', text: error.message }) }
    }, 1500)
    return () => clearInterval(timer)
  }, [renderState])

  useEffect(() => () => { cancelAnimationFrame(animationRef.current); audioEngineRef.current.destroy() }, [])
  useEffect(() => {
    const handleUndo = (event) => {
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        undo()
        return
      }
      if (event.key === 'Delete' && !event.target.closest('input,textarea,select,[contenteditable="true"]')) {
        const active = selectedVisualRef.current || (selectedAudioRef.current ? { kind: 'audio', type: selectedAudioRef.current.type, id: selectedAudioRef.current.id } : null)
        if (active) { event.preventDefault(); commitProject((value) => deleteSelection(value, active)); setSelectedVisual(null); setSelectedAudio(null); setSelectedTrack(null) }
        return
      }
      const modifier = event.ctrlKey || event.metaKey
      if (!modifier) return
      const selection = selectedVisualRef.current || (selectedAudioRef.current ? { type: selectedAudioRef.current.type, id: selectedAudioRef.current.id } : { kind: 'scene', index: selectedIndexRef.current })
      if (event.key.toLowerCase() === 'd' && selection) { event.preventDefault(); commitProject((value) => duplicateSelected(value, selection)) }
      if (event.key.toLowerCase() === 'c' && selection) { event.preventDefault(); clipboardRef.current = selection }
      if (event.key.toLowerCase() === 'v' && clipboardRef.current) { event.preventDefault(); commitProject((value) => duplicateSelected(value, clipboardRef.current)) }
      if (event.key.toLowerCase() === 'x' && selection) { event.preventDefault(); clipboardRef.current = selection; commitProject((value) => removeSelected(value, selection)) }
    }
    window.addEventListener('keydown', handleUndo)
    return () => window.removeEventListener('keydown', handleUndo)
  }, [])

  function loadProject(nextProject) {
    nextProject = normalizeEditorIds(nextProject)
    const saved = readSession(`manifest-studio-session:${nextProject.projectId || 'default'}`)
    const sceneCount = nextProject.visualTrack.length
    const nextIndex = Number.isInteger(saved?.selectedIndex) && saved.selectedIndex >= 0 && saved.selectedIndex < sceneCount
      ? saved.selectedIndex
      : 0
    const nextTime = Number.isFinite(saved?.currentTime)
      ? Math.min(nextProject.duration, Math.max(0, saved.currentTime))
      : 0
    setPlaying(false)
    cancelAnimationFrame(animationRef.current)
    audioEngineRef.current.pauseTimeline()
    historyRef.current = []
    setHistorySize(0)
    projectRef.current = nextProject
    setSelectedIndex(nextIndex)
    setCurrentTime(nextTime)
    setSelectedAudio(null)
    setSelectedVisual(null)
    setSelectedTrack(null)
    if (saved?.panelState) setPanelState((value) => ({ ...value, ...saved.panelState }))
    if (saved?.zoom) setZoom(saved.zoom)
    setProject(nextProject)
  }

  function commitProject(updater) {
    const current = projectRef.current
    const next = typeof updater === 'function' ? updater(current) : updater
    if (!current || !next || next === current) return
    historyRef.current = [...historyRef.current.slice(-49), current]
    setHistorySize(historyRef.current.length)
    projectRef.current = next
    setProject(next)
  }

  function undo() {
    const previous = historyRef.current.at(-1)
    if (!previous) return
    historyRef.current = historyRef.current.slice(0, -1)
    setHistorySize(historyRef.current.length)
    projectRef.current = previous
    setProject(previous)
  }

  function resizeEdit(kind, id, edge, time, phase) {
    if (phase === 'start') resizeSessionRef.current = { base: projectRef.current }
    const base = resizeSessionRef.current?.base || projectRef.current
    const result = kind === 'scene'
      ? { project: resizeSceneBoundary(base, id, time), error: null }
      : resizeAudioClip(base, kind, id, edge, time)
    if (result.error) {
      if (phase === 'end') resizeSessionRef.current = null
      setNotice({ type: 'error', text: result.error })
      return
    }
    projectRef.current = result.project
    setProject(result.project)
    if (phase === 'end') {
      if (JSON.stringify(base) !== JSON.stringify(result.project)) {
        historyRef.current = [...historyRef.current.slice(-49), base]
        setHistorySize(historyRef.current.length)
      }
      resizeSessionRef.current = null
    }
  }

  function editTimed(selection, mode, time, phase) {
    if (phase === 'start') timedEditSessionRef.current = { base: projectRef.current }
    const base = timedEditSessionRef.current?.base || projectRef.current
    if (selection.kind === 'effect') {
      const scene = base.visualTrack[selection.sceneIndex]
      const effect = scene?.effects?.find((item) => item.id === selection.id)
      if (!effect) return
      const duration = effect.end - effect.start
      editVisualDrag(selection, mode === 'move' ? { start: time, end: time + duration } : { [mode]: time }, phase)
      return
    }
    const result = mode === 'move'
      ? moveTimedItem(base, selection, time)
      : resizeTimedItem(base, selection, mode, time)
    if (result.error) { if (phase === 'end') timedEditSessionRef.current = null; setNotice({ type: 'error', text: result.error }); return }
    projectRef.current = result.project; setProject(result.project)
    if (phase === 'end') {
      if (JSON.stringify(base) !== JSON.stringify(result.project)) {
        historyRef.current = [...historyRef.current.slice(-49), base]
        setHistorySize(historyRef.current.length)
      }
      timedEditSessionRef.current = null
    }
  }

  const currentScene = useMemo(() => project ? findSceneAtTime(project.visualTrack, currentTime) : null, [project, currentTime])
  useEffect(() => {
    if (!project || !currentScene) return
    const index = project.visualTrack.findIndex((scene) => scene.sceneId === currentScene.sceneId)
    if (index >= 0) setSelectedIndex(index)
  }, [currentScene?.sceneId])

  function tick() {
    const activeProject = projectRef.current
    const elapsed = (performance.now() - startedAtRef.current) / 1000
    if (elapsed >= activeProject.duration) { setCurrentTime(activeProject.duration); setPlaying(false); audioEngineRef.current.pauseTimeline(); return }
    setCurrentTime(elapsed)
    audioEngineRef.current.sync(activeProject, elapsed, (path) => api.mediaUrl(path, activeProject.projectId), trackStateRef.current).catch(() => {})
    animationRef.current = requestAnimationFrame(tick)
  }

  function togglePlayback() {
    if (playing || preparingAudio) { playbackRequestRef.current += 1; setPreparingAudio(false); setPlaying(false); cancelAnimationFrame(animationRef.current); audioEngineRef.current.pauseTimeline(); return }
    const start = currentTime >= project.duration ? 0 : currentTime
    setPreview({ path: null, progress: 0 })
    setCurrentTime(start)
    startedAtRef.current = performance.now() - start * 1000
    audioEngineRef.current.play(projectRef.current, start, (path) => api.mediaUrl(path, projectRef.current.projectId), trackStateRef.current).then(() => {
      setPlaying(true)
      animationRef.current = requestAnimationFrame(tick)
    }).catch((error) => setNotice({ type: 'error', text: `No se pudo reproducir: ${error.message}` }))
  }

  function seek(time) {
    setCurrentTime(time)
    startedAtRef.current = performance.now() - time * 1000
    if (false) {
      const request = ++playbackRequestRef.current
      setPreparingAudio(true)
      setPlaying(false)
      cancelAnimationFrame(animationRef.current)
      setRenderedPreviewUrl(null)
      setNotice({ type: 'info', text: 'Preparando preview para la nueva posición...' })
      api.renderPreview(projectRef.current, time).then(({ url }) => {
        if (request !== playbackRequestRef.current) return
        setRenderedPreviewStart(time)
        setRenderedPreviewUrl(url)
        setPreparingAudio(false)
        setPlaying(true)
        startedAtRef.current = performance.now() - time * 1000
        animationRef.current = requestAnimationFrame(tick)
      }).catch((error) => { if (request === playbackRequestRef.current) { setPreparingAudio(false); setNotice({ type: 'error', text: error.message }) } })
      return
    }
    if (playing) audioEngineRef.current.seekMixed(time)
  }

  function editScene(changes) {
    commitProject((value) => updateScene(value, selectedIndex, changes))
  }

  function selectVisual(selection) {
    setSelectedAudio(null)
    setSelectedVisual(selection)
    setSelectedTrack(null)
    setInspectorOpen(true)
  }

  function createKeyframe() {
    const scene = projectRef.current.visualTrack[selectedIndex]
    const previousIds = new Set((scene.keyframes || []).map((item) => item.id))
    const next = addKeyframe(projectRef.current, selectedIndex, currentTime - scene.start)
    const keyframe = next.visualTrack[selectedIndex].keyframes.find((item) => !previousIds.has(item.id))
    commitProject(next)
    selectVisual({ kind: 'keyframe', sceneIndex: selectedIndex, id: keyframe.id })
  }

  function createEffect(type) {
    const scene = projectRef.current.visualTrack[selectedIndex]
    const next = addEffect(projectRef.current, selectedIndex, type, currentTime - scene.start)
    const effect = next.visualTrack[selectedIndex].effects.at(-1)
    commitProject(next)
    selectVisual({ kind: 'effect', sceneIndex: selectedIndex, id: effect.id })
  }

  async function importSubtitles(path) {
    try {
      const payload = await api.subtitles(path)
      commitProject((value) => loadSubtitles(value, payload.path || path, payload.cues || []))
      setNotice({ type: 'success', text: `${(payload.cues || []).length} subtitulos cargados` })
    } catch (error) { setNotice({ type: 'error', text: error.message }) }
  }

  function editVisualDrag(selection, changes, phase) {
    if (phase === 'start') visualEditSessionRef.current = { base: projectRef.current }
    const base = visualEditSessionRef.current?.base || projectRef.current
    let normalized = changes
    if (selection.kind === 'effect' && ('start' in changes || 'end' in changes)) {
      const sceneStart = base.visualTrack[selection.sceneIndex].start
      normalized = { ...changes, start: changes.start - sceneStart, end: changes.end - sceneStart }
    }
    const next = updateVisualItem(base, selection, normalized)
    projectRef.current = next
    setProject(next)
    if (phase === 'end') {
      if (JSON.stringify(base) !== JSON.stringify(next)) {
        historyRef.current = [...historyRef.current.slice(-49), base]
        setHistorySize(historyRef.current.length)
      }
      visualEditSessionRef.current = null
    }
  }

  function createTextTrack() {
    commitProject((value) => addTextTrack(value))
  }

  function openTrackSettings(trackId) {
    setSelectedAudio(null); setSelectedVisual(null); setSelectedTrack(trackId); setInspectorOpen(true)
  }

  function changeTrackSettings(changes) {
    commitProject((value) => updateTrackSettings(value, selectedTrack, changes))
  }

  function resizePanel(type, event) {
    event.preventDefault()
    const start = { x: event.clientX, y: event.clientY, value: panelState[type] }
    const move = (nextEvent) => setPanelState((value) => ({ ...value, [type]: Math.max(type === 'timelineHeight' ? 170 : 150, Math.min(type === 'timelineHeight' ? 520 : 420, start.value + (type === 'timelineHeight' ? start.y - nextEvent.clientY : type === 'libraryWidth' ? nextEvent.clientX - start.x : start.x - nextEvent.clientX))) }))
    const end = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', end) }
    document.addEventListener('pointermove', move); document.addEventListener('pointerup', end, { once: true })
  }

  function createTextOverlay(trackId) {
    const next = addTextOverlay(projectRef.current, trackId, currentTime)
    const overlay = next.textTracks.find((track) => track.id === trackId).overlays.at(-1)
    commitProject(next)
    selectVisual({ kind: 'text', trackId, id: overlay.id })
  }

  async function togglePreview(path) {
    if (playing) { setPlaying(false); cancelAnimationFrame(animationRef.current) }
    try {
      const active = await audioEngineRef.current.togglePreview(api.mediaUrl(path, project.projectId), (progress) => setPreview({ path, progress }), () => setPreview({ path: null, progress: 0 }))
      setPreview(active ? { path, progress: 0 } : { path: null, progress: 0 })
    } catch (error) { setNotice({ type: 'error', text: `No se pudo reproducir: ${error.message}` }) }
  }

  function dropAudio(type, payload, time) {
    const activeProject = projectRef.current
    if (payload.kind === 'asset') {
      const result = addAudioClip(activeProject, type, payload.asset, time)
      commitProject(result.project)
      if (result.error) setNotice({ type: 'error', text: result.error })
      return
    }
    if (payload.type === 'narration') {
      const narration = activeProject.narrationTrack
      if (payload.action === 'trim-left') {
        const start = Math.max(0, time)
        commitProject(updateNarration(activeProject, { start, sourceIn: narration.sourceIn + start - narration.start }))
      } else if (payload.action === 'trim-right') {
        commitProject(updateNarration(activeProject, { sourceOut: narration.sourceIn + Math.max(0.1, time - narration.start) }))
      } else commitProject(updateNarration(activeProject, { start: time }))
      return
    }
    const result = moveAudioClip(activeProject, payload.type, payload.id, time)
    commitProject(result.project)
    if (result.error) setNotice({ type: 'error', text: result.error })
  }

  async function save() {
    try { await api.save(project); writeSession(sessionKey, { currentTime, selectedIndex, zoom, panelState }); setNotice({ type: 'success', text: 'Guardado en project/manifest.editor.json' }) }
    catch (error) { setNotice({ type: 'error', text: error.message }) }
  }

  async function renderVideo() {
    try { await api.render(projectRef.current); setRenderState('rendering'); setNotice({ type: 'info', text: 'Render en curso' }) }
    catch (error) { setNotice({ type: 'error', text: error.message }) }
  }

  if (!project) return <main className="loading"><LoaderCircle className="spin" /><span>Cargando manifest...</span>{notice && <small>{notice.text}</small>}</main>
  const selectedScene = project.visualTrack[selectedIndex] || project.visualTrack[0]
  const trackKey = { music: 'musicTrack', ambience: 'ambienceTrack', sfx: 'sfxTrack' }
  const selectedClip = selectedAudio?.type === 'narration' ? project.narrationTrack : selectedAudio ? project[trackKey[selectedAudio.type]]?.find((clip) => clip.id === selectedAudio.id) : null
  const selectedVisualItem = selectedVisual?.kind === 'keyframe' ? project.visualTrack[selectedVisual.sceneIndex]?.keyframes?.find((item) => item.id === selectedVisual.id)
    : selectedVisual?.kind === 'effect' ? project.visualTrack[selectedVisual.sceneIndex]?.effects?.find((item) => item.id === selectedVisual.id)
      : selectedVisual?.kind === 'subtitle' ? project.subtitleTrack?.find((item) => item.id === selectedVisual.id)
        : selectedVisual?.kind === 'text' ? project.textTracks?.find((track) => track.id === selectedVisual.trackId)?.overlays.find((item) => item.id === selectedVisual.id)
          : null
  const fontCss = (project.fontLibrary || []).map((font) => `@font-face{font-family:'${font.family.replaceAll("'", '')}';src:url('${api.fontUrl(font.path)}')}`).join('')
  const trackLabels = { visual: 'Visual', effects: 'Efectos', subtitles: 'Subtitulos', narration: 'Narracion', music: 'Musica', ambience: 'Ambiente', sfx: 'SFX' }
  const selectedTrackLabel = selectedTrack?.startsWith('text:') ? project.textTracks.find((track) => `text:${track.id}` === selectedTrack)?.name : trackLabels[selectedTrack]
  function editAudio(changes) {
    if (selectedAudio.type === 'narration') commitProject((value) => updateNarration(value, changes))
    else if ('start' in changes) {
      const result = moveAudioClip(projectRef.current, selectedAudio.type, selectedAudio.id, changes.start)
      commitProject(result.project); if (result.error) setNotice({ type: 'error', text: result.error })
    } else commitProject((value) => updateAudioClip(value, selectedAudio.type, selectedAudio.id, changes))
  }
  return (
    <main className={`app-shell ${monitorMaximized ? 'monitor-maximized' : ''}`} style={{ '--library-width': `${panelState.libraryWidth}px`, '--inspector-width': `${panelState.inspectorWidth}px`, '--timeline-height': `${panelState.timelineHeight}px` }}>
      <style>{fontCss}</style>
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><Film size={18} /></span><div><strong>Manifest Studio</strong><span>{project.title}</span></div></div>
        <label className="project-picker"><span>Proyecto</span><select value={project.projectId || 'default'} onChange={(event) => { setNotice({ type: 'info', text: 'Cargando proyecto...' }); api.load(event.target.value).then(loadProject).catch((error) => setNotice({ type: 'error', text: error.message })) }}>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="project-picker"><span>Formato</span><select aria-label="Formato" value={`${project.width || 1920}x${project.height || 1080}`} onChange={(event) => { const [width, height] = event.target.value.split('x').map(Number); const next = updateProjectFormat(projectRef.current, width, height); commitProject(next); api.save(next).catch((error) => setNotice({ type: 'error', text: error.message })) }}><option value="1920x1080">16:9 · YouTube</option><option value="1080x1920">9:16 · Shorts</option></select></label>
        <div className="project-stats"><span>{project.visualTrack.length} escenas</span><b /><span data-testid="total-duration">{formatTime(project.duration)}</span></div>
        <div className="header-actions">
          <button className="button secondary undo-button" aria-label="Deshacer" onClick={undo} disabled={!historySize} title="Deshacer (Ctrl+Z)"><Undo2 size={15} /><span>Deshacer</span></button>
          <button className="button secondary" onClick={() => api.load().then(loadProject)} title="Recargar manifest original"><RotateCcw size={15} />Recargar</button>
          <button className="button secondary panel-toggle" onClick={() => setPanelState((value) => ({ ...value, library: !value.library }))} title="Mostrar u ocultar archivos"><FolderOpen size={15} />Archivos</button>
          <button className="button secondary panel-toggle" onClick={() => setPanelState((value) => ({ ...value, timeline: !value.timeline }))} title="Mostrar u ocultar timeline"><Film size={15} />Timeline</button>
          <button className="button secondary" onClick={save}><Save size={15} />Guardar</button>
          <button className="button primary" onClick={renderVideo} disabled={renderState === 'rendering'}>
            {renderState === 'rendering' ? <LoaderCircle className="spin" size={15} /> : <Film size={15} />}Render MP4
          </button>
        </div>
      </header>
      {notice && <div className={`notice ${notice.type}`}>
        {notice.type === 'error' ? <CircleAlert size={15} /> : notice.type === 'success' ? <Check size={15} /> : <LoaderCircle className="spin" size={15} />}
        <span>{notice.text}</span><button onClick={() => setNotice(null)}>×</button>
      </div>}
      <div className="workspace" style={{ gridTemplateColumns: `${panelState.library ? 'var(--library-width)' : '0px'} minmax(340px, 1fr) ${panelState.inspector ? 'var(--inspector-width)' : '0px'}` }}>
        {panelState.library && <AudioLibrary project={project} preview={preview} onPreview={togglePreview} onLoadSubtitle={importSubtitles} onAddEffect={createEffect}
          onChooseFont={(font) => { if (selectedVisualItem && (selectedVisual.kind === 'text' || selectedVisual.kind === 'subtitle')) commitProject((value) => updateVisualItem(value, selectedVisual, { font })) }} />}
        {panelState.library && <i className="panel-resizer vertical library-resizer" onPointerDown={(event) => resizePanel('libraryWidth', event)} />}
        <section className="viewer-column">
          <div className="viewer-toolbar"><span>Monitor</span><div className="viewer-toolbar-actions">
            <button className="inspector-toggle" aria-label="Abrir inspector" onClick={() => setInspectorOpen(true)}><SlidersHorizontal size={15} /></button>
            <button title={monitorMaximized ? 'Restaurar monitor' : 'Hacer grande el monitor'} onClick={() => setMonitorMaximized((value) => !value)}>{monitorMaximized ? <Minimize2 size={15} /> : <Maximize2 size={15} />}</button>
          </div></div>
          <div className="viewer"><ScenePreview key={renderedPreviewUrl || currentScene?.sceneId} project={project} scene={currentScene} currentTime={currentTime} playing={playing} renderedPreviewUrl={renderedPreviewUrl} renderedPreviewStart={renderedPreviewStart} onRenderedTime={(time) => { if (playing) { const timelineTime = renderedPreviewStart + time; setCurrentTime(timelineTime); startedAtRef.current = performance.now() - timelineTime * 1000 } }} onRenderedEnd={() => {
            cancelAnimationFrame(animationRef.current)
            setPlaying(false)
            setRenderedPreviewUrl(null)
            const nextStart = Math.min(projectRef.current.duration, renderedPreviewStart + 12)
            setCurrentTime(nextStart)
            if (nextStart >= projectRef.current.duration) return
            const request = ++playbackRequestRef.current
            setPreparingAudio(true)
            setNotice({ type: 'info', text: 'Preparando el siguiente fragmento...' })
            api.renderPreview(projectRef.current, nextStart).then(({ url }) => {
              if (request !== playbackRequestRef.current) return
              setRenderedPreviewStart(nextStart)
              setRenderedPreviewUrl(url)
              setPreparingAudio(false)
              setPlaying(true)
              startedAtRef.current = performance.now() - nextStart * 1000
              animationRef.current = requestAnimationFrame(tick)
            }).catch((error) => { if (request === playbackRequestRef.current) { setPreparingAudio(false); setNotice({ type: 'error', text: error.message }) } })
          }} />{preparingAudio && <div className="preview-loading"><LoaderCircle className="spin" size={20} /><span>Preparando preview del punto seleccionado...</span></div>}</div>
          <div className="transport">
            <span className="timecode">{formatTime(currentTime)}</span>
            <button className="play-button" onClick={togglePlayback} title={playing || preparingAudio ? 'Pausar' : 'Reproducir'}>{preparingAudio ? <LoaderCircle className="spin" size={17} /> : playing ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}</button>
            <span className="timecode muted">{formatTime(project.duration)}</span>
          </div>
        </section>
        {panelState.inspector && <>{selectedTrack ? <TrackSettingsInspector trackId={selectedTrack} label={selectedTrackLabel} settings={project.trackSettings?.[selectedTrack] || (selectedTrack.startsWith('text:') ? project.textTracks.find((track) => `text:${track.id}` === selectedTrack)?.settings : {}) || {}} fonts={project.fontLibrary || []} open={inspectorOpen} onClose={() => setInspectorOpen(false)} onChange={changeTrackSettings} />
          : selectedVisualItem ? <VisualInspector selection={selectedVisual} item={selectedVisualItem} fonts={project.fontLibrary || []} open={inspectorOpen} onClose={() => setInspectorOpen(false)}
          onChange={(changes) => commitProject((value) => updateVisualItem(value, selectedVisual, changes))}
          onDelete={() => { commitProject((value) => removeVisualItem(value, selectedVisual)); setSelectedVisual(null) }}
          onSplit={() => commitProject((value) => splitSubtitle(value, selectedVisual.id, currentTime))}
          onMerge={() => commitProject((value) => mergeSubtitle(value, selectedVisual.id))}
          onShift={(delta) => commitProject((value) => shiftSubtitles(value, delta))} />
          : selectedClip ? <AudioInspector type={selectedAudio.type} clip={selectedClip} onChange={editAudio} onDelete={() => { commitProject((value) => removeAudioClip(value, selectedAudio.type, selectedAudio.id)); setSelectedAudio(null) }} open={inspectorOpen} onClose={() => setInspectorOpen(false)} />
            : <SceneInspector scene={selectedScene} onChange={editScene} onAddKeyframe={createKeyframe} onAddEffect={createEffect} open={inspectorOpen} onClose={() => setInspectorOpen(false)} />}</>}
        {panelState.inspector && <i className="panel-resizer vertical inspector-resizer" onPointerDown={(event) => resizePanel('inspectorWidth', event)} />}
      </div>
      <div className="timeline-header">
        <div><strong>Timeline</strong><span>{selectedScene ? `${selectedScene.sceneId} · ${selectedScene.motion}` : 'Sin escena'}</span></div>
        <div className="timeline-tools"><button aria-label="Anadir pista de texto" onClick={createTextTrack}><Plus size={13} />Pista de texto</button><label className="zoom-control"><span>Zoom</span><input type="range" min="8" max="48" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label></div>
      </div>
      {panelState.timeline && <AudioTimeline project={project} selectedScene={selectedIndex} selectedAudio={selectedAudio} selectedVisual={selectedVisual} currentTime={currentTime} zoom={zoom} trackState={trackState}
        onSelectScene={(index) => { setSelectedAudio(null); setSelectedVisual(null); setSelectedTrack(null); setSelectedIndex(index); seek(project.visualTrack[index].start) }} onSelectAudio={(type, id) => { setSelectedVisual(null); setSelectedTrack(null); setSelectedAudio({ type, id }); setInspectorOpen(true) }} onSelectVisual={selectVisual} onOpenTrackSettings={openTrackSettings} onReorderTrack={(id, direction) => commitProject((value) => reorderTrack(value, id, direction))} onSeek={seek}
        onInsertImage={(index, path) => { if (path) { commitProject((value) => insertScene(value, index, path)); setSelectedIndex(index) } }}
        onMoveScene={(fromIndex, toIndex) => { if (fromIndex !== toIndex) { commitProject((value) => moveScene(value, fromIndex, toIndex)); setSelectedIndex(toIndex) } }}
        onDropAudio={dropAudio}
        onResizeScene={(index, time, phase) => resizeEdit('scene', index, null, time, phase)}
        onResizeAudio={(type, id, edge, time, phase) => resizeEdit(type, id, edge, time, phase)}
        onMoveTimed={(selection, time, phase) => editTimed(selection, 'move', time, phase)}
        onResizeTimed={(selectionOrType, idOrId, edge, time, phase) => {
          const selection = typeof selectionOrType === 'string' ? { kind: 'audio', type: selectionOrType, id: idOrId } : selectionOrType
          editTimed(selection, edge, time, phase)
        }}
        onEditVisual={editVisualDrag}
        onAddTextTrack={createTextTrack}
        onAddTextOverlay={createTextOverlay}
        onClearTrack={(trackId, label) => { if (window.confirm(`Vaciar todos los elementos de la pista ${label}?`)) { commitProject((value) => clearTrack(value, trackId)); setSelectedAudio(null); setSelectedVisual(null) } }}
        onMute={(type) => setTrackState((value) => { const muted = new Set(value.muted); muted.has(type) ? muted.delete(type) : muted.add(type); return { ...value, muted } })}
        onSolo={(type) => setTrackState((value) => ({ ...value, solo: value.solo === type ? null : type }))} />}
      {panelState.timeline && <i className="panel-resizer horizontal timeline-resizer" onPointerDown={(event) => resizePanel('timelineHeight', event)} />}
      {renderLogs.length > 0 && <details className="render-log"><summary>Registro de render ({renderState})</summary><pre>{renderLogs.join('\n')}</pre></details>}
    </main>
  )
}
