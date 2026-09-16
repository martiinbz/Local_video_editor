async function request(path, options) {
  const response = await fetch(path, options)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Error HTTP ${response.status}`)
  }
  return response.json()
}

export const api = {
  load: (project = '') => request(`/api/project${project ? `?project=${encodeURIComponent(project)}` : ''}`),
  projects: () => request('/api/projects'),
  save: (project) => request('/api/project/save', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(project),
  }),
  render: (project) => request('/api/project/render', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(project),
  }),
  audioPreview: (project) => request('/api/project/audio-preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(project) }),
  renderPreview: (project, time = 0) => request(`/api/project/render-preview?time=${encodeURIComponent(time)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(project) }),
  renderStatus: () => request('/api/render/status'),
  waveform: (path, points = 1024) => request(`/api/audio/waveform?path=${encodeURIComponent(path)}&points=${points}`),
  subtitles: (path) => request(`/api/subtitles?path=${encodeURIComponent(path)}`),
  fonts: () => request('/api/fonts'),
  fontUrl: (path) => `/api/fonts/file?path=${encodeURIComponent(path)}`,
  mediaUrl: (path, project = 'default') => `/api/media?path=${encodeURIComponent(path)}&project=${encodeURIComponent(project || 'default')}`,
}
