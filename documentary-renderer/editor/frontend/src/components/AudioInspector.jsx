import { Trash2, X } from 'lucide-react'
import { NumberField } from './NumberField'

function Input({ label, value, onChange, min = 0, max, ariaLabel }) { return <NumberField label={label} value={value} min={min} max={max} ariaLabel={ariaLabel} onCommit={onChange} /> }

export function AudioInspector({ type, clip, open, onClose, onChange, onDelete }) {
  const name = (clip.file || clip.name || type).split('/').at(-1)
  return <aside className={`inspector panel ${open ? 'open' : ''}`}>
    <div className="inspector-heading"><div><span className="eyebrow">Audio · {type}</span><h2>{name}</h2></div><button className="inspector-close" aria-label="Cerrar inspector" onClick={onClose}><X size={16} /></button></div>
    <div className="form-grid">
      <Input label="Inicio" value={clip.start} onChange={(start) => onChange({ start })} />
      <Input label="Duracion" value={clip.duration ?? clip.end - clip.start} onChange={(duration) => onChange({ duration })} />
      <NumberField className="wide" label="Volumen (%)" ariaLabel="Volumen del clip" value={Math.round((clip.volume ?? 1) * 100)} min={0} max={100} onCommit={(volume) => onChange({ volume: volume / 100 })} />
      {type === 'narration' && <><Input label="Entrada fuente" value={clip.sourceIn} onChange={(sourceIn) => onChange({ sourceIn })} /><Input label="Salida fuente" value={clip.sourceOut} onChange={(sourceOut) => onChange({ sourceOut })} /></>}
      <label className="field wide"><span>Archivo</span><input value={clip.file || ''} readOnly /></label>
    </div>
    {type !== 'narration' && <button className="delete-audio" aria-label="Eliminar audio" onClick={onDelete}><Trash2 size={14} />Eliminar clip</button>}
  </aside>
}
