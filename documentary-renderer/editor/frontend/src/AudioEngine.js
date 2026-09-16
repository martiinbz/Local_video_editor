export class AudioEngine {
  constructor(createAudio = (url) => new Audio(url)) {
    this.createAudio = createAudio
    this.previewAudio = null
    this.previewUrl = null
    this.timelineAudios = new Map()
    this.timelinePlaying = false
    this.mixedAudio = null
  }

  async togglePreview(url, onProgress = () => {}, onStop = () => {}) {
    if (this.previewAudio && this.previewUrl === url) {
      this.stopPreview()
      onStop()
      return false
    }
    this.pauseTimeline()
    this.stopPreview()
    const audio = this.createAudio(url)
    this.previewAudio = audio
    this.previewUrl = url
    audio.ontimeupdate = () => onProgress(audio.duration ? audio.currentTime / audio.duration : 0)
    audio.onended = () => { this.stopPreview(); onStop() }
    await audio.play()
    return true
  }

  stopPreview() {
    if (this.previewAudio) {
      const audio = this.previewAudio
      audio.ontimeupdate = null
      audio.onended = null
      audio.pause()
      audio.currentTime = 0
    }
    this.previewAudio = null
    this.previewUrl = null
  }

  async play(project, time, mediaUrl, trackState = { solo: null, muted: new Set() }) {
    this.stopPreview()
    this.pauseTimeline()
    this.timelinePlaying = true
    await this.sync(project, time, mediaUrl, trackState)
  }

  async playMixed(url, time) {
    this.pauseTimeline()
    const audio = this.createAudio(url)
    audio.currentTime = time
    this.mixedAudio = audio
    this.timelinePlaying = true
    await audio.play()
  }

  seekMixed(time) { if (this.mixedAudio) this.mixedAudio.currentTime = time }

  async sync(project, time, mediaUrl, trackState = { solo: null, muted: new Set() }) {
    if (this.mixedAudio) return
    if (!this.timelinePlaying) return
    const active = this._activeClips(project, time, trackState)
    const activeIds = new Set(active.map((item) => item.clip.id))
    for (const [id, audio] of this.timelineAudios) {
      if (!activeIds.has(id)) { audio.pause(); this.timelineAudios.delete(id) }
    }
    for (const item of active) {
      const desiredTime = item.sourceTime
      let audio = this.timelineAudios.get(item.clip.id)
      if (!audio) {
        audio = this.createAudio(mediaUrl(item.clip.file))
        audio.volume = Math.min(1, Math.max(0, Number(item.clip.volume) || 0))
        audio.currentTime = desiredTime
        this.timelineAudios.set(item.clip.id, audio)
        await audio.play()
      } else {
        audio.volume = Math.min(1, Math.max(0, Number(item.clip.volume) || 0))
        if (Math.abs(audio.currentTime - desiredTime) > 0.35) audio.currentTime = desiredTime
      }
    }
  }

  pauseTimeline() {
    this.timelinePlaying = false
    for (const audio of this.timelineAudios.values()) audio.pause()
    this.timelineAudios.clear()
    if (this.mixedAudio) { this.mixedAudio.pause(); this.mixedAudio = null }
  }

  destroy() {
    this.stopPreview()
    this.pauseTimeline()
  }

  _activeClips(project, time, trackState) {
    const items = []
    const allowed = (type) => !trackState.muted?.has(type) && (!trackState.solo || trackState.solo === type)
    const narration = project.narrationTrack
    if (narration && allowed('narration') && time >= narration.start && time < narration.start + (narration.sourceOut - narration.sourceIn)) {
      items.push({ clip: narration, sourceTime: narration.sourceIn + time - narration.start })
    }
    for (const [type, key] of [['music', 'musicTrack'], ['ambience', 'ambienceTrack'], ['sfx', 'sfxTrack']]) {
      if (!allowed(type)) continue
      for (const clip of project[key] || []) {
        const end = clip.end ?? clip.start + (clip.duration || clip.sourceDuration || 0)
        if (time >= clip.start && time < end) {
          const elapsed = time - clip.start
          const sourceDuration = Number(clip.sourceDuration) || 0
          const sourceTime = clip.loop && sourceDuration > 0 ? elapsed % sourceDuration : elapsed
          items.push({ clip, sourceTime })
        }
      }
    }
    return items
  }
}
