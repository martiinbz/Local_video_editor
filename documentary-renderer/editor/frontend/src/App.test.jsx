import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App, { previewScaleForWidth } from './App'

const fixture = {
  title: 'Hushpuppi',
  duration: 5,
  narrationTrack: { file: 'project/narration.mp3', start: 0, end: 5 },
  musicTrack: [{ id: 'music-1', type: 'music', file: 'assets/music/score.mp3', name: 'score.mp3', start: 0, end: 5, duration: 5, sourceDuration: 5, volume: 0.12 }],
  ambienceTrack: [],
  sfxTrack: [],
  files: { images: ['project/images/one.jpg'], music: ['assets/music/score.mp3'], ambience: [], sfx: [] },
  audioLibrary: { music: [{ path: 'assets/music/score.mp3', name: 'score.mp3', duration: 5, type: 'music' }], ambience: [], sfx: [] },
  subtitleLibrary: [{ path: 'project/subtitles/es.srt', name: 'es.srt' }],
  fontLibrary: [{ path: 'assets/fonts/Inter.ttf', name: 'Inter.ttf', family: 'Inter' }],
  subtitleTrack: [],
  textTracks: [],
  visualTrack: [
    {
      sceneId: 'SCENE_1', start: 0, end: 2, duration: 2, file: 'project/images/one.jpg',
      flowFile: 'project/images/one.jpg', motion: 'static', motionSpeed: 0.5, crop: 'wide',
      focalPoint: [0.5, 0.5], transition: 'hard_cut', transitionDuration: 0.5,
      keyframes: [], effects: [],
      beat: 'Opening', visualType: 'OBJECT', visualLevel: 'HERO', focus: 'OBJ_1',
    },
    {
      sceneId: 'SCENE_2', start: 2, end: 5, duration: 3, file: 'project/images/two.jpg',
      flowFile: 'project/images/two.jpg', motion: 'zoom_in', motionSpeed: 0.5, crop: 'wide',
      focalPoint: [0.5, 0.5], transition: 'fade', transitionDuration: 0.5,
      keyframes: [], effects: [],
    },
  ],
  sourceManifest: { scenes: [{}, {}] },
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (input) => ({
      ok: true,
      json: async () => String(input).includes('/api/audio/waveform')
        ? { duration: 5, points: 256, peaks: Array.from({ length: 256 }, () => [-0.4, 0.4]) }
        : String(input).includes('/api/subtitles?')
          ? { path: 'project/subtitles/es.srt', cues: [{ id: 'subtitle-1', start: 0.5, end: 2, text: 'Hola mundo' }] }
          : structuredClone(fixture),
    })))
  })

  it('scales preview typography from the 1920px render canvas', () => {
    expect(previewScaleForWidth(1920)).toBe(1)
    expect(previewScaleForWidth(960)).toBe(0.5)
    expect(previewScaleForWidth(0)).toBe(1)
  })

  it('loads the project timeline and selection updates the inspector', async () => {
    render(<App />)
    expect(await screen.findByRole('button', { name: /seleccionar SCENE_1/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /seleccionar SCENE_2/i }))
    expect(screen.getByRole('heading', { name: 'SCENE_2' })).toBeInTheDocument()
  })

  it('editing motion and duration updates inspector and total duration', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.selectOptions(screen.getByLabelText('Movimiento'), 'pan_left')
    await userEvent.clear(screen.getByLabelText('Duracion'))
    await userEvent.type(screen.getByLabelText('Duracion'), '4')

    expect(screen.getByLabelText('Movimiento')).toHaveValue('pan_left')
    expect(screen.getByTestId('total-duration')).toHaveTextContent('7.0')
  })

  it('clears an image error when selecting another scene', async () => {
    render(<App />)
    const firstImage = await screen.findByAltText('SCENE_1')
    fireEvent.error(firstImage)
    expect(screen.getByText('Archivo no disponible')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /seleccionar SCENE_2/i }))

    expect(screen.getByAltText('SCENE_2')).toBeInTheDocument()
  })

  it('resets selection when switching to a project with fewer scenes', async () => {
    const shortProject = {
      ...structuredClone(fixture),
      title: 'EP3', projectId: 'ep3', duration: 3,
      visualTrack: [{ ...structuredClone(fixture.visualTrack[0]), sceneId: 'SCENE_001', id: 'SCENE_001', end: 3, duration: 3 }],
    }
    globalThis.fetch.mockImplementation(async (input) => ({
      ok: true,
      json: async () => String(input).includes('/api/projects')
        ? { projects: [{ id: 'default', name: 'Proyecto actual' }, { id: 'ep3', name: 'ep3' }] }
        : String(input).includes('project=ep3') ? shortProject : structuredClone(fixture),
    }))

    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: /seleccionar SCENE_2/i }))
    await userEvent.selectOptions(screen.getByLabelText('Proyecto'), 'ep3')

    expect(await screen.findByRole('button', { name: /seleccionar SCENE_001/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SCENE_001' })).toBeInTheDocument()
  })

  it('uses a project-specific media URL after changing project', async () => {
    const otherProject = {
      ...structuredClone(fixture), projectId: 'ep3',
      visualTrack: [{ ...structuredClone(fixture.visualTrack[0]), file: 'project/images/one.jpg', flowFile: 'project/images/one.jpg' }],
    }
    globalThis.fetch.mockImplementation(async (input) => ({
      ok: true,
      json: async () => String(input).includes('/api/projects')
        ? { projects: [{ id: 'default', name: 'Proyecto actual' }, { id: 'ep3', name: 'ep3' }] }
        : String(input).includes('project=ep3') ? otherProject : structuredClone(fixture),
    }))

    render(<App />)
    const initial = await screen.findByAltText('SCENE_1')
    expect(initial.getAttribute('src')).toContain('project=default')
    await userEvent.selectOptions(screen.getByLabelText('Proyecto'), 'ep3')

    expect((await screen.findByAltText('SCENE_1')).getAttribute('src')).toContain('project=ep3')
  })

  it('opens and closes the inspector from the compact toolbar', async () => {
    const { container } = render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })

    await userEvent.click(screen.getByRole('button', { name: 'Abrir inspector' }))
    expect(container.querySelector('.inspector.open')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar inspector' }))
    expect(container.querySelector('.inspector.open')).not.toBeInTheDocument()
  })

  it('previews an audio from the library and toggles it off', async () => {
    class FakeAudio {
      constructor() { this.paused = true; this.currentTime = 0; this.duration = 5 }
      play = vi.fn(async () => { this.paused = false })
      pause = vi.fn(() => { this.paused = true })
    }
    vi.stubGlobal('Audio', FakeAudio)
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: 'Musica' }))

    await userEvent.click(screen.getByRole('button', { name: 'Reproducir score.mp3' }))
    expect(screen.getByRole('button', { name: 'Detener score.mp3' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Detener score.mp3' }))
    expect(screen.getByRole('button', { name: 'Reproducir score.mp3' })).toBeInTheDocument()
  })

  it('starts the editable preview immediately without rendering an MP4 fragment', async () => {
    class FakeAudio {
      constructor() { this.paused = true; this.currentTime = 0; this.duration = 30; this.volume = 1 }
      play = vi.fn(async () => { this.paused = false })
      pause = vi.fn(() => { this.paused = true })
    }
    vi.stubGlobal('Audio', FakeAudio)
    const { container } = render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByTitle('Reproducir'))

    expect(container.querySelector('video.rendered-preview-video')).not.toBeInTheDocument()
    expect(screen.getByTitle('Pausar')).toBeInTheDocument()
    expect(globalThis.fetch).not.toHaveBeenCalledWith(expect.stringContaining('/api/project/render-preview'), expect.anything())
  })

  it('selects an audio clip and shows its volume inspector', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })

    await userEvent.click(screen.getByRole('button', { name: 'Seleccionar audio score.mp3' }))

    expect(screen.getByRole('heading', { name: 'score.mp3' })).toBeInTheDocument()
    expect(screen.getByLabelText('Volumen del clip')).toHaveValue('12')
    expect(screen.getByRole('button', { name: 'Eliminar audio' })).toBeInTheDocument()
  })

  it('deletes the selected audio block with Delete', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: 'Seleccionar audio score.mp3' }))
    await userEvent.keyboard('{Delete}')

    expect(screen.queryByRole('button', { name: 'Seleccionar audio score.mp3' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /seleccionar SCENE_1/i })).toBeInTheDocument()
  })

  it('undoes the latest project edit from the toolbar', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    const undo = screen.getByRole('button', { name: 'Deshacer' })
    expect(undo).toBeDisabled()

    await userEvent.selectOptions(screen.getByLabelText('Movimiento'), 'pan_left')
    expect(undo).toBeEnabled()
    await userEvent.click(undo)

    expect(screen.getByLabelText('Movimiento')).toHaveValue('static')
    expect(undo).toBeDisabled()
  })

  it('undoes the latest project edit with control z', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.selectOptions(screen.getByLabelText('Movimiento'), 'zoom_out')

    await userEvent.keyboard('{Control>}z{/Control}')

    expect(screen.getByLabelText('Movimiento')).toHaveValue('static')
  })

  it('loads an SRT from the library and exposes its cue on the timeline', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: 'Subtitulos' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cargar es.srt' }))

    expect(await screen.findByRole('button', { name: 'Seleccionar subtitulo Hola mundo' })).toBeInTheDocument()
    expect(screen.getByText('Hola mundo')).toBeInTheDocument()
  })

  it('adds a keyframe at the playhead and opens its inspector', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: 'Anadir keyframe' }))

    expect(screen.getByLabelText('Escala keyframe')).toHaveValue(1)
    expect(screen.getByRole('button', { name: 'Seleccionar keyframe SCENE_1 0.0' })).toBeInTheDocument()
    await userEvent.keyboard('{Control>}z{/Control}')
    expect(screen.queryByRole('button', { name: 'Seleccionar keyframe SCENE_1 0.0' })).not.toBeInTheDocument()
  })

  it('creates a text track and an overlay visible in the preview', async () => {
    render(<App />)
    await screen.findByRole('button', { name: /seleccionar SCENE_1/i })
    await userEvent.click(screen.getByRole('button', { name: 'Anadir pista de texto' }))
    await userEvent.click(screen.getByRole('button', { name: 'Anadir texto a Texto 1' }))

    expect(screen.getByLabelText('Texto del elemento')).toHaveValue('Nuevo texto')
    expect(screen.getByTestId('preview-text')).toHaveTextContent('Nuevo texto')
  })

})
