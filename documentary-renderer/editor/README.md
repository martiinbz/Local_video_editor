# Manifest Studio - Fase 3

Editor web local para revisar y retocar la timeline creada por `project/manifest.json`,
incluyendo audio con waveforms, animacion visual, efectos, subtitulos y pistas de texto.
El manifest original se mantiene intacto; Guardar y Render MP4 escriben primero
`project/manifest.editor.json`.

## Varios proyectos

El proyecto actual sigue viviendo en `project/`. Para trabajar con varios,
crea una carpeta por proyecto dentro de `projects/`, por ejemplo
`projects/episodio-02/`, y coloca dentro la misma estructura (`manifest.json`,
`project/images`, `assets/music`, etc.). El selector superior los detecta
automáticamente. Cada proyecto conserva su propio `manifest.editor.json` y el
servidor recuerda el último proyecto activo en `projects/.active`.

## Edicion de audio

- Pulsa un audio de la biblioteca para escucharlo; pulsa de nuevo para detenerlo.
- Arrastra musica, ambiente o SFX desde la biblioteca hasta su pista.
- Arrastra un clip para moverlo. Los clips se ajustan a decimas y bordes de escena.
- Musica y ambiente no admiten solapes en su propia pista; los SFX si.
- Selecciona un clip para ajustar inicio y volumen o eliminarlo.
- La narracion se puede mover y recortar mediante sus tiradores o el inspector.
- Mute y solo afectan al preview. El render usa los valores del manifest.
- Arrastra los bordes de una escena para cambiar su duracion en tiempo real; las escenas siguientes se recolocan automaticamente.
- Arrastra los bordes de musica o ambiente para acortar o alargar el clip. Si supera la duracion del archivo original, se repite en loop durante el preview y el render.

La primera waveform puede tardar unos segundos. Las siguientes cargas reutilizan la
cache local de `editor/.cache`.

## Edicion visual y texto

- Selecciona una escena y usa **Keyframe** para fijar escala, posicion y rotacion en el playhead.
- Los keyframes se pueden mover en la pista visual; el preview interpola el movimiento en tiempo real.
- Anade efectos desde el inspector o la pestana **Efectos**. Sus segmentos se pueden mover y estirar.
- Coloca archivos `.srt` en `project/subtitles/` y cargalos desde **Subtitulos**.
- Los cues se pueden editar, mover, estirar, dividir, unir y desplazar globalmente.
- Usa **Pista de texto** para crear tantas capas de rotulos como necesites.
- Las fuentes locales viven en `assets/fonts/` y aparecen en la pestana **Fuentes**.
- Textos, keyframes y efectos forman parte del historial y se deshacen con `Ctrl+Z`.

El monitor prioriza velocidad y aproxima algunos efectos. El MP4 de FFmpeg sigue siendo
la referencia final de calidad y sincronizacion.

## Instalacion

Desde la raiz de `documentary-renderer`:

```powershell
python -m pip install -r requirements.txt
Set-Location editor/frontend
npm install
npm run build
Set-Location ../..
```

Si npm muestra `UNABLE_TO_VERIFY_LEAF_SIGNATURE` en este equipo, ejecuta solo esa
instalacion con `npm install --strict-ssl=false`. No guardes ese ajuste globalmente.

## Arranque

```powershell
python editor/start.py
```

Se abre `http://127.0.0.1:8000`. El servidor carga automáticamente las escenas de
`project/manifest.json`, sirve imágenes y audio locales y utiliza el renderer Python
existente para exportar el MP4.

## Desarrollo

En una terminal:

```powershell
python -m editor.backend
```

En otra:

```powershell
Set-Location editor/frontend
npm run dev
```

Vite abre el frontend en `http://127.0.0.1:5173` y redirige `/api` al backend.

## Pruebas

```powershell
python -m pytest
Set-Location editor/frontend
npm test
npm run build
```
