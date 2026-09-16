import { useEffect, useState } from 'react'

export function NumberField({ label, value, onCommit, min, max, step = 'any', ariaLabel = label, className = '' }) {
  const [draft, setDraft] = useState(String(value ?? ''))
  useEffect(() => setDraft(String(value ?? '')), [value])
  const commit = () => {
    const number = Number(draft)
    if (!Number.isFinite(number) || (min != null && number < min) || (max != null && number > max)) { setDraft(String(value ?? '')); return }
    onCommit(number)
  }
  return <label className={`field ${className}`}><span>{label}</span><input aria-label={ariaLabel} type="text" inputMode="decimal" value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={commit} onKeyDown={(event) => { if (event.key === 'Enter') { event.currentTarget.blur() } }} step={step} /></label>
}
