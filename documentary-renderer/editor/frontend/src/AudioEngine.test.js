import { describe, expect, it, vi } from 'vitest'
import { AudioEngine } from './AudioEngine'

class FakeAudio {
  constructor(url) {
    this.src = url
    this.currentTime = 0
    this.volume = 1
    this.paused = true
    this.ontimeupdate = null
    this.onended = null
    this.play = vi.fn(async () => { this.paused = false })
    this.pause = vi.fn(() => { this.paused = true })
  }
}

describe('AudioEngine', () => {
  it('toggles one exclusive library preview and switches files', async () => {
    const created = []
    const engine = new AudioEngine((url) => { const audio = new FakeAudio(url); created.push(audio); return audio })

    await engine.togglePreview('/one.mp3')
    await engine.togglePreview('/one.mp3')
    await engine.togglePreview('/two.mp3')

    expect(created).toHaveLength(2)
    expect(created[0].play).toHaveBeenCalledTimes(1)
    expect(created[0].pause).toHaveBeenCalled()
    expect(created[1].play).toHaveBeenCalledTimes(1)
  })

  it('detaches progress callbacks before stopping a preview', async () => {
    const audio = new FakeAudio('/one.mp3')
    audio.pause = vi.fn(() => { audio.paused = true; audio.ontimeupdate?.() })
    const progress = vi.fn()
    const engine = new AudioEngine(() => audio)

    await engine.togglePreview('/one.mp3', progress)
    await engine.togglePreview('/one.mp3', progress)

    expect(progress).not.toHaveBeenCalled()
  })

  it('stops preview and synchronizes active narration when timeline starts', async () => {
    const created = []
    const engine = new AudioEngine((url) => { const audio = new FakeAudio(url); created.push(audio); return audio })
    await engine.togglePreview('/preview.mp3')
    const project = {
      narrationTrack: { id: 'narration', file: 'voice.mp3', start: 2, sourceIn: 3, sourceOut: 9, volume: 0.8 },
      musicTrack: [], ambienceTrack: [], sfxTrack: [],
    }

    await engine.play(project, 4, (path) => `/media/${path}`)

    expect(created[0].pause).toHaveBeenCalled()
    expect(created[1].src).toBe('/media/voice.mp3')
    expect(created[1].currentTime).toBe(5)
    expect(created[1].volume).toBe(0.8)
    expect(created[1].play).toHaveBeenCalled()
  })

  it('honors mute and solo track state', async () => {
    const created = []
    const engine = new AudioEngine((url) => { const audio = new FakeAudio(url); created.push(audio); return audio })
    const project = {
      narrationTrack: null,
      musicTrack: [{ id: 'm1', file: 'music.mp3', start: 0, end: 10, volume: 0.2 }],
      ambienceTrack: [{ id: 'a1', file: 'room.mp3', start: 0, end: 10, volume: 0.3 }],
      sfxTrack: [],
    }

    await engine.play(project, 2, (path) => path, { solo: 'music', muted: new Set() })

    expect(created).toHaveLength(1)
    expect(created[0].src).toBe('music.mp3')
  })

  it('updates the volume of an active clip', async () => {
    const created = []
    const engine = new AudioEngine((url) => { const audio = new FakeAudio(url); created.push(audio); return audio })
    const project = { narrationTrack: null, musicTrack: [{ id: 'm1', file: 'music.mp3', start: 0, end: 10, volume: 0.2 }], ambienceTrack: [], sfxTrack: [] }
    await engine.play(project, 1, (path) => path)

    await engine.sync({ ...project, musicTrack: [{ ...project.musicTrack[0], volume: 0.7 }] }, 1.1, (path) => path)

    expect(created[0].volume).toBe(0.7)
  })

  it('loops music source time when an editorial clip is longer than its file', async () => {
    const created = []
    const engine = new AudioEngine((url) => { const audio = new FakeAudio(url); created.push(audio); return audio })
    const project = { narrationTrack: null, musicTrack: [{ id: 'm1', file: 'music.mp3', start: 0, end: 13, duration: 13, sourceDuration: 6, loop: true, volume: 0.2 }], ambienceTrack: [], sfxTrack: [] }

    await engine.play(project, 8, (path) => path)

    expect(created[0].currentTime).toBe(2)
  })
})
