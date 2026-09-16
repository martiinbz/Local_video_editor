import { Settings, X } from 'lucide-react'
import { NumberField } from './NumberField'

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>
}

export function TrackSettingsInspector({ trackId, label, settings, fonts, open, onClose, onChange }) {
  const audio = ['narration', 'music', 'ambience', 'sfx'].includes(trackId)
  const text = trackId === 'subtitles' || trackId.startsWith('text:')
  return <aside className={`inspector panel ${open ? 'open' : ''}`}>
    <div className="inspector-heading"><div><span className="eyebrow">Ajustes de pista</span><h2><Settings size={14} />{label}</h2></div><button className="inspector-close" aria-label="Cerrar inspector" onClick={onClose}><X size={16} /></button></div>
    <div className="form-grid">
      {audio && <><NumberField label="Volumen (%)" ariaLabel="Volumen de pista" value={Math.round((settings.volume ?? 1) * 100)} min={0} max={100} onCommit={(volume) => onChange({ volume: volume / 100 })} /><Field label="Ajuste"><input aria-label="Deslizador de volumen de pista" type="range" min="0" max="100" step="1" value={Math.round((settings.volume ?? 1) * 100)} onChange={(e) => onChange({ volume: Number(e.target.value) / 100 })} /></Field></>}
      {text && <>
        <Field label="Tamano"><input aria-label="Tamano de pista" type="number" min="1" max="300" step="1" value={settings.font_size ?? (trackId === 'subtitles' ? 4 : 56)} onChange={(e) => onChange({ font_size: Number(e.target.value) })} /></Field>
        <Field label="Color"><input aria-label="Color de pista" type="color" value={settings.color || '#ffffff'} onChange={(e) => onChange({ color: e.target.value })} /></Field>
        <Field label="Fuente" wide><select aria-label="Fuente de pista" value={settings.font || ''} onChange={(e) => onChange({ font: e.target.value })}><option value="">Sistema</option>{fonts.map((font) => <option key={font.path} value={font.path}>{font.family}</option>)}</select></Field>
        <Field label="Opacidad"><input type="range" min="0" max="1" step="0.05" value={settings.opacity ?? 1} onChange={(e) => onChange({ opacity: Number(e.target.value) })} /></Field>
      </>}
    </div>
    <p className="settings-hint">Estos valores se aplican a todos los elementos actuales de la pista y a los nuevos.</p>
  </aside>
}
