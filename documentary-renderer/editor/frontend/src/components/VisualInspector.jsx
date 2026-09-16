import { Bold, Italic, Scissors, Trash2, Underline, X } from 'lucide-react'

const EFFECTS = ['blur', 'brightness', 'contrast', 'saturation', 'grayscale', 'vignette', 'flash', 'shake', 'film_grain', 'chromatic_aberration']
const ANIMATIONS = ['none', 'fade', 'slide_left', 'slide_right', 'slide_up', 'slide_down']

function Field({ label, children, wide = false }) {
  return <label className={`field ${wide ? 'wide' : ''}`}><span>{label}</span>{children}</label>
}

export function VisualInspector({ selection, item, fonts, open, onClose, onChange, onDelete, onSplit, onMerge, onShift }) {
  if (!item) return null
  const textKind = selection.kind === 'subtitle' || selection.kind === 'text'
  return <aside className={`inspector panel ${open ? 'open' : ''}`}>
    <div className="inspector-heading"><div><span className="eyebrow">{selection.kind}</span><h2>{textKind ? item.text.slice(0, 28) || 'Texto' : item.type || 'Keyframe'}</h2></div><button className="inspector-close" aria-label="Cerrar inspector" onClick={onClose}><X size={16} /></button></div>
    <div className="form-grid">
      {selection.kind === 'keyframe' && <>
        <Field label="Tiempo"><input type="number" step="0.1" value={item.time} onChange={(e) => onChange({ time: Number(e.target.value) })} /></Field>
        <Field label="Escala"><input aria-label="Escala keyframe" type="number" min="1" step="0.01" value={item.scale} onChange={(e) => onChange({ scale: Number(e.target.value) })} /></Field>
        <Field label="Posicion X"><input type="number" min="0" max="1" step="0.01" value={item.x} onChange={(e) => onChange({ x: Number(e.target.value) })} /></Field>
        <Field label="Posicion Y"><input type="number" min="0" max="1" step="0.01" value={item.y} onChange={(e) => onChange({ y: Number(e.target.value) })} /></Field>
        <Field label="Rotacion"><input type="number" step="0.1" value={item.rotation || 0} onChange={(e) => onChange({ rotation: Number(e.target.value) })} /></Field>
      </>}
      {selection.kind === 'effect' && <>
        <Field label="Efecto" wide><select value={item.type} onChange={(e) => onChange({ type: e.target.value })}>{EFFECTS.map((effect) => <option key={effect}>{effect}</option>)}</select></Field>
        <Field label="Inicio"><input type="number" step="0.1" value={item.start} onChange={(e) => onChange({ start: Number(e.target.value) })} /></Field>
        <Field label="Final"><input type="number" step="0.1" value={item.end} onChange={(e) => onChange({ end: Number(e.target.value) })} /></Field>
        <Field label="Intensidad" wide><input aria-label="Intensidad efecto" type="range" min="0" max="1" step="0.01" value={item.intensity} onChange={(e) => onChange({ intensity: Number(e.target.value) })} /></Field>
        <Field label="Activo" wide><input type="checkbox" checked={item.enabled !== false} onChange={(e) => onChange({ enabled: e.target.checked })} /></Field>
      </>}
      {textKind && <>
        <Field label="Texto" wide><textarea aria-label="Texto del elemento" value={item.text} onChange={(e) => onChange({ text: e.target.value })} /></Field>
        <Field label="Inicio"><input type="number" step="0.1" value={item.start} onChange={(e) => onChange({ start: Number(e.target.value) })} /></Field>
        <Field label="Final"><input type="number" step="0.1" value={item.end} onChange={(e) => onChange({ end: Number(e.target.value) })} /></Field>
        <Field label="Fuente" wide><select aria-label="Fuente" value={item.font || ''} onChange={(e) => onChange({ font: e.target.value })}><option value="">Sistema</option>{fonts.map((font) => <option key={font.path} value={font.path}>{font.family}</option>)}</select></Field>
        <Field label="Tamano"><input type="number" min="8" max="300" value={item.font_size || 48} onChange={(e) => onChange({ font_size: Number(e.target.value) })} /></Field>
        <Field label="Color"><input aria-label="Color del texto" type="color" value={item.color || '#ffffff'} onChange={(e) => onChange({ color: e.target.value })} /></Field>
        <Field label="Opacidad"><input type="range" min="0" max="1" step="0.05" value={item.opacity ?? 1} onChange={(e) => onChange({ opacity: Number(e.target.value) })} /></Field>
        <Field label="Alineacion"><select value={item.align || 'center'} onChange={(e) => onChange({ align: e.target.value })}><option value="left">Izquierda</option><option value="center">Centro</option><option value="right">Derecha</option></select></Field>
        <div className="style-toggles field wide"><span>Estilo</span><div><button className={item.bold ? 'active' : ''} title="Negrita" onClick={() => onChange({ bold: !item.bold })}><Bold size={14} /></button><button className={item.italic ? 'active' : ''} title="Cursiva" onClick={() => onChange({ italic: !item.italic })}><Italic size={14} /></button><button className={item.underline ? 'active' : ''} title="Subrayado" onClick={() => onChange({ underline: !item.underline })}><Underline size={14} /></button></div></div>
        <Field label="Posicion X"><input type="number" min="0" max="1" step="0.01" value={item.x ?? 0.5} onChange={(e) => onChange({ x: Number(e.target.value) })} /></Field>
        <Field label="Posicion Y"><input type="number" min="0" max="1" step="0.01" value={item.y ?? 0.85} onChange={(e) => onChange({ y: Number(e.target.value) })} /></Field>
        <Field label="Contorno"><input type="number" min="0" max="12" step="1" value={item.outline ?? 2} onChange={(e) => onChange({ outline: Number(e.target.value) })} /></Field>
        <Field label="Sombra"><input type="number" min="0" max="20" step="1" value={item.shadow ?? 0} onChange={(e) => onChange({ shadow: Number(e.target.value) })} /></Field>
        <Field label="Entrada"><select value={item.animation_in || 'none'} onChange={(e) => onChange({ animation_in: e.target.value })}>{ANIMATIONS.map((value) => <option key={value}>{value}</option>)}</select></Field>
        <Field label="Salida"><select value={item.animation_out || 'none'} onChange={(e) => onChange({ animation_out: e.target.value })}>{ANIMATIONS.map((value) => <option key={value}>{value}</option>)}</select></Field>
        <Field label="Dur. animacion" wide><input type="number" min="0.05" max="5" step="0.05" value={item.transition_duration ?? 0.3} onChange={(e) => onChange({ transition_duration: Number(e.target.value) })} /></Field>
      </>}
    </div>
    {selection.kind === 'subtitle' && <div className="subtitle-tools"><button onClick={onSplit}><Scissors size={13} />Dividir en playhead</button><button onClick={onMerge}>Unir siguiente</button><button onClick={() => onShift(-0.5)}>-0.5s todos</button><button onClick={() => onShift(0.5)}>+0.5s todos</button></div>}
    <button className="delete-audio" aria-label="Eliminar elemento visual" onClick={onDelete}><Trash2 size={14} />Eliminar</button>
  </aside>
}
