import { useState } from 'react'
import { Captions, FolderOpen, Image, Music2, Pause, Play, Sparkles, Trees, Type, Volume2 } from 'lucide-react'
import { api } from '../api'
import { formatTime } from '../editorState'

const EFFECTS = ['blur', 'brightness', 'contrast', 'saturation', 'grayscale', 'vignette', 'flash', 'shake', 'film_grain', 'chromatic_aberration']

export function AudioLibrary({ project, preview, onPreview, onLoadSubtitle, onAddEffect, onChooseFont }) {
  const [tab, setTab] = useState('images')
  const tabs = [
    ['images', Image, 'Imagenes'], ['music', Music2, 'Musica'],
    ['ambience', Trees, 'Ambiente'], ['sfx', Sparkles, 'SFX'],
    ['subtitles', Captions, 'Subtitulos'], ['fonts', Type, 'Fuentes'], ['effects', Sparkles, 'Efectos'],
  ]
  const assets = tab === 'images' ? (project.files?.images || []).map((path) => ({ path, name: path.split('/').at(-1) }))
    : tab === 'subtitles' ? project.subtitleLibrary || []
      : tab === 'fonts' ? project.fontLibrary || []
        : tab === 'effects' ? EFFECTS.map((type) => ({ type, name: type.replaceAll('_', ' ') }))
          : project.audioLibrary?.[tab] || []

  return <aside className="library panel">
    <div className="panel-title"><FolderOpen size={16} /><h2>Archivos</h2></div>
    <div className="segmented" aria-label="Tipo de archivo">
      {tabs.map(([key, Icon, label]) => <button key={key} aria-label={label} className={tab === key ? 'active' : ''} onClick={() => setTab(key)} title={label}><Icon size={14} /><span>{label}</span></button>)}
    </div>
    <div className="asset-list">
      {assets.map((asset) => tab === 'images' ? (
        <div className="asset-item" key={asset.path} draggable onDragStart={(event) => event.dataTransfer.setData('application/x-editor-media', asset.path)}>
          <div className="asset-thumb images"><img src={api.mediaUrl(asset.path, project.projectId)} alt="" /></div><span title={asset.path}>{asset.name}</span>
        </div>
      ) : tab === 'subtitles' ? (
        <button className="asset-item library-action" key={asset.path} aria-label={`Cargar ${asset.name}`} onClick={() => onLoadSubtitle(asset.path)}>
          <Captions size={17} /><span>{asset.name}</span>
        </button>
      ) : tab === 'fonts' ? (
        <button className="asset-item library-action font-asset" key={asset.path} onClick={() => onChooseFont(asset.path)}>
          <Type size={17} /><span style={{ fontFamily: asset.family }}>{asset.family || asset.name}</span>
        </button>
      ) : tab === 'effects' ? (
        <button className="asset-item library-action effect-asset" key={asset.type} onClick={() => onAddEffect(asset.type)}>
          <Sparkles size={16} /><span>{asset.name}</span>
        </button>
      ) : (
        <div className="asset-item audio-asset" key={asset.path} draggable
          onDragStart={(event) => event.dataTransfer.setData('application/x-audio-asset', JSON.stringify({ kind: 'asset', type: tab, asset }))}>
          <button className="asset-preview" aria-label={`${preview.path === asset.path ? 'Detener' : 'Reproducir'} ${asset.name}`} onClick={() => onPreview(asset.path)}>
            {preview.path === asset.path ? <Pause size={13} fill="currentColor" /> : <Play size={13} fill="currentColor" />}
          </button>
          <span title={asset.path}>{asset.name}</span><time>{formatTime(asset.duration)}</time>
          <i style={{ width: `${preview.path === asset.path ? preview.progress * 100 : 0}%` }} />
        </div>
      ))}
      {!assets.length && <div className="empty-list"><Volume2 size={16} />No hay archivos</div>}
    </div>
  </aside>
}
