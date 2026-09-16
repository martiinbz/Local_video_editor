import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

const cache = new Map()

export function Waveform({ path }) {
  const canvasRef = useRef(null)
  const [peaks, setPeaks] = useState(cache.get(path)?.peaks || [])

  useEffect(() => {
    let active = true
    if (!path || cache.has(path)) return undefined
    api.waveform(path).then((data) => {
      cache.set(path, data)
      if (active) setPeaks(data.peaks || [])
    }).catch(() => {})
    return () => { active = false }
  }, [path])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !peaks.length) return
    const rect = canvas.getBoundingClientRect()
    const ratio = window.devicePixelRatio || 1
    canvas.width = Math.max(1, Math.round(rect.width * ratio))
    canvas.height = Math.max(1, Math.round(rect.height * ratio))
    const context = canvas.getContext('2d')
    if (!context) return
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.strokeStyle = 'currentColor'
    context.globalAlpha = 0.72
    context.lineWidth = Math.max(1, ratio)
    context.beginPath()
    const step = peaks.length / canvas.width
    for (let x = 0; x < canvas.width; x += Math.max(1, ratio)) {
      const [low, high] = peaks[Math.min(peaks.length - 1, Math.floor(x * step))]
      context.moveTo(x, (1 - high) * canvas.height / 2)
      context.lineTo(x, (1 - low) * canvas.height / 2)
    }
    context.stroke()
  }, [peaks])

  return <canvas className="waveform" ref={canvasRef} aria-hidden="true" />
}
